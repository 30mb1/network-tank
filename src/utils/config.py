from typing import TypedDict


class CommonConfig(TypedDict):
    keys_file: str
    jrpc: str
    giver_secret_key: str
    giver_address: str


class FundingConfig(TypedDict):
    funding_acc_key: str
    funding_amount: float


class NativeTankConfig(TypedDict):
    messages_count: int
    message_timeout: int


class Config(TypedDict):
    title: str
    common: CommonConfig
    funding: FundingConfig
    native_tank: NativeTankConfig
