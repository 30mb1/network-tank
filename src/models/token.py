from abc import abstractmethod, ABC
from functools import cached_property
from typing import Any

import nekoton as nt

from src.abi import TokenWalletAbi, TokenRootAbi
from src.models.ever_wallet import EverWallet
from src.utils.common import send_tx, to_sync


class Token(ABC):
    address: nt.Address
    transport: Any

    def __init__(self, address: nt.Address, transport: Any):
        self.address = address
        self.transport = transport

    @to_sync
    async def __state(self):
        return await self.transport.get_account_state(self.address)

    # weird hack to avoid type errors with returning coroutines
    @cached_property
    def state(self) -> Any:
        return self.__state()

    @property
    @abstractmethod
    def decimals(self) -> int: ...

    @property
    @abstractmethod
    def symbol(self) -> str: ...

    @abstractmethod
    def wallet_addr(self, addr: nt.Address | str) -> nt.Address: ...

    @abstractmethod
    async def balance(self, addr: nt.Address | str) -> int: ...

    def from_dec(self, value: int | nt.Tokens) -> float:
        return int(value) / 10**self.decimals

    def to_dec(self, value: float | str) -> int:
        return int(float(value) * 10**self.decimals)

    @staticmethod
    @abstractmethod
    def encode_transfer(src: nt.Address, dst: nt.Address, value: int, deploy_wallet_value: int = None) -> nt.Cell: ...

    @abstractmethod
    async def transfer(self, sender: EverWallet, dst: nt.Address, value: int) -> nt.Transaction: ...


class Tip3Token(Token):
    transport: nt.JrpcTransport

    def __init__(self, address: nt.Address, transport: nt.JrpcTransport):
        super().__init__(address, transport)

    @property
    def decimals(self) -> int:
        return TokenRootAbi.decimals().with_args({"answerId": 0}).call(self.state).output["value0"]

    @property
    def symbol(self) -> str:
        return TokenRootAbi.symbol().with_args({"answerId": 0}).call(self.state).output["value0"]

    def wallet_addr(self, addr: nt.Address | str) -> nt.Address:
        addr = nt.Address(str(addr))
        return (
            TokenRootAbi.wallet_of().with_args({"answerId": 0, "walletOwner": addr}).call(self.state).output["value0"]
        )

    async def balance(self, addr: nt.Address | str) -> int:
        token_wallet_addr = self.wallet_addr(addr)
        token_wallet_state = await self.transport.get_account_state(token_wallet_addr)
        if not token_wallet_state:
            return 0
        return int(TokenWalletAbi.balance().with_args({"answerId": 0}).call(token_wallet_state).output["value0"])

    @staticmethod
    def encode_transfer(src: nt.Address, dst: nt.Address, value: int, deploy_wallet_value: int = None) -> nt.Cell:
        deploy_wallet_value: nt.Tokens = deploy_wallet_value or nt.Tokens("0.1")
        return (
            TokenWalletAbi.transfer()
            .with_args(
                {
                    "recipient": dst,
                    "amount": value,
                    "deployWalletValue": deploy_wallet_value,
                    "remainingGasTo": src,
                    "notify": False,
                    "payload": nt.Cell(),
                }
            )
            .encode_internal_input()
        )

    async def transfer(self, sender: EverWallet, dst: nt.Address, value: int) -> nt.Transaction:
        sender_token_wallet = self.wallet_addr(sender.address)
        payload = self.encode_transfer(sender.address, dst, value)
        tx_data = {
            "dst": sender_token_wallet,
            "value": nt.Tokens("0.25"),
            "bounce": True,
            "payload": payload,
            "timeout": 30
        }
        return await send_tx(sender, tx_data)

