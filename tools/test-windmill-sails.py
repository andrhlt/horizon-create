#!/usr/bin/env python3
"""Replay the original sail materials, dye sequence, and glue-free capture."""

import argparse
import csv
from importlib import import_module
import json
from pathlib import Path
import re
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world

windmill = import_module("test-windmill")
TARGET = (8, 180, 23)
POSITIONS = (TARGET, (8, 181, 23), (8, 182, 23), (8, 180, 24), (8, 180, 25), (8, 179, 23), (9, 180, 23))
MILL = windmill.WINDMILLS[1]


def reference(name):
    with (ROOT / f"fixtures/sail-{name}-java.csv").open() as source:
        return list(csv.DictReader(source))


def verify_materials(control, pack):
    test_at = (11, 180, 23)
    rows = reference("materials")
    with ZipFile(pack) as archive:
        for row in rows:
            identity = row["id"]
            name = identity.removeprefix("create:")
            definition = json.loads(archive.read(f"data/create/horizon/block/{name}.json"))
            expected = (int(row["map_color"]), float(row["hardness"]), float(row["resistance"]))
            properties = definition["properties"]
            actual = tuple(properties[key] for key in ("map_color", "hardness", "explosion_resistance"))
            if actual != expected or not bool(definition["item"]) == (name in ("white_sail", "sail_frame")):
                raise RuntimeError(f"Incorrect declaration for {identity}: {definition}")
            coord = windmill.coords(test_at)
            control.command(f"/setblock {coord} {identity}")
            if not control.command(f"/execute if block {coord} {identity}[facing={row['facing']}]").startswith("Test passed"):
                raise RuntimeError(f"Default state for {identity} differs from Java.")
    return len(rows)


def verify_dye(control):
    rows = reference("dye")
    control.commands((
        "/fill 5 179 21 12 179 39 minecraft:smooth_stone",
        "/tp @s 6.5 180.0 23.5",
        "/gamemode survival",
        *(f"/setblock {windmill.coords(pos)} create:{'sail_frame' if i == 5 else 'white_sail'}"
          f"[facing={'west' if i == 4 else 'east'}]" for i, pos in enumerate(POSITIONS)),
    ))
    for row in rows:
        item = row["held"]
        count = int(row["count"])
        control.command(f"/item replace entity @s hotbar.0 with {item} {count}")
        control.call("wait", 3)
        control.call("select", item)
        control.call("look-at", 8.375, 180.82, 23.69)
        control.call("wait", 3)
        control.call("mouse", "right", "click")
        control.call("wait", 4)
        expected = row["states"].split("|")
        checks = control.commands(f"/execute if block {windmill.coords(pos)} {value}[facing={'west' if i == 4 else 'east'}]"
                                  for i, (pos, value) in enumerate(zip(POSITIONS, expected, strict=True)))
        actual_count = control.call("inventory")["counts"].get(item, 0)
        nbt = control.command("/data get entity @s SelectedItem")
        damage = re.search(r'"minecraft:damage": (\d+)', nbt)
        if any(not reply.startswith("Test passed") for reply in checks) or actual_count != count or (
            int(damage[1]) if damage else 0
        ) != int(row["damage"]):
            actual = [control.call("block", *pos)["state"] for pos in POSITIONS]
            raise RuntimeError(f"Java sail action {row['action']} differs: expected {expected}, Horizon {actual}, held {nbt}.")
    return len(rows)


def verify_join(control):
    x, y, z = MILL
    expected, = reference("join")
    control.commands((
        "/clear @s",
        f"/setblock {windmill.coords(MILL)} create:windmill_bearing[facing=east]",
        f"/setblock {x - 1} {y} {z} create:shaft[axis=x]",
        *(f"/setblock {x + 1} {y} {z + i} create:white_sail[facing=east]" for i in range(8)),
        f"/tp @s {x + 0.5} {float(y)} {z - 2.5}",
    ))
    control.call("wait", 3)
    control.call("look-at", x + 0.5, y + 0.91, z + 0.02)
    control.call("wait", 2)
    control.call("mouse", "right", "click")
    control.call("wait", 2)
    control.step_to(control.clock() + 1)
    nbt = control.command(f"/data get block {windmill.coords(MILL)}")
    if (windmill.number(nbt, "Sails"), windmill.number(nbt, "LastGenerated")) != (
        int(expected["sails"]), float(expected["rpm"])
    ):
        raise RuntimeError(f"The eight unglued sails did not produce Java's attached payload: {nbt}")


def run(args):
    pack = args.pack or ROOT / ".local/create.hmod"
    with fixture_world(args, "Windmill-sails", render=True, pack=pack) as control:
        materials = verify_materials(control, pack)
        actions = verify_dye(control)
        verify_join(control)
    print(f"Matched all {materials} sail definitions, {actions} real dye/shearing actions, and Java's eight-sail capture without glue.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
