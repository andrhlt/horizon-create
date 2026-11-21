#!/usr/bin/env python3
"""Check cold idle and running steam boiler/shaft reopen in isolated worlds."""

import argparse
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/fluids/steam_engine.nbt")
BOILER = (4, 98, -11)
SHAFT = (4, 98, -7)
PUMPS = ((6, 98, -11), (6, 98, -10))
LEVER = "/setblock 7 98 -9 minecraft:lever[face=floor,facing=west,powered={}]"


def data(control, pos, path=""):
    suffix = f" {path}" if path else ""
    return control.command(f"/data get block {' '.join(map(str, pos))}{suffix}")


def number(text, key):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", text)
    if not match:
        raise RuntimeError(f"Missing {key} in {text}")
    return float(match[1])


def install(control, *, pump_running):
    control.command("/place template create:gametest/fluids/steam_engine 3 96 -12")
    control.command(LEVER.format("false" if pump_running else "true"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()

    with fixture_world(args, "SteamEngineIdleReopen", STRUCTURE, pack=args.pack,
                       artifact_dir=ROOT / ".local/app-1993") as control:
        install(control, pump_running=False)
        before = data(control, BOILER, "Boiler")
        if int(number(before, "Engines")) != 2 or number(before, "Supply") != 0:
            raise RuntimeError(f"Expected idle two-engine boiler before save: {before}")
        pump_states = [data(control, pos) for pos in PUMPS]
        if any(number(state, "Speed") != 0 for state in pump_states):
            raise RuntimeError(f"Idle setup still drives the water pumps: {pump_states}")
        control.command("/save-all")
        control.restart()
        after = data(control, BOILER, "Boiler")
        if int(number(after, "Engines")) != 2 or number(after, "Supply") != 0:
            raise RuntimeError(f"Idle boiler state changed across cold reopen: {after}")
        pump_states = [data(control, pos) for pos in PUMPS]
        if any(number(state, "Speed") != 0 for state in pump_states):
            raise RuntimeError(f"Water pumps started across idle cold reopen: {pump_states}")
        idle_shaft = data(control, SHAFT)
        if number(idle_shaft, "Speed") != 0:
            raise RuntimeError(f"Idle shaft became powered after reopen: {idle_shaft}")

    with fixture_world(args, "SteamEngineRunningReopen", STRUCTURE, pack=args.pack,
                       artifact_dir=ROOT / ".local/app-1993") as control:
        install(control, pump_running=True)
        origin = control.clock()
        for tick in range(1, 17):
            control.step_to(origin + tick)
        before = data(control, BOILER, "Boiler")
        shaft_before = data(control, SHAFT)
        if number(before, "Supply") <= 0 or number(shaft_before, "Speed") == 0:
            raise RuntimeError(f"Fixture failed to reach running boiler/shaft before save: {before} / {shaft_before}")
        control.command("/save-all")
        control.restart()
        reopened = data(control, BOILER, "Boiler")
        if int(number(reopened, "Engines")) != 2 or number(reopened, "Supply") <= 0:
            raise RuntimeError(f"Running boiler state was lost across cold reopen: {reopened}")
        for _ in range(8):
            control.step_to(control.clock() + 1)
        resumed = data(control, SHAFT)
        if number(resumed, "Speed") == 0 or number(resumed, "EnginePower") <= 0:
            raise RuntimeError(f"Steam engine did not resume after cold reopen: {resumed}")
    print("Idle and running two-engine steam setups retained boiler state and shaft operation after cold reopen.")


if __name__ == "__main__":
    main()
