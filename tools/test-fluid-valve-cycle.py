#!/usr/bin/env python3
"""Compare the original Fluid Valve opening and closing pointer traces."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
import re
from struct import pack, unpack
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


KEYS = ("rpm", "enabled", "chase_speed", "target", "pointer")
VALVE = "10 170 22"
MOTOR = "9 170 22"
mp = import_module("test-multiplayer")


def float32(value):
    return unpack(">f", pack(">f", float(value)))[0]


def get_number(data, key):
    found = re.search(rf"\b{key}:\s*(-?[\d.]+(?:[eE][+-]?\d+)?)f", data)
    return float32(found[1]) if found else 0.0


def sample(world):
    data = world.command(f"/data get block {VALVE}")
    pointer = re.search(r"\bPointer:\s*\{([^}]+)\}", data)
    enabled = "Test passed" in world.command(f"/execute if block {VALVE} create:fluid_valve[enabled=true]")
    previous = pointer[1] if pointer else ""
    return (
        get_number(re.sub(r"\bPointer:\s*\{[^}]*\}", "", data), "Speed"),
        str(enabled).lower(),
        get_number(previous, "Speed"),
        get_number(previous, "Target"),
        get_number(previous, "Value"),
    )


def verify_frames(viewer, role):
    log = (viewer.socket.parent / "ctl.log").read_text(errors="replace")
    frames = re.findall(
        r"CREATE_FLUID_VALVE_FRAME (-?\d+) ([\d.]+) ([\d.]+) ([\d.]+) ([-\d.]+) (\d+)", log
    )
    checked = [tuple(map(float, frame[1:])) for frame in frames]
    assert checked, f"{role}: the original Valve pointer was never drawn"
    assert all(vertices > 0 for _, _, _, _, vertices in checked)
    assert all(abs(angle - (90.0 - 90.0 * (previous + partial * (current - previous)))) < 0.0002
               for partial, previous, current, angle, _ in checked)
    assert any(previous != current and 0.0 < partial < 1.0 for partial, previous, current, _, _ in checked)
    assert any(current == 0.0 for _, _, current, _, _ in checked)
    assert any(current == 1.0 for _, _, current, _, _ in checked)
    print(f"Fluid Valve {role}: {len(checked)} rendered pointer frames with the original model and expected angles.")


def run(args):
    with (ROOT / "fixtures/fluid_valve_cycle-java.csv").open() as source:
        cases = list(csv.DictReader(source))
    env = {"HORIZON_NO_AUDIO": "1"}
    visual = args.visual or args.lan
    if visual:
        env["CREATE_FLUID_VALVE_RENDER_TRACE"] = "1"
    with ExitStack() as sessions:
        world = sessions.enter_context(fixture_world(
            args, "FluidValveCycle", pack=args.pack, render=visual, env=env))
        viewers = []
        if visual:
            viewers.append(("host" if args.lan else "solo", "@s", world))
        if args.lan:
            port = world.call("lan", "open", "0", "commands")["port"]
            scratch = Path(sessions.enter_context(TemporaryDirectory(prefix="hc-valve-", dir="/private/tmp")))
            guest = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", "ValveGuest", render=True,
                scenario="fluid-valve-cycle", pack=args.pack, env=env,
            ))
            mp.until("Valve guest to join", lambda: any(
                entry["name"] == "ValveGuest" and entry["placed"]
                for entry in world.call("lan", "status")["guests"]))
            viewers.append(("guest", "ValveGuest", guest))
        for _, player, viewer in viewers:
            world.commands((f"/gamemode spectator {player}", f"/tp {player} 12.5 172.5 25.5"))
            mp.until("Valve observer to reach the camera location", lambda:
                     viewer.call("state")["player"]["position"] == [12.5, 172.5, 25.5])
            viewer.call("look-at", 10.5, 170.7, 22.5)
        world.command(f"/setblock {VALVE} create:fluid_valve[facing=up,axis_along_first=true]")
        for _ in range(3):
            world.step_to(world.clock() + 1)
        start = world.clock() - int(cases[0]["tick"])
        comparisons = []
        for row in cases:
            tick = int(row["tick"])
            if tick > int(cases[0]["tick"]):
                world.step_to(start + tick)
            if tick == 4:
                world.command(f"/setblock {MOTOR} create:creative_motor[facing=east]{{ScrollValue:64}}")
            elif tick == 13:
                world.command(f"/data merge block {MOTOR} {{ScrollValue:-64}}")
            wanted = tuple(row[key] if key == "enabled" else float32(row[key]) for key in KEYS)
            comparisons.append((tick, wanted, sample(world)))
            for role, _, viewer in viewers:
                viewer.call("wait", 3)
                if tick in (9, 21):
                    state = "open" if tick == 9 else "closed"
                    viewer.call("screenshot", ROOT / f".local/fluid-valve-{role}-{state}.png")
        for role, _, viewer in viewers:
            verify_frames(viewer, role)
    trace = ROOT / ".local/fluid_valve_cycle-horizon.csv"
    with trace.open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(("tick", *KEYS))
        writer.writerows((tick, *actual) for tick, _, actual in comparisons)
    differences = [row for row in comparisons if row[1] != row[2]]
    if differences:
        raise AssertionError(f"{len(differences)} Fluid Valve Java mismatches: {differences[:8]}. Trace: {trace}")
    print(f"Fluid Valve: all {len(comparisons)} Java speed, enabled and pointer rows match.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--lan", action="store_true")
    run(parser.parse_args())
