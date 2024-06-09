import argparse
import asyncio
import logging
import queue
import random
import tomllib

import nekoton as nt

from src.utils.common import get_accounts_file, send_tx, TxData, WalletType, get_accounts_seed, get_accounts
from src.utils.config import Config

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", type=str, default="config.toml", help="TOML config filename")
args = parser.parse_args()


async def main():
    with open(args.config, "rb") as f:
        raw_config: Config = tomllib.load(f)

    common_config = raw_config["common"]
    strat_config = raw_config["strat_2"]

    transport = nt.JrpcTransport(common_config["jrpc"])
    await transport.check_connection()

    # initializing wallets
    wallet_type = strat_config["wallet_type"]
    accounts = get_accounts(transport, common_config, wallet_type)

    msgs_sent = 0
    batch_count = strat_config["batch_count"]
    messages_per_batch = strat_config["messages_per_batch"]
    batch_interval = strat_config["batch_interval"]
    message_timeout = strat_config["message_timeout"]
    total_msgs = batch_count * messages_per_batch

    logging.info(
        f"Sending {total_msgs} messages from {len(accounts)} accounts via batches: "
        f"{batch_count} with {messages_per_batch} messages each per {batch_interval} secs"
    )
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
                tx_data: TxData = {"dst": dst_acc.address, **tx_base}  # type: ignore
                task = tg.create_task(send_tx(sender_account, tx_data, retry_count=100, timeout=message_timeout + 100))
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
