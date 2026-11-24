#!/usr/bin/env python3
"""Add the production Millstone block, flour item and wheat recipe to a test pack."""

import argparse
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = {
    "data/create/horizon/block/millstone.json":
        "content/data/create/horizon/block/millstone.json",
    "data/create/horizon/item/wheat_flour.json":
        "content/data/create/horizon/item/wheat_flour.json",
    "data/create/recipe/milling/wheat.json":
        "content/data/create/recipe/milling/wheat.json",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_pack", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    entries = {name: (ROOT / path).read_bytes() for name, path in RESOURCES.items()}
    with zipfile.ZipFile(args.base_pack) as source:
        for info in source.infolist():
            if info.filename not in entries:
                entries[info.filename] = source.read(info.filename)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as result:
        for name, data in sorted(entries.items()):
            result.writestr(name, data)
    print(f"Built {args.output} with production Millstone resources and wheat recipe.")


if __name__ == "__main__":
    main()
