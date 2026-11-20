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
        # Java's hasValidContact accepts either contact block when the faces oppose.
        # Keep these static cases away from the original moving Gantry fixture.
        control.commands((
            "/setblock 22 100 30 minecraft:stone",
            "/item replace entity @s hotbar.0 with create:redstone_contact 1",
            "/tp @s 25.5 100 30.5",
        ))
        control.call("wait", 3)
        control.call("look-at", 22.5, 100.5, 30.5)
        control.call("select", "create:redstone_contact")
        control.call("interact", 22, 100, 30, "east")
        placed = control.call("block", 23, 100, 30)["state"]
        if not placed.startswith("create:redstone_contact[") or "facing=east" not in placed:
            raise RuntimeError(f"Face placement did not use the Java look-direction default: {placed}")
        static = (
            ("30 100 30", "31 100 30", "create:redstone_contact[facing=east,powered=false]",
             "create:redstone_contact[facing=west,powered=false]", True),
            ("34 100 30", "35 100 30", "create:redstone_contact[facing=east,powered=false]",
             "create:redstone_contact[facing=north,powered=false]", False),
            ("38 100 30", "39 100 30", "create:redstone_contact[facing=east,powered=false]",
             "create:elevator_contact[facing=west,powered=false,calling=false,powering=false]", True),
        )
        for left, right, left_state, right_state, _ in static:
            control.command(f"/setblock {left} {left_state}")
            control.command(f"/setblock {right} {right_state}")
        checks = tuple(
            control.commands(tuple(
                f"/execute if block {left} create:redstone_contact[powered={str(powered).lower()}]"
                for left, _, _, _, powered in static
            ))
        )
        if any("Test passed" not in result for result in checks):
            raise RuntimeError(f"Static Redstone Contact matching failed: {checks}")
        control.command("/save-all flush")
        control.restart()
        checks = tuple(
            control.commands(tuple(
                f"/execute if block {left} create:redstone_contact[powered={str(powered).lower()}]"
                for left, _, _, _, powered in static
            ))
        )
        if any("Test passed" not in result for result in checks):
            raise RuntimeError(f"Static contact pairs changed across idle save/reopen: {checks}")
        control.command("/setblock 31 100 30 air")
        control.command("/setblock 39 100 30 air")
        control.step_to(control.clock() + 1)
        checks = control.commands((
            "/execute if block 30 100 30 create:redstone_contact[powered=false]",
            "/execute if block 38 100 30 create:redstone_contact[powered=false]",
        ))
        if any("Test passed" not in result for result in checks):
            raise RuntimeError(f"Static contacts failed to deactivate after separation: {checks}")
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
    active_reopen_tick = 0
    with fixture_world(args, "Redstone-contact-active-reopen", STRUCTURE) as control:
        control.commands((
            f"/place template create:{STRUCTURE.with_suffix('')} {' '.join(map(str, BASE))}",
            f"/setblock {pos((1, 2, 2))} minecraft:lever[face=floor,facing=west,powered=false]",
        ))
        start = control.clock()
        for tick in range(1, 13):
            control.step_to(start + tick)
        control.command("/save-all flush")
        control.restart()
        reopened_tick = control.clock() - start
        active_reopen_tick = reopened_tick
        row = next((row for row in expected if int(row["tick"]) == reopened_tick), None)
        if row is None:
            raise RuntimeError(f"Active reopen advanced outside the Java trace at tick {reopened_tick}.")
        reopened = sample(control)
        want = (float(row["height"]), *(row[key] for key in KEYS[1:4]), int(row["diamond_y"]))
        if abs(reopened[0] - want[0]) > 1e-6 or reopened[1:] != want[1:]:
            raise RuntimeError(f"Active Gantry/contact reopen at tick {reopened_tick}: {reopened} != {want}")
        if reopened_tick <= 12:
            raise RuntimeError("The active Gantry/contact setup did not resume after reopening.")
    print(f"Static matching, idle reopen, separation and vertical Gantry travel passed; the original Java moving-contact trace and piston column matched all {len(expected)} ticks, and active save/reopen matched Java at trace tick {active_reopen_tick}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    run(parser.parse_args())
