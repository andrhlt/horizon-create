#!/usr/bin/env python3
"""Compare original Create food consumption and nutrition across player ticks."""
import argparse
import csv
from food_trace import same_f32
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, install_pack, last_command_message, run_command_harness

FOODS = ("sweet_roll", "chocolate_glazed_berries", "honeyed_apple")
SAMPLE = (
    "/data get entity @s Inventory[{Slot:0b}].id",
    "/data get entity @s foodLevel",
    "/data get entity @s foodSaturationLevel",
)


def operations(food, reference):
    for command in ("/gamemode survival @s", "/gamerule naturalRegeneration false",
                    "/effect give @s minecraft:hunger 30 255 true"):
        yield {"op": "cmd", "cmd": command, "record": False}
    # Exhaust the default saturation and reach ten hunger, matching Java's setup.
    yield {"op": "tick", "n": 47}
    for command in ("/effect clear @s minecraft:hunger",
                    f"/item replace entity @s hotbar.0 with create:{food}"):
        yield {"op": "cmd", "cmd": command, "record": False}
    yield {"op": "use_item"}
    for row in reference:
        if row["tick"] != "0":
            yield {"op": "tick", "n": 1}
        for command in SAMPLE:
            yield {"op": "cmd", "cmd": command}


def compare(food, reference, records):
    if len(records) != len(reference) * len(SAMPLE):
        raise AssertionError(f"{food}: got {len(records)} samples")
    for index, row in enumerate(reference):
        start = index * len(SAMPLE)
        item, hunger, saturation = map(last_command_message, records[start:start + len(SAMPLE)])
        if "no entity data" in item.lower() or "found no elements" in item.lower():
            item = "minecraft:air"
        else:
            item = item.split("entity data: ")[-1].strip('"')
        hunger = int(hunger.split("entity data: ")[-1])
        saturation = float(saturation.split("entity data: ")[-1].rstrip("f"))
        if (item != row["item"] or hunger != int(row["hunger"])
                or not same_f32(saturation, row["saturation"])):
            raise AssertionError(f"{food} tick {row['tick']}: Horizon {item, hunger, saturation}; Java {row}")


def run(args):
    with (ROOT / "fixtures/food-use-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    for food in FOODS:
        reference = [row for row in rows if row["food"] == food]
        if [row["tick"] for row in reference] != [str(tick) for tick in range(36)]:
            raise AssertionError(f"{food}: incomplete Java trace")
        with TemporaryDirectory(prefix="hc-food-use-") as scratch:
            game = Path(scratch) / "game"
            install_pack(game, args.pack)
            records = run_command_harness(args, game, f"food-use-{food}", operations(food, reference))
        compare(food, reference, records)
        print(f"{food}: matched item, hunger and saturation over {len(reference)} ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
