from typing import Optional

import nekoton as _nt

_giver_v2_abi = _nt.ContractAbi("""{"ABI version": 2,
    "header": ["time", "expire"],
    "functions": [
        {
            "name": "upgrade",
            "inputs": [
                {"name":"newcode","type":"cell"}
            ],
            "outputs": [
            ]
        },
        {
            "name": "sendTransaction",
            "inputs": [
                {"name":"dest","type":"address"},
                {"name":"value","type":"uint128"},
                {"name":"bounce","type":"bool"}
            ],
            "outputs": [
            ]
        },
        {
            "name": "getMessages",
            "inputs": [
            ],
            "outputs": [
                {"components":[{"name":"hash","type":"uint256"},{"name":"expireAt","type":"uint64"}],"name":"messages","type":"tuple[]"}
            ]
        },
        {
            "name": "constructor",
            "inputs": [
            ],
            "outputs": [
            ]
        }
    ],
    "events": [
    ]
}""")

_giver_v2_constructor = _giver_v2_abi.get_function("constructor")
_giver_v2_send_grams = _giver_v2_abi.get_function("sendTransaction")


class GiverV2:
    def __init__(self, transport: _nt.Transport, address: _nt.Address, keypair: _nt.KeyPair):
        self._transport = transport
        self._keypair = keypair
        self._address = address

    @property
    def address(self) -> _nt.Address:
        return self._address

    @property
    def keypair(self) -> _nt.KeyPair:
        return self._keypair

    async def send(self, target: _nt.Address, amount: _nt.Tokens, bounce: bool = False):
        signature_id = await self._transport.get_signature_id()

        # Prepare external message
        message = _giver_v2_send_grams.encode_external_message(
            self.address,
            input={
                "dest": target,
                "value": amount,
                "bounce": bounce
            },
            public_key=self._keypair.public_key,
        ).sign(self._keypair, signature_id)

        # Send external message
        tx = await self._transport.send_external_message(message)
        if tx is None:
            raise RuntimeError("Message expired")

        return tx

    async def get_account_state(self) -> Optional[_nt.AccountState]:
        return await self._transport.get_account_state(self.address)

    async def get_balance(self) -> _nt.Tokens:
        state = await self.get_account_state()
        if state is None:
            return _nt.Tokens(0)
        else:
            return state.balance