#!/usr/bin/env python3
"""Replay Java's shaft transmission, Flywheel coast and placement axes."""

import argparse
import csv
from pathlib import Path
import re
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world

MOTOR = "4 106 -11"
WHEEL = "5 106 -11"
SHAFT = "6 106 -11"
COG = "5 106 -10"
NUMBER = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"


def number(nbt, key):
    match = re.search(rf"\b{key}: ({NUMBER})", nbt)
    return float(match[1]) if match else 0.0


def sample(control, tick):
    wheel, shaft, cog = control.commands((
        f"/data get block {WHEEL}",
        f"/data get block {SHAFT}",
        f"/data get block {COG}",
    ))
    if "create:flywheel" not in wheel:
        raise RuntimeError(f"The Flywheel block entity did not load: {wheel}")
    return [tick, number(wheel, "Speed"), number(shaft, "Speed"), number(cog, "Speed"),
            number(wheel, "Stress"), number(wheel, "Capacity")]


def power(control, speed, place=False):
    if place:
        control.command(f"/setblock {MOTOR} create:creative_motor[facing=east]")
    control.command(f"/data merge block {MOTOR} {{ScrollValue:{speed}}}")


def place_by_player(control):
    with (ROOT / "fixtures/flywheel-placement-java.csv").open() as source:
        placement = list(csv.DictReader(source))
    control.command("/fill 3 96 -13 8 96 -5 minecraft:smooth_stone")
    control.command("/item replace entity @s hotbar.0 with create:flywheel 4")
    control.call("select", "create:flywheel")
    control.command("/gamemode survival")
    for row in placement:
        case = int(row["case"])
        if case == 1:
            control.command("/setblock 6 98 -9 minecraft:barrier")
            control.command("/tp @s 6.1 99 -8.9")
        else:
            control.command("/tp @s 5.5 97 -7.0")
        if case == 2:
            control.command("/setblock 6 97 -10 create:shaft[axis=x]")
        if case == 3:
            control.call("key", "shift", "down")
            control.call("wait", 5)
        control.call("look-at", 5.5, 96.99, -9.5)
        control.call("wait", 3)
        hit = control.call("looking-at")
        control.call("mouse", "right", "click")
        control.call("wait", 3)
        if case == 3:
            control.call("key", "shift", "up")
        actual = control.call("block", 5, 97, -10)["state"]
        if actual != f"create:flywheel[axis={row['axis']}]":
            raise RuntimeError(f"For placement case {case}, Java used {row['axis']}. Horizon placed {actual} (crosshair {hit}).")
        control.command("/setblock 5 97 -10 minecraft:air")
        if case == 1:
            control.command("/setblock 6 98 -9 minecraft:air")
    if control.call("inventory")["counts"].get("create:flywheel", 0):
        raise RuntimeError("The four successful survival placements did not consume the four Flywheels")


def check_assets(pack, source):
    roots = tuple(source / "src" / name / "resources" for name in ("main", "generated"))
    with ZipFile(pack) as archive:
        properties = {
            "blockstates/flywheel.json", "models/item/flywheel.json",
            "models/block/flywheel/block.json", "models/block/flywheel/item.json",
            "models/block/flywheel/flywheel.json", "models/block/flywheel/flywheel.mtl",
            "models/block/flywheel/flywheel.obj", "models/block/flywheel/flywheel_shaftless.obj",
            "textures/block/flywheel.png",
        }
        for model in properties:
            name = f"assets/create/{model}"
            original = next(root / name for root in roots if (root / name).is_file())
            if archive.read(name) != original.read_bytes():
                raise RuntimeError(f"The original Flywheel asset differs: {name}")


def read_motion(log, start):
    return {
        int(tick) - start: [float(previous), float(speed), float(angle)]
        for tick, _, previous, speed, angle in re.findall(
            rf"CREATE_FLYWHEEL_HORIZON (-?\d+),({NUMBER}),({NUMBER}),({NUMBER}),({NUMBER})",
            log.read_text(),
        )
    }


def run(args):
    with (ROOT / "fixtures/flywheel-java.csv").open() as source:
        rows = csv.reader(source)
        header, expected = next(rows), [[float(value) for value in row] for row in rows]
    if any(row[4:6] != [0.0, 0.0] for row in expected):
        raise RuntimeError("The pinned Flywheel must add no stress load or capacity")
    # The port tracks network totals. The Java per-block zero values above
    # document the reference rather than stand in for any recorded port field.
    header = header[:4] + header[6:]
    expected = [row[:4] + row[6:] for row in expected]
    pack = args.pack or ROOT / ".local/create.hmod"
    if args.java_source:
        check_assets(pack, args.java_source)
    actual = []
    env = {"CREATE_FLYWHEEL_TRACE_POS": WHEEL.replace(" ", ",")}
    with fixture_world(args, "Flywheel", render=True, env=env, pack=pack) as control:
        control.command(f"/setblock {WHEEL} create:flywheel[axis=x]")
        control.command(f"/setblock {SHAFT} create:shaft[axis=x]")
        control.command(f"/setblock {COG} create:cogwheel[axis=x]")
        if args.visual:
            control.command("/time set noon")
            control.command("/setblock 9 107 -10 minecraft:barrier")
            control.call("tp", 9.5, 108, -9.5)
            control.call("look-at", 5.5, 106.5, -10.5)
            control.call("key", "f1", "tap")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
            if tick == 3:
                power(control, 64, place=True)
            elif tick == 26:
                power(control, -64)
            elif tick == 51:
                control.command(f"/setblock {MOTOR} minecraft:air")
            elif tick == 76:
                power(control, 32, place=True)
            if args.visual and tick in (20, 68):
                control.call("wait", 2)
                control.call("screenshot", ROOT / f".local/flywheel-{tick}.png")
        place_by_player(control)

    motion = read_motion(ROOT / ".local/horizon-flywheel.log", start)
    combined = [
        [*row, *motion.get(i, [0.0] * 3 if i == 0 else [])]
        for i, row in enumerate(actual)
    ]
    output = ROOT / ".local/flywheel-horizon.csv"
    with output.open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(combined)
    differences = [
        (java, horizon) for java, horizon in zip(expected, combined, strict=True)
        if java != horizon
    ]
    if differences:
        raise SystemExit(f"Flywheel differed on {len(differences)} ticks (Java, Horizon): "
                         f"{differences[:5]}. See {output}")
    print(f"Flywheel matched all {len(combined)} Java ticks and four survival placement cases.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--java-source", type=Path)
    parser.add_argument("--visual", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())
