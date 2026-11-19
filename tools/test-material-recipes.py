#!/usr/bin/env python3
"""Replay pinned Java Basin material and vanilla cooking recipe traces."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

fluid = import_module("test-fluid-food")


def reference(domain, shape):
    with (ROOT / f"fixtures/{domain}-materials-{shape}-java.csv").open(newline="") as source:
        reader = csv.reader(source)
        return next(reader), list(reader)


def inventory(tag):
    slots = {}
    items = re.search(r"\bItems: \[([^\]]*)\]", tag)
    if items is None:
        return slots
    for stack in re.findall(r"\{[^{}]*\}", items[1]):
        item = re.search(r'\bid: "([^"]+)"', stack)
        slot = fluid.number(stack, "Slot", -1)
        if item and slot >= 0:
            slots[int(slot)] = (item[1], int(fluid.number(stack, "count")))
    return slots


def replay_basin(control, setups, ticks):
    lanes = range(16, 16 + len(setups) * 2, 2)
    control.commands((
        "/tp @s 5 107 22",
        *(command for z in lanes for command in (
            f"/setblock 4 105 {z} create:creative_motor[facing=up]",
            f"/data merge block 4 105 {z} {{ScrollValue:256}}",
            f"/setblock 4 106 {z} create:cogwheel[axis=y]",
            f"/setblock 5 106 {z} create:mechanical_mixer",
            f"/setblock 5 104 {z} create:basin",
        )),
    ))
    queries = tuple(command for z in lanes for command in (
        f"/data get block 5 106 {z}", f"/data get block 5 104 {z}",
    ))
    start = control.clock() + 4
    for tick in range(start - 3, start + 1):
        control.step_to(tick)
    for tick in range(ticks):
        if tick:
            control.step_to(start + tick)
        replies = iter(control.commands(queries))
        for name, _, _, _, _ in setups:
            mixer, basin = next(replies), next(replies)
            if 'create:mechanical_mixer' not in mixer or 'create:basin' not in basin:
                raise RuntimeError(f"Missing mixer or basin in {name}: {mixer}, {basin}")
            slots = inventory(basin)
            output, output_count = slots.get(9, ("-", 0))
            yield [
                str(tick), name, str(int(fluid.number(mixer, "Speed"))),
                str(bool(fluid.number(mixer, "Running"))).lower(),
                *(str(int(fluid.number(mixer, key))) for key in ("Ticks", "ProcessingTicks")),
                str(slots.get(0, ("-", 0))[1]), str(slots.get(1, ("-", 0))[1]),
                str(fluid.quantity(basin, "InputTanks")), output, str(output_count),
            ]
        if tick == 0:
            loads = []
            for z, (_, primary, secondary, water, _) in zip(lanes, setups, strict=True):
                at = f"5 104 {z}"
                if int(water):
                    loads.append(
                        f'/data merge block {at} '
                        '{InputTanks:[{TankContent:{Fluid:{id:"minecraft:water",amount:%s}}},{}]}' % water
                    )
                loads.append(f"/item replace block {at} container.0 with {primary}")
                if secondary != "-":
                    loads.append(f"/item replace block {at} container.1 with {secondary}")
            control.commands(loads)


def replay_cooking(control, setups, ticks):
    lanes = range(5, 5 + len(setups) * 3, 3)
    control.commands((
        "/tp @s 8.5 180 22.5",
        *(f"/setblock {x} 180 23 {block}" for x, (_, block, _, _) in zip(lanes, setups, strict=True)),
    ))
    queries = tuple(command for x, (_, block, _, _) in zip(lanes, setups, strict=True) for command in (
        f"/data get block {x} 180 23",
        f"/execute if block {x} 180 23 {block}[lit=true]",
    ))
    start = control.clock()
    for tick in range(ticks):
        if tick:
            control.step_to(start + tick)
        replies = iter(control.commands(queries))
        for name, block, _, _ in setups:
            tag, lit = next(replies), next(replies)
            if block not in tag:
                raise RuntimeError(f"Missing cooking appliance in {name}: {tag}")
            slots = inventory(tag)
            output, output_count = slots.get(2, ("-", 0))
            yield [
                str(tick), name, str(lit.startswith("Test passed")).lower(),
                *(str(int(fluid.number(tag, key))) for key in ("cooking_time_spent", "cooking_total_time")),
                str(slots.get(0, ("-", 0))[1]), output, str(output_count),
            ]
        if tick == 0:
            control.commands(command for x, (_, _, item, _) in zip(lanes, setups, strict=True) for command in (
                f"/item replace block {x} 180 23 container.0 with {item}",
                f"/item replace block {x} 180 23 container.1 with minecraft:coal",
            ))


def compare(args, domain, replay):
    _, setups = reference(domain, "setup")
    header, java = reference(domain, "timing")
    if args.scenario:
        setups = [row for row in setups if row[0] in args.scenario]
        java = [row for row in java if row[1] in args.scenario]
    if not setups:
        return True
    trace = args.output / f"{domain}-materials-horizon.csv"
    with fixture_world(args, f"{domain.title()}Materials", pack=args.pack) as control:
        horizon = list(replay(control, setups, len(java) // len(setups)))
    with trace.open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(horizon)
    mismatches = [(want, got) for want, got in zip(java, horizon, strict=True) if want != got]
    if mismatches:
        affected = sorted({row[1] for row, _ in mismatches})
        print(f"{domain.title()} mismatched Java in {len(mismatches)}/{len(java)} samples "
              f"across {', '.join(affected)}. First differences (Java, Horizon): {mismatches[:7]}. Trace: {trace}")
        return False
    print(f"{domain.title()} matched all {len(java)} Java samples over {len(setups)} scenarios. Trace: {trace}")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--output", type=Path, default=ROOT / ".local")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--basin-only", action="store_true")
    scope.add_argument("--cooking-only", action="store_true")
    parser.add_argument("--scenario", action="append", help="replay only a named scenario; repeat for multiple cases")
    args = parser.parse_args()
    domains = []
    if not args.cooking_only:
        domains.append(("basin", replay_basin))
    if not args.basin_only:
        domains.append(("cooking", replay_cooking))
    if args.scenario:
        known = {row[0] for domain, _ in domains for row in reference(domain, "setup")[1]}
        unknown = set(args.scenario) - known
        if unknown:
            parser.error(f"unknown scenarios: {', '.join(sorted(unknown))}")
    args.output.mkdir(parents=True, exist_ok=True)
    passed = [compare(args, domain, replay) for domain, replay in domains]
    if not all(passed):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
