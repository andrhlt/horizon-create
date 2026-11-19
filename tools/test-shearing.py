#!/usr/bin/env python3
"""Replay the original Create GameTest for wool from a sheep."""
import argparse
import csv
from pathlib import Path

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/misc/shearing.nbt")
SHEARED = '/execute if entity @e[type=minecraft:sheep,nbt={Sheared:1b}]'
WOOL = ('/execute positioned 3 95 -12 if entity '
        '@e[type=minecraft:item,dx=4,dy=4,dz=4,nbt={Item:{id:"minecraft:white_wool"}}]')


def present(control, command):
    reply = control.command(command)
    if not reply.startswith(("Test passed", "Test failed")):
        raise RuntimeError(f"Could not observe shearing: {reply}")
    return reply.startswith("Test passed")


def run(args):
    with (ROOT / "fixtures/shearing-java.csv").open() as source:
        rows = tuple(csv.DictReader(source))
    with fixture_world(args, "Shearing", STRUCTURE, render=True) as control:
        control.commands((
            "/place template create:gametest/misc/shearing 3 96 -12",
            "/tp @s 5.5 98.25 -7.7",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with minecraft:shears",
        ))
        control.call("select", "minecraft:shears")
        for _ in range(4):
            if 'id: "minecraft:shears"' in control.command("/data get entity @s SelectedItem"):
                break
            control.call("wait", 1)
        else:
            raise RuntimeError("The server did not equip the shears")
        sheep = control.call("entities", 6, "minecraft:sheep")["entities"]
        if len(sheep) != 1:
            raise RuntimeError(f"Expected one sheep from the original structure. {sheep}")
        if present(control, SHEARED) or present(control, WOOL):
            raise RuntimeError("The sheep was already sheared")
        start = control.clock()
        control.call("interact-entity", sheep[0]["id"])
        # The control command completes on the client. Keep the player at
        # the sheep until the server returns both effects of the click.
        for _ in range(8):
            if present(control, SHEARED) and present(control, WOOL):
                break
            control.call("wait", 1)
        else:
            raise RuntimeError("The click did not produce a sheared sheep and white wool at the current tick")
        if control.clock() != start:
            raise RuntimeError("The world advanced during the shearing click")
        control.command("/tp @s 2.5 97 -7.5")
        for row in rows:
            tick = int(row["tick"])
            if tick:
                control.step_to(start + tick)
            expected = row["sheared"] == "true", row["wool_present"] == "true"
            actual = present(control, SHEARED), present(control, WOOL)
            if actual != expected:
                raise RuntimeError(f"Shearing differed at tick {tick}. Java {expected}, Horizon {actual}")
    print(f"Sheep state and presence of white wool matched all {len(rows)} Java ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
