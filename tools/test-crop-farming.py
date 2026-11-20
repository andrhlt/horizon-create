#!/usr/bin/env python3
"""Replay the original Java Create crop farming fixture."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

ORIGIN = (3, 96, -12)
TEMPLATE = Path("gametest/contraptions/crop_farming.nbt")
NUM = r"(-?[0-9.Ee+\-]+)"
VECTOR = rf"\[{NUM}d, {NUM}d, {NUM}d\]"
IDS = re.compile(r'\bid: "([^"]+)"')
CROP_AGE = re.compile(r"\bage=(\d+)\b")
ITEM_COUNT = re.compile(r"Count: (\d+)b")


def sample(control):
    x, y, z = ORIGIN
    marker, cart, output = control.commands((
        "/data get entity @e[type=minecraft:marker,tag=create_cart_payload,limit=1] Pos",
        "/data get entity @e[type=minecraft:chest_minecart,limit=1]",
        f"/data get block {x+1} {y+2} {z+12} Items",
    ))
    moving = re.search(VECTOR, marker)
    contraption = (":".join(f"{float(value)-base:.9f}" for value, base in zip(moving.groups(), ORIGIN, strict=True))
                   + ":0.000000") if moving else ""
    position = re.search(r"\bPos: " + VECTOR, cart)
    motion = re.search(r"\bMotion: " + VECTOR, cart)
    cart_trace = ""
    if position and motion:
        cart_trace = ":".join(
            [f"{float(value)-base:.9f}" for value, base in zip(position.groups(), ORIGIN, strict=True)]
            + [f"{float(motion[3]):.9f}"])
    world = control.call("blocks", x + 1, y + 2, z + 5, x + 3, y + 2, z + 11)
    blocks = {(px, pz): state for px, _, pz, state in world["blocks"]}
    crops = []
    for dx in range(1, 4):
        for dz in range(5, 12):
            state = blocks.get((x + dx, z + dz), "minecraft:air")
            name = state.split("[", 1)[0]
            age = CROP_AGE.search(state)
            crops.append(f"{name}={age[1]}" if age else name)
    return [contraption, "|".join(crops), "|".join(sorted(set(IDS.findall(output)))), cart_trace]


def run(args):
    with (ROOT / "fixtures/crop_farming-java.csv").open() as source:
        reader = csv.reader(source)
        header = next(reader)
        header = header[:2] + header[3:]
        expected = [row[:2] + row[3:] for row in reader][:args.ticks]
    actual = []
    with fixture_world(args, "crop_farming", TEMPLATE) as control:
        control.command("/gamerule random_tick_speed 0")
        rule = control.command("/gamerule random_tick_speed")
        if not rule.endswith(" 0"):
            raise RuntimeError(f"Expected random crop growth to be disabled. Got {rule!r}.")
        while control.clock() % 20 != int(expected[0][1]):
            control.step_to(control.clock()+1)
        x, y, z = ORIGIN
        control.command(f"/place template create:{TEMPLATE.with_suffix('')} {x} {y} {z}")
        control.command(f"/tp @s {x+4.5} {y+3} {z}")
        control.call("interact", x+4, y+2, z+1, "up")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start+tick)
            actual.append([str(tick), str((start+tick) % 20), *sample(control)])
        before_reload = inventory_counts(control)
        control.restart()
        after_reload = inventory_counts(control)
        if after_reload != before_reload:
            raise RuntimeError(f"Harvester output changed across save/reopen: {before_reload} -> {after_reload}")
    output = ROOT / ".local/crop_farming-horizon.csv"
    with output.open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(int(want[0]), {key: (a,b) for key,a,b in zip(header,want,got,strict=True) if a != b})
                   for want, got in zip(expected, actual, strict=True) if want != got]
    if differences:
        raise SystemExit(f"crop_farming differed on {len(differences)} ticks. First differences (Java, Horizon) {differences[:4]}. See {output}")
    check_crop_age_boundary(args, expected[0][1])
    print(f"crop_farming matched all {len(actual)} Java ticks. Immature-crop rejection and mature harvesting passed.")


def inventory_counts(control):
    """Return chest-minecart stack counts for loss/duplication checks."""
    dump = control.command("/data get entity @e[type=minecraft:chest_minecart,limit=1] Items")
    return sorted(int(value) for value in ITEM_COUNT.findall(dump))


def check_crop_age_boundary(args, first_world_time):
    with fixture_world(args, "crop_farming_age_boundary", TEMPLATE) as control:
        control.command("/gamerule random_tick_speed 0")
        while control.clock() % 20 != int(first_world_time):
            control.step_to(control.clock() + 1)
        x, y, z = ORIGIN
        control.command(f"/place template create:{TEMPLATE.with_suffix('')} {x} {y} {z}")
        control.commands((
            f"/setblock {x+1} {y+2} {z+5} minecraft:carrots[age=0]",
            f"/setblock {x+2} {y+2} {z+5} minecraft:wheat[age=7]",
        ))
        control.command(f"/tp @s {x+4.5} {y+3} {z}")
        control.call("interact", x+4, y+2, z+1, "up")
        start = control.clock()
        for tick in range(1, 12):
            control.step_to(start + tick)
        movement = control.command("/data get entity @e[type=minecraft:marker,tag=create_cart_payload,limit=1] Pos")
        if not re.search(VECTOR, movement):
            raise RuntimeError("Crop-age fixture never assembled a moving harvester")
        immature = control.call("block", x+1, y+2, z+5)["state"]
        mature = control.call("block", x+2, y+2, z+5)["state"]
        if immature != "minecraft:carrots[age=0]":
            raise RuntimeError(f"Harvester changed an immature crop: {immature}")
        if mature != "minecraft:wheat[age=0]":
            raise RuntimeError(f"Harvester did not harvest and replant the mature crop: {mature}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--ticks", type=int)
    args = parser.parse_args()
    if args.ticks is not None and args.ticks < 1:
        parser.error("--ticks must be positive")
    run(args)
