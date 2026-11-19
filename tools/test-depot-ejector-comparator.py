#!/usr/bin/env python3
"""Compare Java Weighted Ejector signal, item delivery and lid motion."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

launch = import_module("test-depot-ejector-launch")
multiplayer = import_module("test-multiplayer")
SOURCE = "5 104 -11"
COMPARATOR = "6 104 -11"
WIRE = (7, 104, -11)
DEPOT = "9 104 -11"


def setup(host):
    host.commands((
        "/fill 2 103 -13 12 103 -9 minecraft:smooth_stone",
        "/fill 2 104 -13 12 112 -9 minecraft:air",
        f"/setblock {SOURCE} create:weighted_ejector[facing=east]{{HorizontalDistance:4,VerticalDistance:0,ScrollValue:4}}",
        "/setblock 4 104 -11 minecraft:redstone_block",
        "/setblock 5 104 -12 create:creative_motor[facing=south]{ScrollValue:128}",
        f"/setblock {COMPARATOR} minecraft:comparator[facing=west]",
        "/setblock 7 104 -11 minecraft:redstone_wire",
        f"/setblock {DEPOT} create:depot",
        "/gamemode spectator @s",
        "/tp @s 8.5 105 -9.5",
    ))


def select_unlimited(host, actor):
    actor.call("look-at", 5.99, 104.375, -10.5)
    actor.call("mouse", "right", "down")
    actor.call("wait", 7)
    row = next((button for button in actor.call("screen")["buttons"]
                if button["label"] == "Ejected Stack Size"), None)
    if not row:
        actor.call("mouse", "right", "up")
        raise RuntimeError("The Ejector stack-size board did not open.")
    x, y = row["x"] + 3.5, row["y"] + row["h"] / 2
    actor.call("scroll-at", x, y, 0)
    actor.call("click-at", x, y, "right")
    actor.call("wait", 3)
    multiplayer.until("the Ejector accepts the Unlimited setting", lambda:
                      launch.value(host.command(f"/data get block {SOURCE} ScrollValue")) == 0)


def wire_power(reply):
    state = reply["state"]
    matched = re.search(r"\bpower=(\d+)", state)
    if matched is None:
        raise RuntimeError(f"Could not read redstone wire power: {state}")
    return int(matched[1])


def observation(host, tick):
    state, held, output, delivered, lid = host.commands((
        f"/data get block {SOURCE} State",
        f"/data get block {SOURCE} Items",
        f"/data get block {COMPARATOR} OutputSignal",
        f"/data get block {DEPOT} Items",
        f"/data get block {SOURCE} Lid",
    ))
    phase = re.search(r"\b(CHARGED|LAUNCHING|RETRACTING)\b", state)
    if phase is None:
        raise RuntimeError(f"Could not read Ejector at tick {tick}: {state}")
    power = launch.value(output)
    if power is None:
        # Horizon can omit an inactive comparator's empty block entity.
        if "no block entity" not in output.lower() and "found no elements" not in output.lower():
            raise RuntimeError(f"Could not read comparator at tick {tick}: {output}")
        power = 0
    values = dict(re.findall(r"\b(Previous|Value): ([-.0-9]+)f", lid))
    if values.keys() != {"Previous", "Value"}:
        raise RuntimeError(f"Could not read lid interpolation at tick {tick}: {lid}")
    previous, current = float(values["Previous"]), float(values["Value"])
    comparison = [str(tick), phase[1], str(launch.count(held)), str(int(power)),
                  str(wire_power(host.call("block", *WIRE))), str(launch.count(delivered))]
    return comparison, (previous, (previous + current) / 2, current)


def run(args):
    with args.reference.open() as source:
        data = csv.reader(source)
        header = next(data)
        # Java exposes raw strength directly. Horizon is observed through the actual circuit.
        del header[3]
        expected = [row[:3] + row[4:] for row in data]
    with (ROOT / "fixtures/depot-ejector-lid-motion-java.csv").open() as source:
        lid_expected = {int(tick): (phase, tuple(map(float, values)))
                        for tick, phase, *values in list(csv.reader(source))[1:]}
    actual = []
    lid_differences = []
    with ExitStack() as stack:
        world = "EjectorComparatorLAN" if args.multiplayer else "EjectorComparator"
        host = stack.enter_context(fixture_world(args, world, render=True, pack=args.pack))
        setup(host)
        guest = None
        if args.multiplayer:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejector-meter-")))
            name = "EjectMeterGuest"
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, scenario="ejector-meter", render=True, pack=args.pack,
            ))
            multiplayer.until("the comparator fixture guest joins", lambda: any(
                player["name"] == name and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((f"/gamemode survival {name}", f"/tp {name} 7.5 104 -10.5"))
            multiplayer.until("guest sees the redstone circuit", lambda:
                              guest.call("block", *WIRE)["block"] == "minecraft:redstone_wire")
        if not guest:
            host.commands(("/gamemode survival @s", "/tp @s 7.5 104 -10.5"))
        start = host.clock()
        for row in expected:
            tick = int(row[0])
            host.step_to(start + tick)
            if tick in (12, 18, 24, 30):
                count = 1 + (tick - 12) // 6
                host.command(f'/data merge block {SOURCE} '
                             f'{{Items:[{{Slot:0b,id:"minecraft:iron_ingot",count:{count}}}],BeltPosition:0.5f}}')
            if tick == 34:
                select_unlimited(host, guest or host)
                if host.clock() != start + tick:
                    raise RuntimeError("Selecting Unlimited advanced the fixture clock.")
            if tick == 36:
                host.command("/setblock 4 104 -11 minecraft:air")
            comparison, lid = observation(host, tick)
            actual.append(comparison)
            phase, wanted = lid_expected[tick]
            if comparison[1] != phase or any(
                    abs(actual_value - expected_value) > 1e-6
                    for actual_value, expected_value in zip(lid, wanted, strict=True)):
                lid_differences.append((tick, phase, wanted, comparison[1], lid))
            if guest and tick in (15, 21, 27, 33, 37, 41):
                multiplayer.until(f"guest sees wire strength {row[4]} at fixture tick {tick}", lambda:
                                  wire_power(guest.call("block", *WIRE)) == int(row[4]))
        if guest:
            guest.call("interact", 9, 104, -11, "up")
            multiplayer.until("guest receives the measured stack", lambda: multiplayer.count(guest, launch.ITEM) == 4)
    if args.trace:
        with args.trace.open("w") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True) if a != b]
    if differences:
        raise RuntimeError(f"The Ejector comparator differed on {len(differences)} Java ticks: {differences[:8]}")
    if lid_differences:
        raise RuntimeError(f"The Ejector lid differed on {len(lid_differences)} Java ticks: {lid_differences[:8]}")
    print(f"The Comparator, redstone wire, final delivery and lid matched all {len(actual)} Java ticks.")
    if args.multiplayer:
        print("The LAN guest saw all six comparator transitions and collected the delivered stack.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/depot-ejector-comparator-java.csv")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    run(parser.parse_args())
