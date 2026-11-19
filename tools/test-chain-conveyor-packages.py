#!/usr/bin/env python3
"""Replay real conveyor block-entity ticks against the pinned Java package and world traces."""

import argparse
from collections import defaultdict
import csv
import importlib
from pathlib import Path
import re
from struct import pack

from fixture_world import ROOT, fixture_world


chain = importlib.import_module("test-chain-conveyor-kinetics")
snbt = importlib.import_module("test-packager-redstone")

WHEELS = {"straight": (7, 0, 0), "rising_reversal": (6, 2, 3)}
ADDRESS = "Lab-In"


def coords(pos):
    return " ".join(map(str, pos))


def emit_vector(pos):
    return "[I;" + ",".join(map(str, pos)) + "]"


def vector(tag):
    match = re.search(r"\[I;\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\]", tag)
    if not match:
        raise RuntimeError(f"Expected position in {tag}")
    return ":".join(match.groups())


def field_vector(tag, name):
    return vector(tag.partition(f"{name}:")[2]) if f"{name}:" in tag else "-"


def scalar(tag, name):
    m = re.search(rf"\b{name}:\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)", tag)
    return m[1] if m else "0"


def address(tag):
    return re.search(r'create:package_address["\']?:\s*["\']([^"\']*)["\']', tag)[1]


def payload(tag):
    cargo = re.search(r'minecraft:(paper|string)["\']', tag)
    if not cargo:
        raise RuntimeError(f"Missing cargo in {tag}")
    item = re.search(r"\{([^{}]*minecraft:(?:paper|string)[^{}]*)\}", tag)
    count = scalar(item[1], "count")
    return f"{address(tag)}:{cargo[1]}:{count}"


def stack(package_address, item, count):
    return ('{id:"create:cardboard_package_12x12",count:1,components:{'
            f'"create:package_address":"{package_address}","create:package_contents":'
            f'[{{slot:0,item:{{id:"minecraft:{item}",count:{count}}}}}]' + '}}')


def merge(world, pos, data):
    world.command(f"/data merge block {coords(pos)} {data}")


def setup(world, a, b, motor, port, delta, rising, *, warm=3):
    world.commands((
        "/fill 6 98 -12 19 107 -5 minecraft:air",
        f"/setblock {coords(a)} create:chain_conveyor",
        f"/setblock {coords(b)} create:chain_conveyor",
        f"/setblock {coords(motor)} create:creative_motor[facing=up]",
        f"/data merge block {coords(motor)} {{ScrollValue:128}}",
    ))
    if not rising:
        world.command(f"/setblock {coords(port)} create:package_frogport")
    chain.set_link(world, a, delta)
    chain.set_link(world, b, tuple(-n for n in delta))
    now = world.clock()
    for i in range(1, warm + 1):
        world.step_to(now+i)


