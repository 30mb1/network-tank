import asyncio
import logging
import os
from threading import Thread
from typing import List, Tuple, TypedDict

import nekoton as nt

from src.models.ever_wallet import EverWallet
from src.models.highload_wallet import HighloadWalletV2
from src.utils.config import WalletType, CommonConfig
from src.utils.keys import gen_keys_from_seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def from_wei(value: int | nt.Tokens | float) -> float:
    return int(value) / 10**9


def to_wei(value: float | str) -> int:
    return int(float(value) * 10**9)


def from_dec(value: int | nt.Tokens, decimals: int) -> float:
    return int(value) / 10**decimals


def to_dec(value: float | str, decimals: int) -> int:
    return int(float(value) * 10**decimals)


async def get_transport(jrpc: str) -> nt.JrpcTransport:
    transport = nt.JrpcTransport(jrpc)
    await transport.check_connection()
    return transport


def get_wallets(keys: List[nt.KeyPair], transport: nt.Transport) -> List[EverWallet]:
    return [EverWallet(transport=transport, keypair=keypair) for keypair in keys]


def gen_seed() -> nt.Bip39Seed:
    return nt.Bip39Seed.generate()


def get_addrs_from_seed(seed: str, count: int) -> List[Tuple[nt.Address, nt.KeyPair]]:
    keys = gen_keys_from_seed(count, seed)
    return list(zip([EverWallet.compute_address(keypair.public_key) for keypair in keys], keys))


def get_keypairs_file(file: str) -> List[nt.KeyPair]:
    logger = logging.getLogger(__name__)
    # check if file exists
    if not os.path.exists(file):
        logger.error(f"File {file} with keys not found")
        exit(1)

    try:
        with open(file) as f:
            keys = f.readlines()
            keys = [key.strip().split(",") for key in keys]
            (keys, public_keys) = list(zip(*keys))
    except Exception as e:
        logger.error(f"Error while reading keys file: {e}")
        exit(1)

    logger.info(f"Read {len(keys)} accounts from file {file}")
    return [nt.KeyPair(bytes.fromhex(key)) for key in keys]


def get_accounts(transport: nt.Transport, config: CommonConfig, wallet_type: WalletType) -> List[EverWallet | HighloadWalletV2]:
    if config["keys_file"]:
        logging.info(f"Using keys file {config['keys_file']} for getting accounts")
        return get_accounts_file(config["keys_file"], transport, wallet_type)
    else:
        logging.info(f"Using seed for getting accounts")
        if not (config["seed_phrase"] and config["accounts_num"]):
            raise Exception("Seed phrase and accounts number must be provided in config")
        return get_accounts_seed(config["seed_phrase"], config["accounts_num"], transport, wallet_type)


def get_accounts_seed(
    seed: str, count: int, transport: nt.Transport, type_: WalletType = WalletType.WALLET
) -> List[EverWallet | HighloadWalletV2]:
    keys = gen_keys_from_seed(count, seed)
    if type_ == WalletType.HIGHLOAD:
        return [HighloadWalletV2(transport=transport, keypair=keypair) for keypair in keys]
    else:
        return [EverWallet(transport=transport, keypair=keypair) for keypair in keys]


def get_accounts_file(
    file: str, transport: nt.Transport, type_: WalletType = WalletType.WALLET
) -> List[EverWallet | HighloadWalletV2]:
    keys = get_keypairs_file(file)
    if type_ == WalletType.HIGHLOAD:
        return [HighloadWalletV2(transport=transport, keypair=keypair) for keypair in keys]
    else:
        return [EverWallet(transport=transport, keypair=keypair) for keypair in keys]


def short_addr(addr: nt.Address):
    return f"{str(addr)[:8]}...{str(addr)[-6:]}"


class TxData(TypedDict):
    dst: nt.Address
    value: nt.Tokens
    payload: nt.Cell
    bounce: bool
    timeout: int


async def send_tx(
    account: EverWallet | HighloadWalletV2, tx_data: TxData, retry_count=3, timeout=60, silent=True
) -> nt.Transaction:
    for i in range(retry_count):
        try:
            return await asyncio.wait_for(account.send(**tx_data), timeout=timeout)
        except TimeoutError:
            if not silent:
                logging.error(
                    f"Timeout#{i} while sending tx from {short_addr(account.address)} to {short_addr(tx_data['dst'])}, retrying..."
                )
        except RuntimeError:
            if not silent:
                logging.error(f"Message expired#{i}, retrying...")
    raise Exception(f"Timeout while sending tx")


async def send_tx_batch(
    account: HighloadWalletV2, txs: List[TxData], retry_count=3, timeout=60, silent=True
) -> nt.Transaction:
    messages: List[Tuple[nt.Message, 3]] = []
    for tx in txs:
        message = nt.Message(
            header=nt.InternalMessageHeader(  # type: ignore
                value=tx["value"],  # type: ignore
                dst=tx["dst"],
                bounce=tx["bounce"],
            ),
            body=tx.get("payload"),
        )
        messages.append((message, 3))
    for i in range(retry_count):
        try:
            return await asyncio.wait_for(account.send_raw(messages, txs[0]["timeout"]), timeout=timeout)
        except TimeoutError:
            if not silent:
                logging.error(
                    f"Timeout#{i} while sending txs from {short_addr(account.address)} retrying..."
                )
        except RuntimeError:
            if not silent:
                logging.error(f"Message expired#{i}, retrying...")
    raise Exception(f"Timeout while sending tx")


class SyncThread(Thread):
    result = None

    def run(self):
        self.result = asyncio.run(self._target(*self._args, **self._kwargs))  # type: ignore


def to_sync(func):
    def wrapper(*args, **kwargs):
        thread = SyncThread(target=func, args=args, kwargs=kwargs)
        thread.start()
        thread.join()
        return thread.result

    return wrapper
