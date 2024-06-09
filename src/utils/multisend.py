import asyncio
import logging
from typing import Tuple, List

import nekoton as nt

from src.models.ever_wallet import EverWallet
from src.models.highload_wallet import HighloadWalletV2
from src.models.token import Token
from src.utils.common import send_tx, short_addr, from_wei


async def multisend_native(account: HighloadWalletV2, receivers: list[Tuple[nt.Address, int]]) -> nt.Transaction:
    """
    Send tokens to multiple addresses in one transaction
    :param account: HighloadWalletV2
    :param receivers: List of addresses and amounts
    :return: Transaction
    """
    messages = []
    for receiver, amount in receivers:
        message = nt.Message(
            header=nt.InternalMessageHeader(  # type: ignore
                value=nt.Tokens.from_nano(amount),  # type: ignore
                dst=receiver,
                bounce=False,
            )
        )
        messages.append((message, 3))

    return await account.send_raw(messages)


async def multisend_token(
    account: HighloadWalletV2, token: Token, receivers: list[Tuple[nt.Address, int]]
) -> nt.Transaction:
    """
    Send tokens to multiple addresses in one transaction
    :param account: HighloadWalletV2
    :param token: Token model
    :param receivers: List of addresses and amounts
    :return: Transaction
    """
    messages = []
    sender_token_wallet = token.wallet_addr(account.address)
    for receiver, amount in receivers:
        payload = token.encode_transfer(account.address, receiver, amount)
        message = nt.Message(
            header=nt.InternalMessageHeader(value=nt.Tokens("0.25"), dst=sender_token_wallet, bounce=True), body=payload  # type: ignore
        )
        messages.append((message, 3))

    return await account.send_raw(messages)


async def multisend(
    account: HighloadWalletV2,
    native_receivers: list[Tuple[nt.Address, int]],
    token_receivers: list[Tuple[nt.Address, int]],
    token: Token,
):
    """
    Send tokens to multiple addresses in one transaction
    :param account: HighloadWalletV2
    :param token: Token model
    :param native_receivers: List of addresses and amounts for native tokens
    :param token_receivers: List of addresses and amounts for token
    """
    if native_receivers:
        await multisend_native(account, native_receivers)
    if token_receivers:
        await multisend_token(account, token, token_receivers)


async def transfer_native_batch(transfers: List[Tuple[EverWallet, nt.Address, int]]):
    """
    Transfer a batch of tokens to multiple addresses
    :param transfers: List of tuples with sender Account, receiver address and amount
    """

    # asynchronously send tokens to multiple addresses
    async def log_send_tx(acc: EverWallet, dst: nt.Address, amount: int):
        logging.info(f"Account {short_addr(acc.address)} sending {from_wei(amount):.3f} ever to {short_addr(dst)}...")
        tx = await send_tx(
            acc, {"dst": dst, "value": nt.Tokens.from_nano(amount), "payload": nt.Cell(), "bounce": False}
        )
        logging.info(
            f"Account {short_addr(acc.address)} sent {from_wei(amount):.3f} ever to {short_addr(dst)},"
            f" tx: {tx.hash.hex()}"
        )

    await asyncio.gather(*[log_send_tx(acc, dst, amount) for acc, dst, amount in transfers])


async def transfer_token_batch(transfer: List[Tuple[EverWallet, nt.Address, int]], token: Token):
    """
    Transfer a batch of tokens to multiple addresses
    :param transfer: List of tuples with sender Account, receiver address and amount
    :param token: Token model
    """

    # asynchronously send tokens to multiple addresses
    async def log_send_tx(acc: EverWallet, dst: nt.Address, amount: int):
        logging.info(
            f"Account {short_addr(acc.address)} sending {token.from_dec(amount):.3f} {token.symbol} to {short_addr(dst)}..."
        )
        tx = await token.transfer(acc, dst, amount)
        logging.info(
            f"Account {short_addr(acc.address)} sent {token.from_dec(amount):.3f} {token.symbol} to {short_addr(dst)},"
            f" tx: {tx.hash.hex()}"
        )

    await asyncio.gather(*[log_send_tx(acc, dst, amount) for acc, dst, amount in transfer])
