import argparse
import asyncio
import logging
import tomllib

import nekoton as nt

from src.models.ever_wallet import EverWallet
from src.models.giver_v2 import GiverV2
from src.models.highload_wallet import HighloadWalletV2
from src.utils.common import get_accounts_file, to_wei, from_wei
from src.utils.config import Config, GiverAccType
from src.utils.multisend import multisend_native

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", type=str, default="config.toml", help="TOML config filename")
args = parser.parse_args()


HIGHLOAD_WALLET_MAX_MSGS = 255


async def main():
    with open(args.config, "rb") as f:
        raw_config: Config = tomllib.load(f)

    transport = nt.JrpcTransport(raw_config["common"]["jrpc"])
    await transport.check_connection()

    wallet_type = raw_config["funding"]["deposit_wallet_type"]
    # initializing wallets
    accounts = get_accounts_file(raw_config["common"]["keys_file"], transport, type_=wallet_type)
    funding_keypair = nt.KeyPair(bytes.fromhex(raw_config["funding"]["funding_acc_key"]))
    giver_keypair = nt.KeyPair(bytes.fromhex(raw_config["common"]["giver_secret_key"]))
    giver_address = nt.Address(raw_config["common"]["giver_address"])

    funding_wallet = HighloadWalletV2(transport=transport, keypair=funding_keypair)
    if raw_config["common"]["giver_acc_type"] == GiverAccType.GIVER:
        giver_wallet = GiverV2(transport=transport, address=giver_address, keypair=giver_keypair)
    else:
        giver_wallet = EverWallet(transport=transport, keypair=giver_keypair)

    # fetching balances for giver and funding wallet
    funding_balance = from_wei(await funding_wallet.get_balance())
    giver_balance = from_wei(await giver_wallet.get_balance())

    logging.info(f"Funding wallet: {funding_wallet.address}, balance: {funding_balance:.1f}")
    logging.info(f"Giver wallet: {giver_wallet.address}, balance: {giver_balance:.1f}")

    # checking that funding wallet has enough evers to fund all accounts
    funding_amount = raw_config["funding"]["funding_amount"]
    # we suppose highload wallet needs 2 evers of tech costs for sending 255 msgs pack
    min_balance = funding_amount * len(accounts) + (len(accounts) / HIGHLOAD_WALLET_MAX_MSGS) * 2
    if funding_balance < min_balance:
        logging.info(f"Refilling funding wallet from giver. Required: {min_balance:.1f}, have: {funding_balance:.1f}")
        await giver_wallet.send(funding_wallet.address, nt.Tokens.from_nano(to_wei(min_balance)))

    logging.info(f"Sending {len(accounts)} accounts {raw_config['funding']['funding_amount']} evers each")
    # divide accounts in 255-sized chunks
    chunks = [accounts[i : i + HIGHLOAD_WALLET_MAX_MSGS] for i in range(0, len(accounts), HIGHLOAD_WALLET_MAX_MSGS)]
    for idx, chunk in enumerate(chunks):
        receivers = [(i.address, to_wei(funding_amount)) for i in chunk]
        logging.info(f"Sending {funding_amount} evers to {len(receivers)} accounts, chunk {idx + 1}/{len(chunks)}")
        await multisend_native(funding_wallet, receivers)


asyncio.run(main())
