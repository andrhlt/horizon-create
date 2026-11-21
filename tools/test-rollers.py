#!/usr/bin/env python3
"""Replay the original Java Create roller tracks and tunnel paving fixtures."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

SCENARIOS = {
    "roller_filling": ((3, 96, -12), (7, 5, 1, "north"), (4, 2)),
    "roller_paving_and_clearing": ((17, 96, -12), (8, 4, 1, "east"), (3, 1)),
}
GANTRY = "@e[type=minecraft:marker,tag=create_gantry_payload,limit=1]"
POSITION = re.compile(r"\[(-?[\d.Ee+-]+)d, (-?[\d.Ee+-]+)d, (-?[\d.Ee+-]+)d\]")
COMPOUND = re.compile(r"\{[^{}]+\}")


def stock(reply):
    return sum(int(count[1]) for tag in COMPOUND.findall(reply)
               if 'id: "create:andesite_casing"' in tag
               and (count := re.search(r"\bcount: (\d+)", tag)))


def sample(control, base, barrel):
    x, y, z = base
    report = control.command(f"/data get entity {GANTRY} Pos")
    position = POSITION.search(report)
    if position:
        carriage = ":".join(f"{float(value) - origin:.9f}"
                            for value, origin in zip(position.groups(), base, strict=True))
        reply = control.command(
            f"/data get entity {GANTRY} CreateGantry.Blocks[{{Pos:[I;0,-1,0]}}].VanillaEntity.Items")
        material = stock(reply)
    else:
        carriage = ""
        by, bz = barrel
        replies = control.commands(f"/data get block {x+bx} {y+by} {z+bz} Items" for bx in (2, 6))
        material = sum(map(stock, replies))
    report = control.call("blocks", x+1, y+1, z+1, x+4, y+4, z+3)
    bulk = {(wx, wy, wz): block.split("[", 1)[0] for wx, wy, wz, block in report["blocks"]}
    blocks = "|".join(bulk.get((x+dx, y+dy, z+dz), "minecraft:air")
                      for dx in range(1, 5) for dy in range(1, 5) for dz in range(1, 4))
    return [carriage, str(material), blocks]


def run(args):
    scenario = args.scenario
    base, lever, barrel = SCENARIOS[scenario]
    template = Path(f"gametest/contraptions/{scenario}.nbt")
    with (ROOT / f"fixtures/{scenario}-java.csv").open() as reference:
        rows = csv.reader(reference)
        full_header = next(rows)
        header = full_header[:2] + full_header[3:]
        expected = [row[:2] + row[3:] for row in list(rows)[:args.ticks]]
    actual = []
    with fixture_world(args, scenario, template) as control:
        control.command("/gamerule random_tick_speed 0")
        while control.clock() % 20 != int(expected[0][1]):
            control.step_to(control.clock() + 1)
        x, y, z = base
        lx, ly, lz, direction = lever
        control.command(f"/place template create:{template.with_suffix('')} {x} {y} {z}")
        if scenario == "roller_paving_and_clearing":
            # Java GameTest adds a barrier shell immediately outside the structure.
            control.command(f"/fill {x} {y} {z+3} {x+9} {y+6} {z+3} minecraft:barrier")
        control.command(f"/setblock {x+lx} {y+ly} {z+lz} minecraft:lever[face=wall,facing={direction},powered=false]")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            if args.reopen_at is not None and tick == args.reopen_at:
                before = sample(control, base, barrel)
                control.command("/save-all flush")
                control.restart()
                after = sample(control, base, barrel)
                if before != after:
                    raise RuntimeError(f"{scenario} save/reopen changed actor position, inventory or blocks at tick {tick}: {before} -> {after}")
                start = control.clock() - tick
            actual.append([str(tick), expected[tick][1], *sample(control, base, barrel)])
    dest = ROOT / f".local/{scenario}-horizon.csv"
    with dest.open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = []
    for want, got in zip(expected, actual, strict=True):
        if want == got:
            continue
        detail = {key: (a, b) for key, a, b in zip(header, want, got, strict=True) if a != b}
        if "world_blocks" in detail:
            oracle, native = detail.pop("world_blocks")
            detail["blocks"] = [(i, a, b) for i, (a, b) in enumerate(zip(oracle.split("|"), native.split("|"), strict=True)) if a != b]
        differences.append((want[0], detail))
    if differences:
        raise SystemExit(f"{scenario} differed at {len(differences)} ticks. First differences (Java, Horizon) {differences[:5]}. See {dest}")
    print(f"{scenario} matched all {len(actual)} Java ticks. See {dest}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("scenario", choices=tuple(SCENARIOS))
    parser.add_argument("--ticks", type=int)
    parser.add_argument("--reopen-at", type=int, help="save/reopen once at this sampled tick")
    args = parser.parse_args()
    if args.ticks is not None and args.ticks < 1:
        parser.error("--ticks must be positive")
    if args.reopen_at is not None and args.reopen_at < 1:
        parser.error("--reopen-at must be positive")
    run(args)