def run(args, scenario, expected, packages):
    rising = scenario == "rising_reversal"
    delta = WHEELS[scenario]
    a = (8, 102, -10)
    b = tuple(p + d for p, d in zip(a, delta))
    motor = (a[0], a[1] - 1, a[2])
    port = (b[0] + 2, b[1] - 2, b[2])
    errors = []
    label = f"ChainPackages-{scenario}" + (f"-Reopen{args.reopen_at}" if args.reopen_at is not None else "")
    with fixture_world(args, label, pack=args.pack) as world:
        setup(world, a, b, motor, port, delta, rising)
        start = world.clock()
        for tick, java in enumerate(expected):
            if rising and tick in (11, 41):
                merge(world, motor, f"{{ScrollValue:{-128 if tick == 11 else 128}}}")
            if rising and tick == 31:
                world.command(f"/setblock {coords(motor)} minecraft:air")
            if tick == len(expected) - 4:
                chain.set_link(world, a)
                chain.set_link(world, b)

            if tick:
                world.step_to(start + tick)
            if not rising and tick == 0:
                merge(world, port, f'{{AddressFilter:"{ADDRESS}"}}')
                merge(world, b, '{PackagePorts:[{Port:[I;2,-2,0],ChainPosition:150f}]}')
            if tick == 2:
                matching = stack(ADDRESS, "paper", 3)
                if rising:
                    boxes = f"{{Item:{matching},Position:0f,Connection:{emit_vector(delta)}}}"
                else:
                    boxes = (f"{{Item:{matching},Position:40f}},"
                             f'{{Item:{stack("Other", "string", 2)},Position:40f}}')
                merge(world, a, f"{{Packages:[{boxes}]}}")
            if rising and tick == 39:
                world.command(f"/setblock {coords(motor)} create:creative_motor[facing=up]")

            if tick == args.reopen_at:
                world.call("save")
                world.env["HORIZON_STILL"] = "1"
                world.restart()
                assert world.clock() == start + tick, (tick, world.clock(), start)
            positions = (a, b) if rising else (a, b, port)
            replies = world.commands(f"/data get block {coords(pos)}" for pos in positions)
            contents = [reply.partition("block data: ")[2] for reply in replies]
            assert all(contents), replies
            seen = []
            for wheel, pos in zip(("A", "B"), (a, b)):
                tags = world.command(f"/data get block {coords(pos)} Packages").partition("block data: ")[2]
                for entry in snbt.top_level_entries(tags):
                    edge = field_vector(entry, "Connection")
                    seen.append((wheel, "loop" if edge == "-" else "travel", edge, payload(entry),
                                 pack("f", float(scalar(entry, "Position")))))
            java_motion = [(p["wheel"], p["path"], p["edge"], p["payload"],
                            pack("f", float(p["chain_position"]))) for p in packages.get(tick, ())]

            route = next((field_vector(entry, "Next") for entry in
                          snbt.top_level_entries(world.command(f"/data get block {coords(a)} RoutingEntries")
                                                 .partition("block data: ")[2])
                          if ADDRESS in entry), "0:0:0")
            progress = float(scalar(contents[2], "AnimationProgress")) if not rising else 0.0
            custody = "-"
            if not rising:
                tag = contents[2]
                if "ReceivingPackage:" in tag:
                    if "AnimationStartedAt:" in tag:
                        receipt = tag.partition("ReceivingPackage:")[2]
                        custody = "animation:" + payload(receipt)
                elif "create:package_contents" in tag:
                    custody = "inventory:" + payload(tag)
            a_tag, b_tag = contents[:2]
            edge_flags = tuple(
                world.command(f"/data get block {coords(pos)} Connections").find("[I;") != -1
                for pos in (a, b)
            )
            state = (
                *(float(scalar(tag, "Speed")) for tag in (a_tag, b_tag)),
                *edge_flags,
                *(scalar(tag, "Reversed") != "0" for tag in (a_tag, b_tag)),
                route,
                custody,
            )
            expected_state = (float(java["a_rpm"]), float(java["b_rpm"]),
                              *(java[field] == "true" for field in
                                ("a_has_edge", "b_has_edge", "a_reversed", "b_reversed")),
                              java["a_route_for_lab_in"], java["frogport_custody"])
            if sorted(seen) != sorted(java_motion):
                errors.append(f"tick {tick} package actual {seen!r}, Java {java_motion!r}")
            if state != expected_state or abs(progress - float(java["frogport_animation"])) > 1e-7:
                errors.append(f"tick {tick} world actual {state}, progress {progress}, "
                              f"Java {expected_state}, progress {java['frogport_animation']}")
            if len(errors) >= 12:
                break
    if errors:
        raise RuntimeError(scenario + "\n" + "\n".join(errors))
    print(f"{scenario}: {len(expected)} world ticks, {sum(map(len, packages.values()))} package states")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--scenario", choices=WHEELS)
    parser.add_argument("--reopen-at", type=int)
    args = parser.parse_args()
    if args.reopen_at is not None and not args.scenario:
        parser.error("--reopen-at requires a scenario")
    world, packages = defaultdict(list), defaultdict(lambda: defaultdict(list))
    with (ROOT / "fixtures/chain-conveyor-world-java.csv").open() as rows:
        for row in csv.DictReader(rows):
            world[row["scenario"]].append(row)
    with (ROOT / "fixtures/chain-conveyor-package-java.csv").open() as rows:
        for row in csv.DictReader(rows):
            packages[row["scenario"]][int(row["tick"])].append(row)
    if args.scenario == "straight" and args.reopen_at == 27:
        with (ROOT / "fixtures/chain-conveyor-port-reload-java.csv").open() as rows:
            for row in csv.DictReader(rows):
                sample = world["straight"][int(row["tick"])]
                sample.update(frogport_animation=row["progress"], frogport_custody=row["custody"])
    for scenario in (args.scenario,) if args.scenario else WHEELS:
        if args.reopen_at is not None and not 0 <= args.reopen_at < len(world[scenario]):
            parser.error("--reopen-at is outside the selected trace")
        run(args, scenario, world[scenario], packages[scenario])


if __name__ == "__main__":
    main()
