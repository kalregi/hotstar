"""Resolve and import the reviewed 1990s rock/alternative expansion."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import import_christmas as importer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolve", action="store_true")
    parser.add_argument("--merge", action="store_true")
    args = parser.parse_args()
    if not args.resolve and not args.merge:
        parser.error("Choose --resolve or --merge")
    importer.SOURCE = ROOT / "rock_90s_catalog.csv"
    importer.RESULT = ROOT / "reports/rock_90s_spotify_matches.csv"
    rows, _ = importer.read_rows(importer.SOURCE)
    if not all(1990 <= int(row["year"]) <= 1999 and row["decade"] == "1990s" for row in rows):
        raise ValueError("Only 1990s recordings belong in this expansion")
    if args.resolve and not importer.resolve():
        raise SystemExit(1)
    if args.merge:
        importer.merge(expected_count=60, tag="Rock")


if __name__ == "__main__":
    main()
