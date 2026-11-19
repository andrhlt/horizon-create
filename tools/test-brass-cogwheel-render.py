#!/usr/bin/env python3
"""Capture a motor-driven cased cog and axle at known ticks."""
import argparse
from math import fmod
from pathlib import Path
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world

VARIANTS = (
    "brass_encased_cogwheel", "andesite_encased_cogwheel",
    "andesite_encased_large_cogwheel", "brass_encased_large_cogwheel",
)


def check_assets(pack, java_source, variant):
    client_resources = java_source / "src/main/resources"
    generated_resources = java_source / "src/generated/resources"
    large = "_large_" in variant
    material = variant.split("_", 1)[0]
    gear = "large_cogwheel" if large else "cogwheel"
    side = f"{material}_encased_cogwheel_side{'_connected' if large else ''}"
    assets = (
        f"blockstates/{variant}.json",
        f"models/block/{gear}_shaftless.json",
        "models/block/shaft_half.json",
        f"models/block/encased_{gear}/block_top_bottom.json",
        f"textures/block/{side}.png",
    )
    with ZipFile(pack) as archive:
        for asset in assets:
            name = f"assets/create/{asset}"
            original = client_resources / name
            if not original.exists():
                original = generated_resources / name
            if archive.read(name) != original.read_bytes():
                raise RuntimeError(f"Packed asset differs from Java Create: {name}")


def verify(args):
    if args.frames is not None:
        args.frames.mkdir(parents=True, exist_ok=True)
    variant = args.variant
    large = "_large_" in variant
    world = variant.title().replace("_", "") + "Render"
    with fixture_world(args, world, render=True, pack=args.pack,
                       env={"CREATE_CASED_COG_RENDER": "8,101,-10"}) as control:
        control.commands((
            "/fill 4 100 -15 15 100 -7 minecraft:smooth_stone",
            "/fill 4 101 -15 15 103 -7 minecraft:air",
            "/setblock 7 101 -10 create:creative_motor[facing=east]",
            f"/setblock 8 101 -10 create:{variant}[axis=x,bottom_shaft=true,top_shaft=true]",
            "/data merge block 7 101 -10 {ScrollValue:24}",
            "/time set noon",
            "/tp @s 11.75 101.000 -10.25",
        ))
        control.call("look-at", 8.6, 101.58, -9.5)
        control.call("key", "f1", "tap")
        control.call("wait", 3)
        start = control.clock()
        render_ticks = {}
        for tick in (1, 2, 3, 4, 5, 6):
            control.step_to(start + tick)
            if tick == 4:
                control.command(f"/setblock 8 101 -10 create:{variant}[axis=x,bottom_shaft=true,top_shaft=false]")
            if tick in (2, 3, 5, 6):
                control.call("wait", 2)
                speed = control.command("/data get block 8 101 -10 Speed")
                if not speed.rstrip().endswith("24.0f"):
                    raise RuntimeError(f"Motor failed to power the test cog: {speed}")
                render_ticks[control.clock()] = tick < 4
                if args.frames is not None:
                    control.call("screenshot", args.frames / f"tick-{tick}.png")

    # Java's odd Y + Z phase is zero for the shafts and small gear.
    # The large cog teeth start 11.25 degrees ahead of its shafts.
    observed = {}
    with (ROOT / f".local/horizon-{world.lower()}.log").open() as stream:
        for line in stream:
            fields = line.split()
            if not fields or fields[0] != "CREATE_CASED_COG_FRAME":
                continue
            clock = int(fields[1])
            if clock not in render_ticks:
                continue
            partial, rpm, phase, angle = map(float, fields[2:6])
            gear, bottom, top = map(int, fields[6:9])
            if rpm != 24 or phase != 0 or not gear or not bottom or bool(top) != render_ticks[clock]:
                continue
            gear_phase, gear_angle = map(float, fields[9:]) if len(fields) == 11 else (phase, angle)
            java_gear_phase = 11.25 if large else 0.0
            java_shaft_angle = fmod((clock + partial) * 24 * 3 / 10, 360)
            java_gear_angle = fmod((clock + partial) * 24 * 3 / 10 + java_gear_phase, 360)
            if gear_phase != java_gear_phase or abs(gear_angle - java_gear_angle) >= 0.01 or abs(angle - java_shaft_angle) >= 0.01:
                raise RuntimeError(f"Clock {clock} expected gear/shaft angles {java_gear_angle}/{java_shaft_angle}, got {gear_angle}/{angle}")
            observed[clock] = gear_angle
    if set(observed) != set(render_ticks) or len(set(observed.values())) < 2:
        raise RuntimeError(f"Expected rotating gear and open axle submissions at {render_ticks}, got {observed}")
    print(f"All {len(observed)} rendered ticks matched the Java rotation angle and open shaft geometry.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--variant", choices=VARIANTS, default=VARIANTS[0])
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--frames", type=Path)
    parser.add_argument("--java-source", type=Path)
    args = parser.parse_args()
    if args.java_source is not None:
        check_assets(args.pack or ROOT / ".local/create.hmod", args.java_source, args.variant)
    verify(args)


if __name__ == "__main__":
    main()
