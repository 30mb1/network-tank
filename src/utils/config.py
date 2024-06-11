from enum import Enum, StrEnum
from typing import TypedDict


class GiverAccType(StrEnum):
    GIVER = "giver"
    WALLET = "ever_wallet"


class CommonConfig(TypedDict):
    keys_file: str
    seed_phrase: str
    accounts_num: int
    jrpc: str
    giver_acc_type: GiverAccType
    giver_secret_key: str
    giver_address: str


class WalletType(StrEnum):
    HIGHLOAD = "highload"
    WALLET = "ever_wallet"


class FundingConfig(TypedDict):
    funding_acc_key: str
    funding_amount: float
    deposit_wallet_type: WalletType


class Strat1(TypedDict):
    messages_count: int
    message_timeout: int
    wallet_type: WalletType


class Strat2(TypedDict):
    messages_per_batch: int
    batch_interval: int
    batch_count: int
    message_timeout: int
    # highload or ever_wallet
    wallet_type: WalletType


class Strat3(Strat2):
    process_count: int


class Config(TypedDict):
    title: str
    common: CommonConfig
    funding: FundingConfig
    strat_1: Strat1
    strat_2: Strat2
    strat_3: Strat3
