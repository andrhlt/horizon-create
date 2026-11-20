#!/usr/bin/env python3
"""Compare Analog Lever clicks, debounce and wire propagation with Java Create."""

import argparse
import csv
from pathlib import Path
import re
from runpy import run_path

from fixture_world import ROOT, fixture_world

LEVER = (8, 180, 8)
WEAK_WIRE = (9, 180, 8)
STRONG_WIRE = (8, 179, 9)
FIELDS = ("state", "timer", "weak_wire", "strong_wire")
RAISE = {3, 9, *range(29, 46)}
LOWER = set(range(62, 80))


def coords(pos):
    return " ".join(map(str, pos))


def setup(control):
    setup_commands = (
        "/setblock 8 179 8 minecraft:smooth_stone",
        "/setblock 9 179 8 minecraft:smooth_stone",
        "/setblock 8 178 9 minecraft:smooth_stone",
        "/setblock 8 179 10 minecraft:smooth_stone",
        f"/setblock {coords(LEVER)} create:analog_lever[face=floor,facing=north]",
        f"/setblock {coords(WEAK_WIRE)} minecraft:redstone_wire",
        f"/setblock {coords(STRONG_WIRE)} minecraft:redstone_wire",
        "/tp @s 8.5 180 10.5",
    )
    for command, reply in zip(setup_commands, control.commands(setup_commands), strict=True):
        if command.startswith("/setblock") and "Changed the block" not in reply:
            raise RuntimeError(f"Fixture setup failed for {command}: {reply}")
    control.call("look-at", "8.5", "180.16", "8.5")
    control.call("wait", 3)


def read_int(value, pattern, description):
    match = re.search(pattern, value)
    if match is None:
        raise RuntimeError(f"Could not sample {description}: {value}")
    return int(match[1])


def wire_powers(control):
    wires = (control.call("block", *pos)["state"] for pos in (WEAK_WIRE, STRONG_WIRE))
    return tuple(read_int(value, r"power=(\d+)", field) for value, field in zip(wires, FIELDS[2:], strict=True))


def sample(control):
    tags = control.commands(f"/data get block {coords(LEVER)} {tag}" for tag in ("State", "ChangeTimer"))
    return (
        *(read_int(value, r"(\d+)$", field) for value, field in zip(tags, FIELDS[:2], strict=True)),
        *wire_powers(control),
    )


def advance(control, ticks):
    """Advance a frozen fixture by one server tick at a time."""
    for _ in range(ticks):
        control.step_to(control.clock() + 1)


def run(args):
    with (ROOT / "fixtures/analog-lever-java.csv").open() as data:
        expected = tuple(csv.DictReader(data))
    with fixture_world(args, "Analog-lever", render=args.visual, pack=args.pack) as control:
        setup(control)
        if args.visual:
            control.call("key", "f1", "tap")
        control.step_to(control.clock() + 1)
        start = control.clock()
        differences = []
        with (ROOT / ".local/analog-lever-horizon.csv").open("w") as out:
            writer = csv.writer(out)
            writer.writerow(("tick", *FIELDS))
            for row in expected:
                tick = int(row["tick"])
                if tick:
                    control.step_to(start + tick)
                found = sample(control)
                writer.writerow((tick, *found))
                wanted = tuple(int(row[field]) for field in FIELDS)
                if wanted != found:
                    difference = f"Tick {tick}: Horizon {found}, Java {wanted} [{', '.join(FIELDS)}]"
                    if not args.diagnostics:
                        raise RuntimeError(difference)
                    differences.append(difference)
                if args.visual and tick in (0, 61):
                    control.call("screenshot", ROOT / f".local/analog-lever-{tick:02}.png")
                if tick == min(LOWER) - 2:
                    control.call("key", "shift", "down")
                    control.call("wait", 2)
                    control.call("look-at", "8.5", "180.17", "8.5")
                if tick in RAISE:
                    control.call("interact", *LEVER)
                elif tick in LOWER:
                    control.call("mouse", "right", "click")
                    control.call("wait", 3)
                if tick == max(LOWER) + 1:
                    control.call("key", "shift", "up")
        if differences:
            raise RuntimeError("\n".join(differences[:10]))
    print(f"Analog Lever value, debounce timer and both circuits matched all {len(expected)} Java ticks.")


