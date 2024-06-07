import argparse
import asyncio
import logging
import tomllib

import nekoton as nt

from src.utils.common import from_wei, get_accounts_file
from src.utils.config import Config

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", type=str, default="config.toml", help="TOML config filename")
parser.add_argument('-t', '--type', type=str, choices=['highload', 'ever_wallet'], help='Wallet type')
args = parser.parse_args()


async def print_balances():
    with open(args.config, "rb") as f:
        raw_config: Config = tomllib.load(f)

    transport = nt.JrpcTransport(raw_config["common"]["jrpc"])
    await transport.check_connection()

    accounts = get_accounts_file(raw_config["common"]["keys_file"], transport, args.type)

    logging.info(f"Fetched balances for provided accounts:")
    balances = await asyncio.gather(*[acc.get_balance() for acc in accounts])

    for idx, acc in enumerate(accounts):
        logging.info(f"{acc.address} balance: {from_wei(balances[idx]):.1f} ever")
    # get sum of all balances
    ever_sum = sum([int(i) for i in balances])
    # log it
    logging.info(f"Total ever sum: {from_wei(ever_sum):.3f} ever")


asyncio.run(print_balances())
