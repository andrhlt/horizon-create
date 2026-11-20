#!/usr/bin/env python3
"""Replay focused Hand Crank placement, grip, generator and restart cases."""

import argparse
import csv
from importlib import import_module
from math import isclose
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

crank = import_module("test-hand-crank")
wear = import_module("test-extendo-grip-wear")
multiplayer = import_module("test-multiplayer")
TARGET = " ".join(map(str, crank.CRANK))
COG = "create:brass_encased_cogwheel[axis=x,top_shaft={top},bottom_shaft={bottom}]"
GAUGE = "create:stressometer[facing=up,axis_along_first={first}]"
NEIGHBORS = {
    "encased_east_open": (7, COG.format(top="false", bottom="true")),
    "encased_east_closed": (7, COG.format(top="true", bottom="false")),
    "encased_west_open": (5, COG.format(top="true", bottom="false")),
    "encased_west_closed": (5, COG.format(top="false", bottom="true")),
    "gauge_x": (7, GAUGE.format(first="true")),
    "gauge_z": (7, GAUGE.format(first="false")),
    "gauge_sneak": (7, GAUGE.format(first="true")),
    "axes_conflict": (7, COG.format(top="false", bottom="true")),
}


def reference(name):
    with (ROOT / f"fixtures/hand-crank-{name}-java.csv").open() as source:
        return list(csv.DictReader(source))


def compare(row, actual, context, mismatches):
    for field, got in actual.items():
        expected = row[field]
        if isinstance(got, float):
            matched = isclose(float(expected), got, abs_tol=0.00002, rel_tol=0.0)
        else:
            matched = expected == str(got).lower()
        if not matched:
            mismatches.append(f"{context} {field}: Java {expected}, Horizon {got}")


def click(control, coords, sneaking=False, face=None):
    if sneaking:
        control.call("key", "shift", "down")
        control.call("wait", 3)
    try:
        target = (*coords, face) if face else coords
        control.call("interact", *target)
    finally:
        if sneaking:
            control.call("key", "shift", "up")


def placement(args):
    rows = reference("placement")
    mismatches = []
    with fixture_world(args, "HandCrankShaftFaces", pack=args.pack) as control:
        crank.setup(control)
        control.commands((
            "/tp @s 6.5 101 -7.5",
            f"/setblock {crank.FRONT} minecraft:air",
            f"/setblock {crank.REAR} minecraft:air",
            "/item replace entity @s weapon.mainhand with create:hand_crank 16",
        ))
        for row in rows:
            name = row["case"]
            x, neighbor = NEIGHBORS[name]
            opposite = 12 - x
            control.commands((
                f"/setblock {TARGET} minecraft:air",
                f"/setblock {opposite} 101 -10 minecraft:air",
                f"/setblock {x} 101 -10 {neighbor}",
                f"/setblock {crank.REAR} "
                + ("create:shaft[axis=z]" if name == "axes_conflict" else "minecraft:air"),
            ))
            control.call("wait", 4)
            click(control, (6, 100, -10), sneaking=name == "gauge_sneak", face="up")
            state = control.call("block", *crank.CRANK)["state"]
            want = "create:hand_crank[facing={facing},waterlogged={waterlogged}]".format(**row)
            if state != want:
                mismatches.append(f"{name}: Java {want}, Horizon {state}")
    return len(rows), mismatches


def exhaustion(control):
    status = control.call("lan", "status")
    return next(player["food"][2] for player in status["guests"] if player["name"] == status["host"])


def grip(args):
    rows = reference("grip")
    mismatches = []
    with fixture_world(args, "HandCrankGrip", pack=args.pack) as control:
        crank.setup(control)
        control.command(f"/setblock {crank.REAR} minecraft:stone")
        control.call("lan", "open", "0", "commands", "force")
        for row in rows:
            name = row["case"]
            main = wear.GRIP if name == "main" else "minecraft:air"
            off = wear.GRIP if name == "off" else "minecraft:air"
            control.commands((
                f"/item replace entity @s hotbar.0 with {main}",
                f"/item replace entity @s weapon.offhand with {off}",
            ))
            control.call("key", "1", "tap")
            multiplayer.until("the crank user's held items", lambda:
                ((control.call("inventory")["held"] or {}).get("item")
                 == (wear.GRIP if name == "main" else None))
                and control.call("inventory")["offhand"]["item"]
                == (wear.GRIP if name == "off" else None))
            before = exhaustion(control)
            click(control, crank.CRANK)
            nbt = control.command(f"/data get block {TARGET} InUse")
            actual = {
                "in_use": int(nbt.split()[-1]),
                "exhaustion": exhaustion(control) - before,
                "main_damage": wear.damage(control, "@s", "SelectedItem"),
                "off_damage": wear.damage(control, "@s", "equipment.offhand"),
            }
            control.step_to(control.clock() + 1)
            actual["crank_rpm"] = crank.tag_value(control.command(f"/data get block {TARGET}"), "Speed")
            compare(row, actual, name, mismatches)
            for _ in range(9):
                control.step_to(control.clock() + 1)
    return len(rows), mismatches


