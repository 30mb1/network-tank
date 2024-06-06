import argparse
import asyncio
import logging
import tomllib

import nekoton as nt

from src.models.highload_wallet import HighloadWalletV2
from src.utils.common import get_accounts_file, to_wei, from_wei
from src.utils.config import Config
from src.utils.multisend import multisend_native

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", type=str, default="config.toml", help="TOML config filename")
args = parser.parse_args()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


HIGHLOAD_WALLET_MAX_MSGS = 255


async def main():
    with open(args.config, "rb") as f:
        raw_config: Config = tomllib.load(f)

    transport = nt.JrpcTransport(raw_config["common"]["jrpc"])
    await transport.check_connection()

    # initializing wallets
    accounts = get_accounts_file(raw_config["common"]["keys_file"], transport)
    keypair = nt.KeyPair(bytes.fromhex(raw_config["funding"]["funding_acc_key"]))
    funding_wallet = HighloadWalletV2(transport=transport, keypair=keypair)

    funding_amount = raw_config["funding"]["funding_amount"]
    # checking that funding wallet has enough evers to fund all accounts
    funding_balance = from_wei(await funding_wallet.get_balance())
    min_balance = funding_amount * len(accounts) + (len(accounts) / HIGHLOAD_WALLET_MAX_MSGS) * 2
    if funding_balance < min_balance:
        logger.error(f"Insufficient funds in funding account. Required: {min_balance:.1f}, have: {funding_balance:.1f}")
        exit(1)

    # divide accounts in 255-sized chunks
    chunks = [accounts[i : i + HIGHLOAD_WALLET_MAX_MSGS] for i in range(0, len(accounts), HIGHLOAD_WALLET_MAX_MSGS)]
    for idx, chunk in enumerate(chunks):
        receivers = [(i.address, to_wei(funding_amount)) for i in chunk]
        logger.info(f"Sending {funding_amount} evers to {len(receivers)} accounts, chunk {idx + 1}/{len(chunks)}")
        await multisend_native(funding_wallet, receivers)


asyncio.run(main())
