#!/usr/bin/env python3
"""Compare the axe and pickaxe tag membership of all six Java cogwheels."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import install_pack, last_command_message, run_command_harness


BLOCKS = (
    "cogwheel", "large_cogwheel",
    "andesite_encased_cogwheel", "brass_encased_cogwheel",
    "andesite_encased_large_cogwheel", "brass_encased_large_cogwheel",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=lambda path: Path(path).resolve(strict=True))
    args = parser.parse_args()

    operations = [
        {"op": "cmd", "cmd": "/tp @s 8 103 4", "record": False},
        {"op": "settle"},
    ]
    checks = {}
    for index, name in enumerate(BLOCKS):
        pos = f"{3 + index * 2} 101 4"
        block = f"create:{name}"
        operations.append({"op": "cmd", "cmd": f"/setblock {pos} {block}", "record": False})
        for predicate in (block, "#minecraft:mineable/axe", "#minecraft:mineable/pickaxe"):
            query = f"/execute if block {pos} {predicate}"
            checks[query] = f"{block} at {pos}, checking {predicate}"
            operations.append({"op": "cmd", "cmd": query})

    with TemporaryDirectory(prefix="hc-cogwheel-mining-") as scratch:
        game = Path(scratch) / "game"
        install_pack(game, args.pack)
        records = run_command_harness(args, game, "CogwheelMiningTags", operations)
    replies = {record["cmd"]: last_command_message(record) for record in records}
    failures = [f"{label}: {replies.get(query, 'no reply')}"
                for query, label in checks.items() if replies.get(query) != "Test passed"]
    if failures:
        raise RuntimeError("Cogwheel tag checks failed:\n" + "\n".join(failures))
    print(f"All {len(BLOCKS)} cogwheel variants matched both Java mining tags.")


if __name__ == "__main__":
    main()