def motor(args):
    rows = [row for row in reference("edges-motor")
            if int(row["motor_rpm"]) == args.motor and int(row["tick"]) != 0]
    mismatches = []
    env = {"CREATE_HAND_CRANK_TRACE": ",".join(map(str, crank.CRANK))}
    with fixture_world(args, f"HandCrankMotor{args.motor}", env=env,
                       pack=args.pack) as control:
        crank.setup(control)
        control.commands((
            "/setblock 6 101 -13 create:creative_motor[facing=south]",
            f"/data merge block 6 101 -13 {{ScrollValue:{args.motor}}}",
        ))
        start = control.clock()
        log = control.socket.parent / "ctl.log"
        for row in rows:
            tick = int(row["tick"])
            control.step_to(start + tick)
            block = control.call("block", *crank.CRANK)["block"]
            mounted = block == "create:hand_crank"
            rear = control.command(f"/data get block {crank.REAR}")
            items = control.call("entities", 12, "minecraft:item")["entities"]
            drops = sum(entity["item"]["count"] for entity in items
                        if entity["item"]["item"] == "create:hand_crank")
            actual = {
                "mounted": mounted,
                "shaft_rpm": crank.tag_value(rear, "Speed"),
                "capacity": crank.tag_value(rear, "Capacity"),
                "drops": drops,
                "in_use": 0,
                "crank_rpm": 0.0,
            }
            if mounted:
                samples = crank.trace(log, "TICK", start + tick)
                if len(samples) != 1:
                    raise RuntimeError(f"Expected one crank tick at {start + tick}, got {samples}")
                actual.update(in_use=int(samples[0][0]), crank_rpm=float(samples[0][2]))
            compare(row, actual, f"{args.motor} RPM, tick {tick}", mismatches)
            if tick in (4, 9, 16):
                click(control, crank.CRANK, sneaking=tick == 16)
            if tick == 16:
                # The Java mock player does not pick up the drop.
                control.command("/tp @s 2.5 101 -7.5")
    return len(rows), mismatches


def persistence(args):
    def state(tag):
        match = re.search(r"InUse: (\d+)", tag)
        return (int(match[1]) if match else 0), "Backwards: 1b" in tag

    # Idle crank: its block and unloaded network remain unchanged after reopen.
    with fixture_world(args, "HandCrankIdleReopen") as control:
        crank.setup(control)
        control.call("command", "/save-all")
        control.restart()
        after = control.command(f"/data get block {TARGET}")
        if state(after) != (0, False):
            raise RuntimeError(f"Idle crank changed across restart: {after}")
        rear = control.command(f"/data get block {crank.REAR}")
        if crank.tag_value(rear, "Speed") != 0.0:
            raise RuntimeError(f"Idle crank network started after restart: {rear}")

    # Save during a crank stroke on a compatible 16 RPM source. The crank's
    # ten-tick stroke can naturally finish while a cold client starts; after
    # reopening, the motor must still be connected and resume driving the shaft.
    with fixture_world(args, "HandCrankActiveReopen") as control:
        crank.setup(control)
        control.command("/setblock 6 101 -13 create:creative_motor[facing=south]")
        control.command("/data merge block 6 101 -13 {ScrollValue:16}")
        control.step_to(control.clock() + 1)
        click(control, crank.CRANK)
        before = control.command(f"/data get block {TARGET}")
        if state(before) != (10, False):
            raise RuntimeError(f"Expected an active forward crank before save: {before}")
        control.call("command", "/save-all")
        control.restart()
        after = control.command(f"/data get block {TARGET}")
        remaining, backwards = state(after)
        if not 0 <= remaining <= 10 or backwards:
            raise RuntimeError(f"Crank direction/state changed across restart: {after}")
        for _ in range(11):
            remaining, _ = state(control.command(f"/data get block {TARGET}"))
            if remaining == 0:
                break
            control.step_to(control.clock() + 1)
        motor = control.command("/data get block 6 101 -13")
        if "ScrollValue: 16" not in motor:
            raise RuntimeError(f"Saved motor setting changed across restart: {motor}")
        if control.call("block", 6, 101, -13)["block"] != "create:creative_motor":
            raise RuntimeError("The active setup lost its motor across restart.")
        control.step_to(control.clock() + 1)
        rear = control.command(f"/data get block {crank.REAR}")
        if crank.tag_value(rear, "Speed") != 16.0:
            raise RuntimeError(f"Saved connected motor did not resume driving the shaft: {rear}")
    return 4, []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    scenario = parser.add_mutually_exclusive_group(required=True)
    scenario.add_argument("--placement", action="store_true")
    scenario.add_argument("--grip", action="store_true")
    scenario.add_argument("--motor", type=int, choices=(16, 32))
    scenario.add_argument("--persistence", action="store_true")
    args = parser.parse_args()
    check = (placement if args.placement else grip if args.grip else
             persistence if args.persistence else motor)
    samples, mismatches = check(args)
    if mismatches:
        raise RuntimeError(f"{len(mismatches)} field mismatches across {samples} samples:\n"
                           + "\n".join(mismatches[:20]))
    if check is persistence:
        print("Hand Crank direction and active timer survived a world restart.")
    else:
        print(f"Hand Crank {check.__name__} matched {samples} Java samples.")


if __name__ == "__main__":
    main()
