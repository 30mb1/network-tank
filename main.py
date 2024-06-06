import asyncio
from typing import TypedDict

import nekoton as nt
import tomllib

import argparse
import random

from src.models.ever_wallet import EverWallet
from src.utils.common import get_accounts_file, send_tx, TxData
from src.utils.config import Config

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", type=str, default="config.toml", help="TOML config filename")
args = parser.parse_args()


async def main():
    with open(args.config, "rb") as f:
        raw_config: Config = tomllib.load(f)

    transport = nt.JrpcTransport(raw_config["common"]["jrpc"])
    await transport.check_connection()

    # initializing wallets
    accounts = get_accounts_file(raw_config["common"]["keys_file"], transport)

    def send_random_messages(sender_account: EverWallet, count: int):
        msg_timeout = raw_config["native_tank"]["message_timeout"]
        tx_base = {"value": nt.Tokens("0.1"), "payload": nt.Cell(), "bounce": False, "timeout": msg_timeout}
        for i in range(count):
            dst_acc = random.choice(accounts)
            tx_data: TxData = {'dst': dst_acc.address, **tx_base} # type: ignore
            send_tx(
                sender_account, tx_data, retry_count=100, timeout=msg_timeout + 2
            )  # additional 2 seconds for network latency and other costs

    messages_per_account = int(raw_config["native_tank"]["messages_count"] / len(accounts))
    tasks = []
    for account in accounts:
        tasks.append(asyncio.create_task(send_random_messages(account, messages_per_account)))

    await asyncio.gather(*tasks)

asyncio.run(main())
