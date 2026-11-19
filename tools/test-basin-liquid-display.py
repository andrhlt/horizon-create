#!/usr/bin/env python3
"""Replay the visible fluid compartments of a Basin as it fills and drains."""

import argparse
import csv
from pathlib import Path
import re
import struct

from fixture_world import ROOT, fixture_world

BASIN = "5 97 -9"
PARTIALS = (0.0, 0.5, 1.0)
FLOAT = r"-?\d+(?:\.\d+)?(?:[Ee][-+]?\d+)?"


def f32(n):
    return struct.unpack("<f", struct.pack("<f", float(n)))[0]


def level(tank, key):
    match = re.search(rf"\b{key}: ({FLOAT})", tank)
    return f32(match[1]) if match else 0.0


def dimensions(tanks, partial):
    units = []
    for tank in tanks:
        prior, current = level(tank, "PreviousLevel"), level(tank, "Level")
        value = f32(f32(prior + f32(f32(current - prior) * partial)) * 1000)
        units.append(value if value >= 1 else 0.0)
    total = 0.0
    for value in units:
        total = f32(total + value)
    fill = min(f32(total / 2000), 1.0)
    remainder = f32(1.0 - fill)
    surface = f32(0.125 + f32(f32(1.0 - f32(remainder * remainder)) * 0.75))
    widths = [f32(f32(value / total) * 0.75) if total else 0.0 for value in units]
    return [total, surface, *(n for values in zip(units, widths, strict=True) for n in values)]


def fluid(ident, amount):
    return f'{{TankContent:{{Fluid:{{id:"{ident}",amount:{amount}}}}}}}'


def place(control):
    control.command("/fill 3 96 -11 8 96 -6 minecraft:smooth_stone")
    control.command("/fill 3 97 -11 8 100 -6 minecraft:air")
    control.command(f"/setblock {BASIN} create:basin")
    if not control.command(f"/execute if block {BASIN} create:basin").startswith("Test passed"):
        raise RuntimeError("The fixture could not place create:basin. Check that the Create pack loaded.")


def update(control, tick):
    if tick == 4:
        water, lava = fluid("minecraft:water", 1000), fluid("minecraft:lava", 500)
        honey = fluid("create:honey", 250)
        control.command(f"/data merge block {BASIN} {{InputTanks:[{water},{lava}],OutputTanks:[{honey},{{}}]}}")
    elif tick == 20:
        control.command(f"/data modify block {BASIN} InputTanks[0].TankContent set value {{}}")
    elif tick == 28:
        chocolate = fluid("create:chocolate", 250)
        control.command(f"/data modify block {BASIN} OutputTanks[1] set value {chocolate}")


def sample(control, tick):
    tag = control.command(f"/data get block {BASIN} BasinFluidVisual")
    tanks = re.findall(r"\{(?:[^{}]|\{[^{}]*\})*\}", tag)
    if tanks and len(tanks) != 4:
        raise RuntimeError(f"Expected four visual tank slots: {tag}")
    for partial in PARTIALS:
        geometry = dimensions(tanks or ("",) * 4, partial)
        yield [str(tick), f"{partial:.1f}", *(f"{value:.7f}" for value in geometry)]


def run(args):
    with (ROOT / "fixtures/basin-liquid-display-java.csv").open() as source:
        reader = csv.reader(source)
        headers, expected = next(reader), list(reader)
    actual = []
    with fixture_world(args, "Basin-liquid-display", render=args.visual, pack=args.pack) as control:
        place(control)
        if args.visual:
            control.command("/time set noon")
            control.command("/setblock 6 100 -8 minecraft:barrier")
            control.call("tp", 6.5, 101.0, -7.5)
            control.call("key", "f1", "tap")
        start = control.clock()
        for tick in range(1, int(expected[-1][0]) + 1):
            control.step_to(start + tick)
            actual.extend(sample(control, tick))
            if args.visual and tick in (4, 18, 42):
                control.call("look-at", 5.5, 97.48, -8.5)
                control.call("wait", 2)
                control.call("screenshot", ROOT / f".local/basin-liquid-display-{tick}.png")
            update(control, tick)
    output = ROOT / ".local/basin-liquid-display-horizon.csv"
    with output.open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(actual)
    differences = [
        (java, horizon)
        for java, horizon in zip(expected, actual, strict=True)
        if java[:2] != horizon[:2] or any(
            abs(float(a) - float(b)) > (0.0003 if index % 2 == 0 else 0.000002)
            for index, (a, b) in enumerate(zip(java[2:], horizon[2:], strict=True))
        )
    ]
    if differences:
        raise SystemExit(f"Basin display differed on {len(differences)} rows (Java, Horizon): "
                         f"{differences[:4]}. See {output}")
    print(f"Basin fluid geometry matched {len(actual)} Java samples. See {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--pack", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())
