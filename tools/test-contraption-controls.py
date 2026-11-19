#!/usr/bin/env python3
"""Measure the rotating farming assembly in the original actor controls fixture."""
import argparse
import csv
import math
from pathlib import Path
import re
import struct

from fixture_world import ROOT, fixture_world

BASE = (3, 96, -12)
TEMPLATE = Path("gametest/contraptions/controls.nbt")
BUTTON = (5, 4, 4)
GEARSHIFT = (4, 4, 4)
BEARING = (4, 3, 4)
DIRT = ((4, 1, 6), (2, 1, 4), (4, 1, 2))
CROPS = ((4, 2, 7), (1, 2, 4), (4, 2, 1))
HARVESTER = "create:mechanical_harvester"
PLOUGH = "create:mechanical_plough"
NUMBER = r"(-?[0-9.eE+\-]+)"
POSITION = re.compile(rf"\[{NUMBER}d, {NUMBER}d, {NUMBER}d\]")



def at(pos):
    return tuple(coord + offset for coord, offset in zip(BASE, pos, strict=True))


def sample(control):
    bearing_data, _ = control.commands(
        "/data get block " + " ".join(map(str, at(pos))) for pos in (BEARING, GEARSHIFT)
    )
    seq = control.call("block", *at(GEARSHIFT))["state"]
    button = control.call("block", *at(BUTTON))["state"]
    active = "Running: 1b" in bearing_data or "Running: 1," in bearing_data
    angle_in_nbt = re.search(rf"\bAngle: {NUMBER}f", bearing_data)
    angle = ""
    if active and angle_in_nbt:
        raw = struct.unpack("f", struct.pack("f", float(angle_in_nbt[1])))[0]
        angle = f"{raw:.9f}"
    disabled = re.search(r"\bDisabledActors: \[([^\]]*)\]", bearing_data)
    filters = disabled[1] if disabled else ""
    dirt = [control.call("block", *at(pos))["block"] == "minecraft:farmland" for pos in DIRT]
    crops = [re.search(r"\bage=(\d+)", control.call("block", *at(pos))["state"]) for pos in CROPS]
    state = re.search(r"\bstate=(\d+)", seq)
    return [
        state[1] if state else "missing",
        str("powered=true" in button).lower(),
        angle,
        str(f'"{HARVESTER}"' in filters).lower(),
        str(f'"{PLOUGH}"' in filters).lower(),
        ":".join(str(tilled).lower() for tilled in dirt),
        ":".join(age[1] if age else "missing" for age in crops),
    ]


def click_actor_control(control, kind):
    selector = f'@e[type=minecraft:interaction,tag=create_actor_controls,nbt={{CreateActorFilter:"{kind}"}},limit=1]'
    reply = control.command(f"/data get entity {selector} Pos")
    position = POSITION.search(reply)
    if not position:
        raise RuntimeError(f"Cannot find the moving control for {kind}. {reply}")
    px, py, pz = map(float, position.groups())
    cx, _, cz = at(BEARING)
    dx, dz = px - (cx + 0.5), pz - (cz + 0.5)
    radius = math.hypot(dx, dz)
    control.call("tp", px - 2.5 * dz / radius, py + 0.5, pz + 2.5 * dx / radius)
    control.call("look-at", px, py + 0.5, pz)
    time = control.clock()
    control.call("use-item")
    control.call("wait", 2)
    if control.clock() != time:
        raise RuntimeError("The world advanced while dispatching the control click")
    bearing = " ".join(map(str, at(BEARING)))
    result = control.command(f"/data get block {bearing} DisabledActors")
    if f'"{kind}"' not in result:
        raise RuntimeError(f"Clicking the moving control for {kind} did not disable its actor. {result}")


def press(control):
    x, y, z = BASE
    control.call("tp", x+7.5, y+4.0, z+4.5)
    control.call("interact", *at(BUTTON))


def run(args):
    with (ROOT / "fixtures/controls-java.csv").open() as file:
        reader = csv.DictReader(file)
        keys = ("tick", "world_time_mod_20", "sequence_state", "button_powered",
                "bearing_angle", "harvester_disabled", "plough_disabled", "tilled_soils", "crop_ages")
        expected = [[row[key] for key in keys] for row in reader][:args.ticks]
    with fixture_world(args, "contraption_controls", TEMPLATE) as control:
        control.command("/gamerule random_tick_speed 0")
        while control.clock() % 20 != int(expected[0][1]):
            control.step_to(control.clock()+1)
        x, y, z = BASE
        control.command(f"/place template create:{TEMPLATE.with_suffix('')} {x} {y} {z}")
        control.command(f"/tp @s {x+6.5} {y+4} {z+4.5}")
        start = control.clock()
        actual = []
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            if tick == 20:
                press(control)
            actual.append([str(tick), str((start+tick)%20), *sample(control)])
            # The GameTest observes the released gearshift, then clicks the control
            # and button in the same callback. The new states appear in the next row.
            if tick in (41, 62, 83) and tick + 1 < len(expected):
                if tick != 83:
                    click_actor_control(control, HARVESTER if tick == 41 else PLOUGH)
                press(control)
    out = ROOT / ".local/controls-horizon.csv"
    with out.open("w",newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(keys)
        writer.writerows(actual)
    mismatches = [(a,b) for a,b in zip(expected,actual,strict=True) if a!=b]
    if mismatches:
        raise SystemExit(f"{len(mismatches)} mismatches in the first {len(expected)} ticks. {mismatches[:6]}. See {out}")
    print(f"All {len(expected)} ticks matched. See {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--ticks", type=int, default=105)
    run(parser.parse_args())
