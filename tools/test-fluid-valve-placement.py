#!/usr/bin/env python3
"""Compare Valve placement from each original view direction and sneak state."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


mp = import_module("test-multiplayer")
VALVE = "create:fluid_valve"
TARGET = (10, 170, 22)
SUPPORT = (10, 169, 22)
FACING_AXES = {"east": "x", "west": "x", "up": "y", "down": "y", "north": "z", "south": "z"}

NEIGHBORS = {
    "shaft_north": ((10, 170, 21, "create:shaft[axis=z]"),),
    "shaft_east": ((11, 170, 22, "create:shaft[axis=x]"),),
    "pipe_east": ((11, 170, 22, "create:fluid_pipe"),),
    "glass_east_x": ((11, 170, 22, "create:glass_fluid_pipe[axis=x]"),),
    "glass_east_z": ((11, 170, 22, "create:glass_fluid_pipe[axis=z]"),),
    "encased_east": ((11, 170, 22, "create:encased_fluid_pipe"),),
    "pump_east_west": ((11, 170, 22, "create:mechanical_pump[facing=west]"),),
    "smart_pipe_east_west": ((11, 170, 22, "create:smart_fluid_pipe[facing=west]"),),
    "tank_east": ((11, 170, 22, "create:fluid_tank"),),
    "cauldron_east": ((11, 170, 22, "minecraft:water_cauldron"),),
    "shaft_north_pipe_south": (
        (10, 170, 21, "create:shaft[axis=z]"),
        (10, 170, 23, "create:fluid_pipe"),
    ),
    "water_source": (),
    "water_flow": (),
}



def run(args):
    fixture = "fluid_valve_neighbors" if args.neighbors else "fluid_valve_placement"
    with (ROOT / f"fixtures/{fixture}-java.csv").open() as source:
        cases = list(csv.DictReader(source))
    env = {"HORIZON_NO_AUDIO": "1"}
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(
            args, "FluidValvePlacement", pack=args.pack, render=not args.lan, env=env))
        actor, player = host, "@s"
        if args.lan:
            player = "ValvePlacement"
            port = host.call("lan", "open", "0", "commands")["port"]
            scratch = Path(sessions.enter_context(TemporaryDirectory(prefix="hc-valve-", dir="/private/tmp")))
            actor = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario="fluid-valve-placement", pack=args.pack, env=env,
            ))
            mp.until("Valve guest to join", lambda: any(
                entry["name"] == player and entry["placed"]
                for entry in host.call("lan", "status")["guests"]))
        host.commands((
            f"/gamemode survival {player}",
            "/fill 7 169 20 13 169 27 minecraft:stone",
            "/fill 7 170 20 13 175 27 minecraft:air",
        ))
        mismatches = []
        for case in cases:
            yaw, pitch = case["yaw"], case.get("pitch", "90")
            if args.neighbors:
                host.commands(("/fill 9 170 21 11 170 23 minecraft:air",))
                for x, y, z, state in NEIGHBORS[case["neighbor"]]:
                    host.commands((f"/setblock {x} {y} {z} {state}",))

            start = "12.5 170 24.5" if case.get("neighbor") == "shaft_north_pipe_south" else "10.5 170 25.5"
            host.commands((
                "/setblock 10 170 22 minecraft:air",
                f"/tp {player} {start} {yaw} {pitch}",
                f"/item replace entity {player} hotbar.0 with {VALVE}",
            ))
            mp.until("the Valve stack to reach the actor", lambda: mp.count(actor, VALVE) == 1)
            actor.call("select", VALVE)
            sneak = case.get("sneaking", "false") == "true"
            if sneak:
                actor.call("key", "shift", "down")
            try:
                actor.call("wait", 4)
                if case.get("neighbor") in {"water_source", "water_flow"}:
                    level = int(case["neighbor"] == "water_flow")
                    host.commands((f"/setblock 10 170 22 minecraft:water[level={level}]",))
                actor.call("interact", *SUPPORT, "up")
                placed = mp.until("the Valve to be placed", lambda:
                                  (block := host.call("block", *TARGET))["block"] == VALVE and block)
            finally:
                if sneak:
                    actor.call("key", "shift", "up")
            properties = dict(part.split("=", 1) for part in placed["state"].split("[", 1)[1][:-1].split(","))
            expected = {
                "facing": case.get("facing", "up"),
                "axis_along_first": case["first"],
                "enabled": case.get("enabled", "false"),
                "waterlogged": case.get("waterlogged", "false"),
            }
            axes = [axis for axis in "xyz" if axis != FACING_AXES[properties["facing"]]]
            pipe = int(properties["axis_along_first"] == "true")
            if (properties != expected or axes[pipe] != case["pipe_axis"]
                    or ("shaft_axis" in case and axes[1 - pipe] != case["shaft_axis"])):
                mismatches.append((case, properties))
            print(f"Valve placement: {case} -> {properties}")
        assert not mismatches, mismatches
    print(f"All {len(cases)} original Valve placement states matched.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--neighbors", action="store_true")
    run(parser.parse_args())
