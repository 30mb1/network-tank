import argparse
import asyncio
import logging
import queue
import random
import tomllib

import nekoton as nt

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
    msgs_sent = 0
    total_msgs = raw_config["strat_1"]["messages_count"]
    logging.info(f"Sending {total_msgs} messages from {len(accounts)} accounts")
    accs_queue = queue.Queue()
    for acc in accounts:
        accs_queue.put(acc)

    async def send_random_messages():
        nonlocal msgs_sent

        msg_timeout = raw_config["strat_1"]["message_timeout"]
        tx_base = {"value": nt.Tokens("0.1"), "payload": nt.Cell(), "bounce": False, "timeout": msg_timeout}
        while (total_msgs - msgs_sent) > 0:
            sender_account = accs_queue.get()
            dst_acc = random.choice(accounts)
            tx_data: TxData = {'dst': dst_acc.address, **tx_base}  # type: ignore
            await send_tx(
                sender_account, tx_data, retry_count=100, timeout=msg_timeout + 2
            )  # additional 2 seconds for network latency and other costs
            msgs_sent += 1
            accs_queue.put(sender_account)
            logging.info(f"Total {msgs_sent} messages sent")

    tasks = [asyncio.create_task(send_random_messages()) for _ in range(len(accounts))]
    await asyncio.gather(*tasks)

asyncio.run(main())
