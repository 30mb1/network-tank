import argparse
from src.utils.keys import gen_keys_from_seed_file


parser = argparse.ArgumentParser()
parser.add_argument("-n", "--number", type=int, default=10, help="Number of keys to generate")
parser.add_argument("-f", "--file", type=str, default="keys.txt", help="Filename with account keys")
parser.add_argument("-s", "--seed", required=True, type=str, help="Seed phrase to generate keys from, could be omitted")
args = parser.parse_args()


gen_keys_from_seed_file(args.number, args.file, args.seed)
