#!/usr/bin/env python3
"""Drive real player target selection and placement for the Weighted Ejector."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
EJECTOR = "create:weighted_ejector"
STONE = "minecraft:smooth_stone"


def pos_text(pos):
    return " ".join(map(str, pos))


def player_pad(control, at, offset):
    x, y, z = at
    dx, dz = offset
    px, pz = x + dx, z + dz
    control.command(f"/setblock {px} {y - 1} {pz} {STONE}")
    return px + .5, y, pz + .5


def run(args):
    with args.reference.open() as source:
        expected = list(csv.DictReader(source))
    for verify, case in ((args.switch_slot, 8), (args.deselect, 9)):
        if verify:
            expected.append({
                "case": str(case), "dx": "4", "dy": "0", "dz": "0",
                "facing": "north", "horizontal": "1", "vertical": "0",
            })
    actual = []
    clear = []
    with ExitStack() as stack:
        control = stack.enter_context(fixture_world(
            args, "EjectorTargetPlacementLAN" if args.multiplayer else "EjectorTargetPlacement",
            render=True, pack=args.pack,
        ))
        actor, target_name = control, "@s"
        if args.multiplayer:
            port = control.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejector-target-")))
            target_name = "EjectorTagGuest"
            actor = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", target_name,
                scenario="ejector-target", render=True, pack=args.pack,
            ))
            multiplayer.until("guest in the target fixture", lambda: any(
                entry["name"] == target_name and entry["placed"]
                for entry in control.call("lan", "status")["guests"]
            ))
        control.commands((f"/gamemode survival {target_name}", f"/give {target_name} {EJECTOR} 32"))
        multiplayer.until("selected Weighted Ejector in hotbar", lambda: multiplayer.count(actor, EJECTOR) == 32)
        actor.call("select", EJECTOR)
        for case in expected:
            i = int(case["case"])
            x, y, z = 5, 105, -15 if i == 9 else -11 - 9 * i
            dx, dy, dz = (int(case[name]) for name in ("dx", "dy", "dz"))
            mark = (x + dx, y + dy, z + dz)
            tx, ty, tz = mark
            here = (x, y, z)
            control.command(f"/tp {target_name} {tx + 1.5} {ty} {tz + .5}")
            control.step_to(control.clock() + 1)
            control.command(f"/setblock {pos_text(mark)} {STONE}")
            player_pad(control, mark, (1, 0))
            control.command(f"/tp {target_name} {tx + 1.5} {ty} {tz + .5}")
            control.step_to(control.clock() + 1)
            actor.call("key", "shift", "down")
            control.step_to(control.clock() + 1)
            try:
                actor.call("interact", *mark, "up")
                if i == 9:
                    actor.call("look-at", tx + .5, ty + .5, tz + .5)
                    actor.call("key", "shift", "down")
                    actor.call("wait", 5)
                    actor.call("mouse", "left", "down")
                    try:
                        actor.call("wait", 5)
                        control.step_to(control.clock() + 1)
                    finally:
                        actor.call("mouse", "left", "up")
            finally:
                actor.call("key", "shift", "up")
            if i == 9:
                actor.call("wait", 5)
                if control.call("block", *mark)["block"] != STONE:
                    raise RuntimeError("Crouch-left-click broke the selected target.")
            control.step_to(control.clock() + 1)
            above = (tx, ty + 1, tz)
            unexpectedly_placed = control.call("block", *above)["block"] == EJECTOR
            clear.append(not unexpectedly_placed)
            if unexpectedly_placed:
                control.command(f"/setblock {pos_text(above)} minecraft:air")
            if i == 8:
                actor.call("select", 9)
                control.step_to(control.clock() + 1)
                selected = f"/data get entity {target_name} SelectedItemSlot"
                multiplayer.until("the empty hotbar slot is selected",
                                  lambda: control.command(selected).endswith(" 8"))
                actor.call("select", 1)
                control.step_to(control.clock() + 1)
                multiplayer.until("the Ejector hotbar slot is selected",
                                  lambda: control.command(selected).endswith(" 0"))

            control.command(f"/tp {target_name} {x + .5} {y} {z - 1.5}")
            control.step_to(control.clock() + 1)
            player_pad(control, here, (0, -2))
            support = (x, y - 1, z)
            control.command(f"/setblock {pos_text(support)} {STONE}")
            control.command(f"/tp {target_name} {x + .5} {y} {z - 1.5}")
            control.step_to(control.clock() + 1)
            actor.call("look-at", x + .5, y + 1.62, z + 2.5)
            control.step_to(control.clock() + 1)
            actor.call("interact", *support, "up")
            multiplayer.until("placed Weighted Ejector", lambda: control.call("block", *here)["block"] == EJECTOR)
            if actor is not control:
                multiplayer.until("guest sees Weighted Ejector", lambda: actor.call("block", *here)["block"] == EJECTOR)
            block = control.call("block", *here)
            facing = re.search(r"\bfacing=(east|north|south|west)\b", block["state"])
            hr, vt = control.commands((
                f"/data get block {pos_text(here)} HorizontalDistance",
                f"/data get block {pos_text(here)} VerticalDistance",
            ))
            horizontal = re.search(r"(-?\d+)$", hr)
            vertical = re.search(r"(-?\d+)$", vt)
            actual.append((str(i), facing[1], horizontal[1] if horizontal else "1", vertical[1] if vertical else "0"))
    want = [(line["case"], line["facing"], line["horizontal"], line["vertical"]) for line in expected]
    if args.trace:
        with args.trace.open("w") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(("case", "facing", "horizontal", "vertical", "selection_did_not_place"))
            writer.writerows((*row, kept) for row, kept in zip(actual, clear, strict=True))
    if actual != want or not all(clear):
        raise RuntimeError(f"Ejector target placements differ: {list(zip(want, actual, clear, strict=True))}")
    print("The Weighted Ejector matched eight Java target selection and placement cases.")
    if args.switch_slot:
        print("Switching hotbar slots cleared the selected target.")
    if args.deselect:
        print("Crouch-left-click cleared the selected target without breaking it.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/weighted-ejector-target-java.csv")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    parser.add_argument("--switch-slot", action="store_true")
    parser.add_argument("--deselect", action="store_true")
    run(parser.parse_args())
