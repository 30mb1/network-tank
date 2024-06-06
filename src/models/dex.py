import nekoton as nt

from src.abi import DexPairAbi, DexRootAbi


class DexPair:
    address: nt.Address
    state: nt.AccountState
    transport: nt.JrpcTransport

    def __init__(self, address: nt.Address, transport: nt.JrpcTransport):
        self.address = address
        self.transport = transport

    async def get_token_roots(self) -> tuple[nt.Address, nt.Address]:
        if not self.state:  # cache
            self.state = await self.transport.get_account_state(self.address)
        res = DexPairAbi.get_token_roots().with_args({"answerId": 0}).call(self.state).output
        return res["left"], res["right"]

    async def get_balances(self) -> tuple[int, int]:
        self.state = await self.transport.get_account_state(self.address)
        res = DexPairAbi.get_balances().with_args({"answerId": 0}).call(self.state).output["value0"]
        return res["left_balance"], res["right_balance"]

    async def get_amount_out(self, amount_in: int, token_in: nt.Address) -> int:
        self.state = await self.transport.get_account_state(self.address)
        return (
            DexPairAbi.expected_exchange()
            .with_args({"answerId": 0, "amount": amount_in, "spent_token_root": token_in})
            .call(self.state)
            .output["expected_amount"]
        )


class DexRoot:
    address: nt.Address
    state: nt.AccountState
    transport: nt.JrpcTransport

    def __init__(self, address: nt.Address, transport: nt.JrpcTransport):
        self.address = address
        self.transport = transport

    async def pair_address(self, left: nt.Address, right: nt.Address) -> nt.Address:
        if not self.state:  # cache
            self.state = await self.transport.get_account_state(self.address)
        return (
            DexRootAbi.get_expected_pair_address()
            .with_args({"answerId": 0, "left_root": left, "right_root": right})
            .call(self.state)
            .output["value0"]
        )

    async def pair(self, left: nt.Address, right: nt.Address) -> DexPair:
        address = await self.pair_address(left, right)
        pair_ = DexPair(address, self.transport)
        return pair_
