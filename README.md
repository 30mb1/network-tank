# network-tank
## Install
1. Create virtual environment
```bash
pdm install
# or manually
virtualenv -p python3 .venv
```
2. Activate it and install nekoton (`feature/get_blockchain_config` branch)
```bash
source .venv/bin/activate
pdm add ${PATH_TO_LOCAL_NEKOTON_BUILD}
```
## Config
1. Crete .toml config from template and fill it with your data
```bash
cp config.toml.example config.toml
```
2. Generate keypairs (optional, if you want to use keys file)
```bash
# n - number of accounts to generate
python gen_keys.py -n 100 --seed "${YOUR_SEED_PHRASE}"
```
## Run
### Test case 1
Create N parallel flows (N = number of accounts). Every flow sends tx by tx synchronously after former tx is confirmed.
Tx is a simple value transfer to another account.
```bash
python strat-1.py
```
### Test case 2
Every M seconds send batch of N messages asynchronously. Batches are independent and don't wait for each other,
so that account could be used for sending new message before previous one is confirmed. Generates more load than strat-1.
Tx is a simple value transfer to another account.

```bash
python strat-2.py
```