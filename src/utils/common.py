import asyncio
import logging
import os
from threading import Thread
from typing import List, Tuple, TypedDict

import nekoton as nt

from src.models.ever_wallet import EverWallet
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
            (keys, public_keys, addresses) = list(zip(*keys))
    except Exception as e:
        logger.error(f"Error while reading keys file: {e}")
        exit(1)

    logger.info(f"Read {len(keys)} accounts from file {file}")
    return [nt.KeyPair(bytes.fromhex(key)) for key in keys]


def get_accounts_file(file: str, transport: nt.Transport) -> List[EverWallet]:
    keypairs = get_keypairs_file(file)
    return [EverWallet(transport=transport, keypair=keypair) for keypair in keypairs]


def short_addr(addr: nt.Address):
    return f"{str(addr)[:8]}...{str(addr)[-6:]}"


class TxData(TypedDict):
    dst: nt.Address
    value: nt.Tokens
    payload: nt.Cell
    bounce: bool
    timeout: int


async def send_tx(account: EverWallet, tx_data: TxData, retry_count=3, timeout=60) -> nt.Transaction:
    for i in range(retry_count):
        try:
            return await asyncio.wait_for(account.send(**tx_data), timeout=timeout)
        except TimeoutError:
            logging.error(f"Timeout#{i} while sending tx from {account.address} to {tx_data['dst']}, retrying...")
        except RuntimeError:
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
