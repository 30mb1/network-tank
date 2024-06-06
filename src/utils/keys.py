from typing import List

import nekoton as nt
import os

import logging

from src.models.ever_wallet import EverWallet



def rotate_archive(filename: str):
    os.makedirs("archive_tvm", exist_ok=True)
    # get names of all files in 'archive' dir
    files = os.listdir("archive_tvm")
    # all files in 'archive' dir have xxx.N format
    # get highest N through all files
    highest = max([int(f.split(".")[2]) for f in files if ".".join(f.split(".")[:2]) == filename] or [0])

    # if keys.txt file exists in current dir, move it to archive
    if os.path.exists(filename):
        os.rename(filename, f"archive_tvm/{filename}.{highest + 1}")
        logging.info(f"Archived {filename} to archive_tvm/{filename}.{highest + 1}")


def gen_keys_from_seed(number: int, seed_phrase: str) -> List[nt.KeyPair]:
    keys = []
    seed = nt.Bip39Seed(seed_phrase)
    for i in range(number):
        keypair = seed.derive(f"m/44'/396'/0'/0/{i}")
        keys.append(keypair)
    return keys


def gen_keys_from_seed_file(number: int, filename: str, seed_phrase: str):
    rotate_archive(filename)

    keys = gen_keys_from_seed(number, seed_phrase)
    with open(filename, "w") as f:
        for idx, keypair in enumerate(keys):
            logging.info(f"Key {idx + 1} generated, public key: {keypair.public_key.encode('hex')}")
            addr = EverWallet.compute_address(nt.PublicKey.from_bytes(bytes.fromhex(str(keypair.public_key))))
            f.write(f"{keypair.secret_key.hex()},{keypair.public_key.encode('hex')},{addr}\n")
    logging.info(f"Generated {number} keys and dumped to {filename}")
