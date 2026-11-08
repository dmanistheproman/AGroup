"""Generate the test data set (X-05) into its own database, separate from the demo database.

    python scripts/generate_data.py                       instance/test-data.sqlite3, seed 314, full scale
    python scripts/generate_data.py --reset               start again from an empty file
    python scripts/generate_data.py --scale 0.2 --seed 7 --database instance/small.sqlite3
    python run.py --database instance/test-data.sqlite3   open the site on the test data

Generated accounts log in with the password "testdata"; the demo accounts keep "demo".
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.data_generator import TEST_DATABASE, TEST_PASSWORD, generate  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", default=str(TEST_DATABASE), help="SQLite file to fill (not the demo database)")
    parser.add_argument("--seed", type=int, default=314, help="random seed; the same seed gives the same data")
    parser.add_argument("--scale", type=float, default=1.0, help="1.0 = at least 100 records per main entity")
    parser.add_argument("--reset", action="store_true", help="delete the file first and generate again")
    args = parser.parse_args()
    if args.scale <= 0:
        parser.error("--scale must be above 0")

    started = time.perf_counter()
    try:
        counts = generate(args.database, seed=args.seed, scale=args.scale, reset=args.reset)
    except ValueError as error:
        parser.error(str(error))
    if not counts.pop("skipped"):
        print(f"Done in {time.perf_counter() - started:.1f} s.")
    width = max(map(len, counts))
    for name, value in counts.items():
        print(f"  {name.ljust(width)}  {value}")
    print(f"Open it with: python run.py --database {args.database}   (generated accounts: password {TEST_PASSWORD})")


if __name__ == "__main__":
    main()
