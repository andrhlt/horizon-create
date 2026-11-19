#!/usr/bin/env python3
"""Replay Java Create's mounted item extraction and fluid drain GameTests."""
import argparse
from collections import Counter
import csv
from pathlib import Path
import re
import struct

from fixture_world import ROOT, fixture_world

SCENARIOS = {
    "mounted_item_extract": (14, "minecraft:barrel"),
    "mounted_fluid_drain": (3, "create:fluid_tank"),
}


def data(reply):
    return reply.partition(" has the following block data: ")[2]


def amount(reply, key):
    return sum(map(int, re.findall(rf"\b{key}: (\d+)\b", data(reply))))


def cargo(reply):
    totals = Counter()
    for entry in re.findall(r"\{([^{}]+)\}", data(reply)):
        item = re.search(r'\bid: "([^"]+)"', entry)
        count = re.search(r"\bcount: (\d+)\b", entry)
        if item and count:
            totals[item[1]] += int(count[1])
    return "|".join(f"{item}={totals[item]}" for item in sorted(totals))


def java_float(text):
    value, = struct.unpack("f", struct.pack("f", float(text.removesuffix("f"))))
    return f"{value:.6f}"


def sample(control, x, fluid):
    bearing = f"{x+1} 99 -10"
    source = f"{x+1} 98 -10"
    output = f"{x+4} 97 -11"
    path = "TankContent.Fluid" if fluid else "Items"
    queries = [
        f"/data get block {bearing} Running",
        f"/data get block {bearing} Angle",
        f"/data get block {source} {path}",
        f"/data get block {bearing} " + ("MovedBlocks[0].Entity.TankContent.Fluid" if fluid else "MountedItems"),
        f"/data get block {output} {path}",
    ]
    if not fluid:
        queries.append(f"/data get block {x+4} 97 -10 Items")
    moving, angle, stored, mounted, received, *hopper = control.commands(queries)
    running = data(moving) == "1b"
    key = "amount" if fluid else "count"
    source = mounted if running else stored
    if fluid:
        for reply in (source, received):
            if amount(reply, key) and 'id: "minecraft:water"' not in data(reply):
                raise RuntimeError(f"The original fixture carries water. Found {reply}.")
    state = [str(int(running)), java_float(data(angle)) if running else "",
             str(amount(source, key)), str(amount(received, key))]
    if not fluid:
        state.extend(cargo(reply) for reply in (source, hopper[0], received))
    return state


def run(args, scenario):
    x, storage = SCENARIOS[scenario]
    structure = Path(f"gametest/contraptions/{scenario}.nbt")
    with (ROOT / f"fixtures/{scenario}-java.csv").open() as reference:
        reader = csv.reader(reference)
        header, expected = next(reader), list(reader)[:args.ticks]
    fluid = storage == "create:fluid_tank"
    cargo_path = ROOT / "fixtures/mounted_item_cargo-java.csv"
    if not fluid:
        with cargo_path.open() as reference:
            reader = csv.reader(reference)
            cargo_header, expected_cargo = next(reader), list(reader)[:args.ticks]
        header.extend(cargo_header[1:])
        for basic, items in zip(expected, expected_cargo, strict=True):
            if basic[0] != items[0]:
                raise RuntimeError(f"Different Java sample tick for state {basic} and cargo {items}.")
            basic.extend(items[1:])
    actual = []
    with fixture_world(args, scenario, structure, pack=args.pack) as control:
        time = control.clock()
        for tick in range(time + 1, time + (int(expected[0][1]) - time) % 20 + 1):
            control.step_to(tick)
        control.command(f"/place template create:{structure.with_suffix('')} {x} 96 -12")
        lever = f"{x+1} 100 -11 minecraft:lever[face=wall,facing=north,powered="
        control.command(f"/setblock {lever}false]")
        start = control.clock()
        for tick, *_ in expected:
            if int(tick):
                control.step_to(start + int(tick))
            actual.append([tick, str((start + int(tick)) % 20),
                           *sample(control, x, fluid)])
            _, _, running, _, source, output, *_ = actual[-1]
            if tick == "2" and not fluid:
                if "Test passed" in control.command("/execute if entity @e[type=minecraft:item]"):
                    raise RuntimeError("Assembling the bearing dropped some of its cargo.")
            if running == "1" and source == "0" and output == expected[0][4]:
                control.command(f"/setblock {lever}true]")
        restored = None
        if len(expected) > 1 and expected[-2][2] == "1" and expected[-1][2] == "0":
            restored = (control.call("block", x+1, 98, -10)["state"],
                        control.call("block", x+2, 98, -10)["state"])
    path = ROOT / f".local/{scenario}-horizon.csv"
    with path.open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want[0], {key: (a, b) for key, a, b in zip(header, want, got, strict=True) if a != b})
                   for want, got in zip(expected, actual, strict=True) if want != got]
    if differences:
        raise SystemExit(f"{scenario} differed at {len(differences)} ticks. "
                         f"First differences (Java, Horizon) {differences[:6]}. See {path}")
    if restored:
        interface = "portable_fluid_interface" if fluid else "portable_storage_interface"
        model, _, properties = restored[1].partition("[")
        properties = dict(pair.split("=", 1) for pair in properties.rstrip("]").split(",") if "=" in pair)
        if (restored[0].split("[", 1)[0] != storage
                or model != f"create:{interface}" or properties.get("facing") != "east"
                or properties.get("extended", "false") != "false"):
            raise RuntimeError(f"{scenario} restored an unexpected payload. Found {restored}.")
    print(f"{scenario} matched all {len(actual)} Java ticks. See {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("scenario", choices=tuple(SCENARIOS))
    parser.add_argument("--ticks", type=int)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    if args.ticks is not None and args.ticks < 1:
        parser.error("--ticks must be positive")
    run(args, args.scenario)
