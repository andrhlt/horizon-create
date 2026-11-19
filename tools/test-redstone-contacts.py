#!/usr/bin/env python3
"""Replay Java's original vertical Gantry moving past three Redstone Contacts."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/contraptions/redstone_contacts.nbt")
BASE = (5, 100, -11)
CARRIAGE = (2, 2, 1)
KEYS = ("height", "contact_1", "contact_2", "contact_3", "diamond_y")


def pos(local):
    return " ".join(str(x + y) for x, y in zip(BASE, local, strict=True))


def sample(control):
    marker, *checks = control.commands((
        "/data get entity @e[type=minecraft:marker,limit=1] Pos[1]",
        *(f"/execute if block {pos((4, height, 1))} create:redstone_contact[powered=true]" for height in (3, 5, 7)),
        *(f"/execute if block {pos((5, height, 1))} minecraft:diamond_block" for height in range(5, 12)),
    ))
    moving = re.search(r"(-?\d+(?:\.\d+)?)d$", marker)
    height = float(moving[1]) - BASE[1] - CARRIAGE[1] if moving else 999.0
    powered = tuple("true" if "Test passed" in match else "false" for match in checks[:3])
    diamond = next((height + 1 for height, value in zip(range(5, 12), checks[3:], strict=True)
                    if "Test passed" in value), 0)
    return (height, *powered, diamond)


def run(args):
    with (ROOT / "fixtures/redstone_contacts-java.csv").open() as data:
        expected = tuple(csv.DictReader(data))
    with fixture_world(args, "Redstone-contacts", STRUCTURE, render=args.visual) as control:
        control.commands((
            f"/place template create:{STRUCTURE.with_suffix('')} {' '.join(map(str, BASE))}",
            f"/setblock {pos((1, 2, 2))} minecraft:lever[face=floor,facing=west,powered=false]",
        ))
        start = control.clock()
        differences = []
        with (ROOT / ".local/redstone_contacts-horizon.csv").open("w") as out:
            writer = csv.writer(out)
            writer.writerow(("tick", *KEYS))
            for row in expected:
                tick = int(row["tick"])
                if tick:
                    control.step_to(start + tick)
                found = sample(control)
                writer.writerow((tick, *found))
                want = (float(row["height"]), *(row[key] for key in KEYS[1:4]), int(row["diamond_y"]))
                if abs(found[0] - want[0]) > 1e-6 or found[1:] != want[1:]:
                    detail = f"Tick {tick}: Horizon {found}, Java {want}"
                    if not args.diagnostics:
                        raise RuntimeError(detail)
                    differences.append(detail)
                if args.visual and tick == 29:
                    control.commands(("/time set noon", "/tp @s 15 107 -5"))
                    control.call("wait", 3)
                    control.call("look-at", 8, 104, -10)
                    control.call("key", "f1", "tap")
                    control.call("wait", 4)
                    control.call("screenshot", ROOT / ".local/redstone-contacts.png")
                    control.call("key", "f1", "tap")
            if differences:
                raise RuntimeError("\n".join(differences[:8]))
    print(f"Vertical Gantry travel, all three contacts, and the piston column matched Java for all {len(expected)} ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    run(parser.parse_args())