def run_removal(args):
    path = ROOT / "fixtures/analog-lever-removal-java.csv"
    with path.open() as data:
        expected = {int(tick): (int(weak), int(strong)) for tick, weak, strong in list(csv.reader(data))[1:]}
    scenario = "Analog-lever-destruction" if args.destroy else "Analog-lever-replacement"
    with fixture_world(args, scenario, pack=args.pack) as control:
        setup(control)
        control.step_to(control.clock() + 1)
        start = control.clock()
        differences = []
        with (ROOT / f".local/{scenario.lower()}-horizon.csv").open("w") as out:
            writer = csv.writer(out)
            writer.writerow(("tick", *FIELDS[2:]))
            for tick in range(1, max(expected) + 1):
                control.step_to(start + tick)
                if tick == 3:
                    control.call("interact", *LEVER)
                if tick == 20:
                    suffix = " destroy" if args.destroy else ""
                    reply = control.command(f"/setblock {coords(LEVER)} minecraft:air{suffix}")
                    if "Changed the block" not in reply:
                        raise RuntimeError(f"Could not remove the powered lever: {reply}")
                if tick in expected:
                    control.call("wait", 2)
                    observed = wire_powers(control)
                    writer.writerow((tick, *observed))
                    if observed != expected[tick]:
                        differences.append(f"Tick {tick}: Horizon {observed}, Java {expected[tick]}")
        if differences:
            raise RuntimeError("\n".join(differences))
    print(f"Removing the powered Analog Lever matched both Java wire traces for {len(expected)} ticks.")


def run_crafting(args):
    craft = run_path(ROOT / "tools/test-survival-crafting.py")["craft"]
    with fixture_world(args, "Analog-lever-crafting", render=True, pack=args.pack) as control:
        setup(control)
        control.commands((
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with minecraft:stick",
            "/item replace entity @s hotbar.1 with create:andesite_casing",
            f"/setblock {coords(LEVER)} minecraft:air",
        ))
        control.call("open-inventory")
        for source, grid in ((0, 100), (1, 102)):
            control.call("click-slot", source)
            control.call("click-slot", grid)
        craft(control, "create:analog_lever", 1)
        control.call("close")
        control.call("select", "create:analog_lever")
        control.call("interact", 8, 179, 8, "up")
        control.call("wait", 3)
        state = control.call("block", *LEVER)["state"]
        if not state.startswith("create:analog_lever[face=floor"):
            raise RuntimeError(f"Placed lever did not attach to the floor: {state}")
        for tool in ("axe", "pickaxe"):
            reply = control.command(f"/execute if block {coords(LEVER)} #minecraft:mineable/{tool}")
            if "Test passed" not in reply:
                raise RuntimeError(f"The lever is missing its Java {tool} mining tag: {reply}")
    print("Survival crafting made and placed an Analog Lever with both Java mining tags.")


def run_reopen(args):
    """Verify the durable lever value and connected output across a restart."""
    with fixture_world(args, "Analog-lever-reopen", pack=args.pack) as control:
        setup(control)
        for _ in range(7):
            control.call("interact", *LEVER)
            advance(control, 16)
        before = sample(control)
        if before[:2] != (7, 0) or before[2:] != (7, 7):
            raise RuntimeError(f"Unexpected pre-save Analog Lever state: {before}")
        saved_clock = control.clock()
        control.call("save")
        control.env["HORIZON_STILL"] = "1"
        control.restart()
        after = sample(control)
        if after != before:
            raise RuntimeError(f"Analog Lever changed across reopen: before={before}, after={after}")
        control.call("look-at", "8.5", "180.16", "8.5")
        control.call("key", "shift", "down")
        control.call("interact", *LEVER)
        control.call("key", "shift", "up")
        advance(control, 16)
        lowered = sample(control)
        if lowered[:2] != (6, 0) or lowered[2:] != (6, 6):
            raise RuntimeError(f"Reopened Analog Lever did not resume operation: {lowered}")
    print("Analog Lever value and both connected redstone outputs survived save/reopen and resumed operation.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    scenario = parser.add_mutually_exclusive_group()
    scenario.add_argument("--removal", action="store_const", const=run_removal, dest="run", default=run)
    scenario.add_argument("--craft", action="store_const", const=run_crafting, dest="run")
    scenario.add_argument("--reopen", action="store_const", const=run_reopen, dest="run")
    parser.add_argument("--destroy", action="store_true")
    args = parser.parse_args()
    args.run(args)
