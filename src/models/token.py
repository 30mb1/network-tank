from abc import abstractmethod, ABC
from functools import cached_property, cache
from typing import Any, List

import nekoton as nt
import requests
from bitarray import bitarray
from pytoniq import begin_cell, Cell, Address as TAddress, LiteBalancer
from pytoniq_core import Slice

from tvm.abi import TokenWalletAbi, TokenRootAbi
from tvm.models.ever_wallet import EverWallet
from tvm.utils import send_tx
from tvm.utils.common import to_sync
from hashlib import sha256


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
        }
        return await send_tx(sender, tx_data)


class JettonToken(Token):
    transport: LiteBalancer

    def __init__(self, address: nt.Address, transport: LiteBalancer):
        super().__init__(address, transport)

    @to_sync
    async def __jetton_data(self) -> dict:
        transport = LiteBalancer.from_mainnet_config(trust_level=1)
        await transport.start_up()
        stack = await transport.run_get_method(address=str(self.address), method="get_jetton_data", stack=[])
        return {
            "total_supply": stack[0],
            "is_mintable": stack[1] != 0,
            "admin_address": stack[2].load_address(),
            "content": stack[3],
            "wallet_code": stack[4],
        }

    @cached_property
    def jetton_data(self) -> dict:
        return self.__jetton_data()  # type: ignore

    def flatten_snake_cell(self, slice1: Slice) -> bytes:
        prefix = slice1.load_uint(8)  # snake format prefix
        if prefix == 1:
            raise ValueError("Token uses chunk format for onchain content! Not supported")

        bit_res: bitarray = bitarray()
        while slice1.remaining_bits > 0 or slice1.remaining_refs > 0:
            if slice1.remaining_bits:
                data = slice1.load_bits(slice1.remaining_bits)
                bit_res.extend(data)
            if slice1.refs:
                slice1 = slice1.refs[0].to_slice()
        return bit_res.tobytes()

    def read_onchain_content(self, slice1: Slice):
        dict_res = slice1.load_dict(256)
        content_keys = ["symbol", "decimals", "name", "description", "image", "uri"]
        result = {}
        for key in content_keys:
            val_slice: Slice = dict_res.get(int(sha256(key.encode("utf-8")).hexdigest(), 16))
            if not val_slice:
                continue
            val_slice = val_slice if val_slice.remaining_refs == 0 else val_slice.load_ref().to_slice()
            # we suppose values are always snake formatted
            val_bytes = self.flatten_snake_cell(val_slice)

            if key in ["name", "description", "symbol", "decimals"]:
                result[key] = val_bytes.decode("utf-8", "ignore")

            if key in ["uri", "image"]:
                result[key] = val_bytes.decode("ascii")

        # if uri is presented try to get part of content from there with priority on onchain values
        if "uri" in result:
            res = requests.get(result["uri"]).json()
            for key, value in res.items():
                if key not in result:  # not overwriting onchain values
                    result[key] = value

        return result

    @cached_property
    def content(self):
        content: Cell = self.jetton_data["content"]
        slice1 = content.to_slice()
        prefix = slice1.load_uint(8)
        if prefix == 0:
            return self.read_onchain_content(slice1)
        # if
        pass

    @property
    def decimals(self) -> int:
        return int(self.content["decimals"])

    @property
    def symbol(self) -> str:
        return self.content["symbol"]

    @cache
    async def wallet_addr(self, addr: nt.Address) -> nt.Address:
        stack = await self.transport.run_get_method(
            address=str(self.address),
            method="get_wallet_address",
            stack=[begin_cell().store_address(str(addr)).end_cell().begin_parse()],
        )
        address: TAddress = stack[0].load_address()
        return nt.Address(address.to_str())

    async def _get_wallet_data(self, wallet_addr: nt.Address) -> list:
        stack = await self.transport.run_get_method(address=str(wallet_addr), method="get_wallet_data", stack=[])
        return [stack[0], stack[1].load_address(), stack[2].load_address(), stack[3]]

    async def balance(self, addr: nt.Address | str) -> int:
        token_wallet_addr = await self.wallet_addr(addr)
        return (await self._get_wallet_data(token_wallet_addr))[0]

    @staticmethod
    def encode_transfer(src: nt.Address, dst: nt.Address, value: int, deploy_wallet_value: int = None) -> nt.Cell:
        # schema:
        #   (int) query_id
        #   (uint) amount
        #   (address) destination
        #   (address) response_address
        #   (maybe_ref) custom_payload
        #   (uint) forward_amount
        #   (maybe_ref) forward_payload
        payload_cell = (
            begin_cell()
            .store_uint(0xF8A7EA5, 32)
            .store_uint(0, 64)
            .store_coins(value)
            .store_address(str(dst))
            .store_address(None)
            .store_maybe_ref(None)
            .store_coins(0)
            .store_maybe_ref(None)
            .end_cell()
        )
        return nt.Cell.from_bytes(payload_cell.to_boc())

    async def transfer(self, sender: EverWallet, dst: nt.Address, value: int) -> nt.Transaction:
        pass
