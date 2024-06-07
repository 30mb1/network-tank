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
    batch_count = raw_config["strat_2"]["batch_count"]
    messages_per_batch = raw_config["strat_2"]["messages_per_batch"]
    batch_interval = raw_config["strat_2"]["batch_interval"]
    message_timeout = raw_config["strat_2"]["message_timeout"]
    total_msgs = batch_count * messages_per_batch

    logging.info(f"Sending {total_msgs} messages from {len(accounts)} accounts via batches: "
                 f"{batch_count} with {messages_per_batch} messages each per {batch_interval} secs")
    accs_queue = queue.Queue()
    for acc in accounts:
        accs_queue.put(acc)

    def send_callback(*_):
        nonlocal msgs_sent
        msgs_sent += 1
        logging.info(f"Total {msgs_sent} messages sent")

    async def send_batch():
        tx_base = {"value": nt.Tokens("0.1"), "payload": nt.Cell(), "bounce": False, "timeout": message_timeout}
        async with asyncio.TaskGroup() as tg:
            for _ in range(messages_per_batch):
                sender_account = accs_queue.get()
                accs_queue.put(sender_account)
                dst_acc = random.choice(accounts)
                tx_data: TxData = {'dst': dst_acc.address, **tx_base}  # type: ignore
                task = tg.create_task(send_tx(sender_account, tx_data, retry_count=100, timeout=message_timeout + 2))
                task.add_done_callback(send_callback)

    tasks = []
    for i in range(batch_count):
        # send batch
        logging.info(f"Sending batch #{i + 1}/{batch_count}")
        tasks.append(asyncio.create_task(send_batch()))
        await asyncio.sleep(batch_interval)

    logging.info(f"All batches sent, waiting for msgs to be delivered")
    await asyncio.gather(*tasks)


asyncio.run(main())
