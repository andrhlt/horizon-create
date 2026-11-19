#!/usr/bin/env python3
"""Replay the original Java Create elevator and seated cow fixture."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

ORIGIN = (3, 96, -12)
TEMPLATE = Path("gametest/contraptions/elevator.nbt")
PRIMARY = (5, 11, 3)
MIRROR = (5, 11, 1)
BOTTOM = (2, 2, 2)
TOP = (2, 11, 2)
LEVER = (1, 10, 2)
BOTTOM_LEVER = (1, 1, 2)
COW = (4.5, 3.0, 2.5)
CART = "@e[type=minecraft:marker,tag=create_elevator_cabin,limit=1]"
NUMBER = r"(-?[0-9.eE+\-]+)"
BELT = re.compile(rf"\bBelt(From|To): {NUMBER}d")
POSITION = re.compile(rf"\[{NUMBER}d, {NUMBER}d, {NUMBER}d\]")


def at(local):
    return tuple(origin + coordinate for origin, coordinate in zip(ORIGIN, local, strict=True))


def as_argument(local):
    return " ".join(map(str, at(local)))


def sample(control):
    data, cow, cabin = control.commands((
        f"/data get block {as_argument(MIRROR)}",
        "/data get entity @e[type=minecraft:cow,limit=1] Pos",
        f"/data get entity {CART} Pos",
    ))
    positions = []
    for response, digits in ((cabin, 9), (cow, 6)):
        pos = POSITION.search(response)
        positions.append(f"{float(pos[2]) - ORIGIN[1]:.{digits}f}" if pos else "")
    states = []
    for pos, key in ((BOTTOM, "lit"), (TOP, "lit"), (LEVER, "powered")):
        block = control.call("block", *at(pos))["state"]
        states.append(str(f"{key}=true" in block).lower())
    return [*states, str("MirrorParent:" in data).lower(), *positions]


def check_belts(control, previous, current):
    if not current:
        return
    start = PRIMARY[1] - 1
    expected = (start - float(previous or current), start - float(current))
    for pulley in (PRIMARY, MIRROR):
        reply = control.command(f"/data get block {as_argument(pulley)}")
        values = {key: float(value) for key, value in BELT.findall(reply)}
        if ("BeltRunning: 1b" not in reply or
                any(abs(values.get(key, float("inf")) - value) > 1e-8
                    for key, value in zip(("From", "To"), expected, strict=True))):
            raise RuntimeError(f"Pulley {pulley} expected belt offsets {expected}. Got {reply}.")


def run(args):
    with (ROOT / "fixtures/elevator-java.csv").open() as source:
        reader = csv.reader(source)
        columns = next(reader)
        expected = [row[:2] + row[3:] for row in reader][:args.ticks]
    actual = {}
    resumed = 0
    with fixture_world(args, "elevator", TEMPLATE, render=args.visual, pack=args.pack) as control:
        control.command("/gamerule random_tick_speed 0")
        while control.clock() % 20 != int(expected[0][1]):
            control.step_to(control.clock() + 1)
        control.command(f"/place template create:{TEMPLATE.with_suffix('')} {as_argument((0, 0, 0))}")
        start = control.clock()
        reference_start = start
        for tick in range(len(expected)):
            if tick < resumed:
                continue
            if tick > resumed:
                control.step_to(start + tick)
            if tick == 1:
                control.command(f"/summon minecraft:cow {as_argument(COW)}")
            actual[tick] = [str(tick), str((reference_start + tick) % 20), *sample(control)]
            if args.visual:
                previous = expected[tick - 1][-2] if tick else ""
                check_belts(control, previous, expected[tick][-2])
                if tick in (35, 59):
                    control.call("tp", *at((17.5, 6.5, 2.5)))
                    control.call("look-at", *at((5.5, 6.0, 2.5)))
                    control.call("key", "f1", "tap")
                    control.call("wait", 3)
                    control.call("screenshot", ROOT / f".local/elevator-belt-{tick}.png")
                    control.call("key", "f1", "tap")

            if tick == 15 and not args.baseline:
                control.call("tp", *at((7.5, 11.0, 4.5)))
                if args.visual:
                    control.call("wait", 3)
                    control.call("look-at-block", *at(PRIMARY))
                control.call("interact", *at(PRIMARY))
                queued = control.command(f"/data get block {as_argument(PRIMARY)} Clicked")
                if not queued.endswith("1b"):
                    raise RuntimeError(f"The player's pulley click did not queue assembly. {queued}")
            if tick == 21:
                control.call("tp", *at((0.5, 10.0, 4.0)))
                if args.visual:
                    control.call("wait", 3)
                    control.call("look-at-block", *at(LEVER))
                control.call("interact", *at(LEVER))
            if tick == args.reload_at:
                control.restart()
                clock = control.clock()
                restored = sample(control)
                # A boot tick may advance the world clock before the pulley chunk ticks.
                # Use the restored state once to locate the cabin in the Java trip.
                last = min(clock - start, len(expected) - 4)
                times = [i for i in range(tick, last + 1) if expected[i][2:] == restored]
                if len(times) != 1:
                    raise RuntimeError(f"Reopened elevator state did not match the Java trip: {restored}.")
                resumed = times[0]
                start = clock - resumed
                print(f"Reopened the elevator at Java trip tick {resumed}.")
        if args.reload_idle:
            for tick in range(start + len(expected), start + len(expected) + 24):
                control.step_to(tick)
            idle = sample(control)
            if idle[:4] != ["false", "true", "true", "true"] or idle[-2] != "10.000000000":
                raise RuntimeError(f"The elevator did not settle at the top floor: {idle}.")
            control.restart()
            reopened = sample(control)
            if reopened != idle:
                raise RuntimeError(f"The stopped elevator changed on reload: {idle} to {reopened}.")
            print("Stopped elevator and its cow remained at the top floor after reopening.")

            control.command(f"/setblock {as_argument(BOTTOM_LEVER)} minecraft:lever[face=floor,facing=west,powered=false]")
            control.call("tp", *at((0.5, 1.0, 2.5)))
            control.call("wait", 3)
            control.call("look-at-block", *at(BOTTOM_LEVER))
            control.call("interact", *at(BOTTOM_LEVER))
            lever = control.call("block", *at(BOTTOM_LEVER))["state"]
            if "powered=true" not in lever:
                raise RuntimeError(f"The player did not toggle the lower call lever: {lever}.")
            with (ROOT / "fixtures/elevator-return-java.csv").open() as source:
                reader = csv.reader(source)
                return_header, return_expected = next(reader), list(reader)
            clock = control.clock()
            descent = []
            for tick, *_ in return_expected:
                if int(tick):
                    control.step_to(clock + int(tick))
                descent.append([tick, *sample(control)])
                if tick == "1":
                    floor = control.call("block", *at((2, 1, 2)))["state"]
                    if "calling=true" not in floor:
                        raise RuntimeError(f"The lower call did not reach the elevator contact: {floor}.")
            path = ROOT / ".local/elevator-return-horizon.csv"
            with path.open("w", newline="") as stream:
                writer = csv.writer(stream, lineterminator=chr(10))
                writer.writerow(return_header)
                writer.writerows(descent)
            if descent != return_expected:
                first = next((a, b) for a, b in zip(return_expected, descent, strict=True) if a != b)
                raise RuntimeError(f"Return trip differs from Java. First mismatch {first}. See {path}.")
            print(f"Returned the reopened elevator to the bottom. All {len(descent)} Java ticks matched.")

            control.call("tp", *at((7.5, 11.0, 4.5)))
            control.call("wait", 3)
            control.call("look-at-block", *at(PRIMARY))
            control.call("interact", *at(PRIMARY))
            clock = control.clock()
            for tick in range(clock + 1, clock + 4):
                control.step_to(tick)
            landed = sample(control)
            seat = control.call("block", *at((4, 2, 2)))["state"]
            if landed[3] != "false" or landed[4] or not seat.startswith("create:white_seat"):
                raise RuntimeError(f"The cabin and its seat did not disassemble at the bottom: {landed}, {seat}.")
            print("Disassembled the returned cabin and restored the seat block.")
    suffix = "-reload" if args.reload_at or args.reload_idle else ""
    output = ROOT / f".local/elevator{suffix}-horizon.csv"
    with output.open("w", newline="") as report:
        writer = csv.writer(report, lineterminator="\n")
        writer.writerow(columns[:2] + columns[3:])
        writer.writerows(actual.values())
    diffs = [(expected[tick], current) for tick, current in actual.items() if expected[tick] != current]
    if diffs:
        raise SystemExit(f"{len(diffs)} elevator mismatches. First six {diffs[:6]}. See {output}")
    print(f"Elevator matched {len(actual)} Java ticks. See {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--ticks", type=int, choices=range(1, 68), default=67)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--reload-at", type=int, choices=(35,))
    parser.add_argument("--reload-idle", action="store_true")
    args = parser.parse_args()
    if args.reload_at and (args.baseline or args.ticks <= args.reload_at + 3):
        parser.error("--reload-at requires an active elevator replay through the restart")
    if args.reload_idle and (args.baseline or args.ticks != 67):
        parser.error("--reload-idle requires the complete elevator fixture")
    run(args)
