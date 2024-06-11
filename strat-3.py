import argparse
import asyncio
import logging
import queue
import random
import tomllib
from multiprocessing import Pool
from typing import List

import nekoton as nt

from src.utils.common import TxData, get_accounts, send_tx_batch
from src.utils.config import Config

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", type=str, default="config.toml", help="TOML config filename")
args = parser.parse_args()


with open(args.config, "rb") as f:
    raw_config: Config = tomllib.load(f)

common_config = raw_config["common"]
strat_config = raw_config["strat_3"]

process_count = strat_config["process_count"]


def run_batch_loop(idx):
    async def _inner():
        base = f"Process #{idx + 1}: "
        transport = nt.JrpcTransport(common_config["jrpc"])
        await transport.check_connection()
        # initializing wallets
        wallet_type = strat_config["wallet_type"]
        accounts = get_accounts(transport, common_config, wallet_type)
        chunk_size = (len(accounts) // process_count) + 1
        accounts = accounts[idx * chunk_size: (idx + 1) * chunk_size]

        msgs_sent = 0
        batch_count = strat_config["batch_count"]
        messages_per_batch = strat_config["messages_per_batch"]
        batch_interval = strat_config["batch_interval"]
        message_timeout = strat_config["message_timeout"]
        total_msgs = batch_count * messages_per_batch

        logging.info(
            f"{base}Sending {total_msgs} messages from {len(accounts)} accounts via batches: "
            f"{batch_count} with {messages_per_batch} messages each per {batch_interval} secs"
        )
        accs_queue = queue.Queue()
        for acc in accounts:
            accs_queue.put(acc)

        def send_callback(task: asyncio.Task, *args):
            if task.exception() is None:
                nonlocal msgs_sent
                msgs_sent += 1
                logging.info(f"{base}Total {msgs_sent} messages sent")
            else:
                logging.error(f"{base}Error while sending message: {task.exception()}")

        async def send_batch():
            tx_base = {"value": nt.Tokens("0.1"), "payload": None, "bounce": False, "timeout": message_timeout}
            async with asyncio.TaskGroup() as tg:
                for _ in range(messages_per_batch):
                    sender_account = accs_queue.get()
                    accs_queue.put(sender_account)
                    txs: List[TxData] = []  # type: ignore
                    for j in range(strat_config['internals_per_message']):
                        dst_acc = random.choice(accounts)
                        txs.append({"dst": dst_acc.address, **tx_base})
                    task = tg.create_task(
                        send_tx_batch(sender_account, txs, retry_count=100, timeout=message_timeout + 100)
                    )
                    task.add_done_callback(send_callback)

        tasks = []
        for i in range(batch_count):
            # send batch
            logging.info(f"{base}Sending batch #{i + 1}/{batch_count}")
            tasks.append(asyncio.create_task(send_batch()))
            await asyncio.sleep(batch_interval)

        logging.info(f"{base}All batches sent, waiting for msgs to be delivered")
        await asyncio.gather(*tasks)

    asyncio.run(_inner())


if __name__ == "__main__":
    with Pool(process_count) as p:
        p.map(run_batch_loop, range(process_count))
