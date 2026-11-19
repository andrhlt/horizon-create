#!/usr/bin/env python3
"""Replay the original mounted extraction with a real comparator and wire.

Apply java-mounted-storage-trace.patch and java-mounted-port-comparator-trace.patch
to pinned Create. Run ./gradlew -PparityMountedComparator=item runGameTestServer
and repeat with =fluid for the two complete detector traces. For the idle
cycle and its last-connected-tick restart, also apply
java-mounted-port-idle-followup.patch and run with =idle and =rescue.
For the disabled pump motor, also apply java-mounted-fluid-idle-trace.patch
and run with =fluid_idle.
"""

import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mounted = import_module("test-mounted-storage")
multiplayer = import_module("test-multiplayer")
FIXTURE_ROOT = Path(__file__).resolve().parent.parent


def coords(pos):
    return " ".join(map(str, pos))


def wire_power(actor, wire):
    state = actor.call("block", *wire)["state"]
    return state.partition("power=")[2].split(",")[0].rstrip("]")


def lever_state(world, operator, at, block, powered):
    command = f"/setblock {coords(at)} {block}{str(powered).lower()}]"
    if operator is world:
        world.command(command)
    else:
        operator.call("command", command)
        multiplayer.until("the server to apply the lever", lambda: (
            f"powered={str(powered).lower()}" in world.call("block", *at)["state"]
        ))


def run(args):
    kind = "fluid" if args.fluid else "item"
    if args.idle or args.rescue:
        kind = "rescue" if args.rescue else "idle"
    if args.idle_fluid:
        kind = "fluid_idle"
    uses_fluid = args.fluid or args.idle_fluid
    scenario = "mounted_fluid_drain" if uses_fluid else "mounted_item_extract"
    x, _ = mounted.SCENARIOS[scenario]
    station = x + 4, 98, -10
    meter = x + 5, 98, -10
    wire = x + 6, 98, -10
    structure = Path(f"gametest/contraptions/{scenario}.nbt")
    with (FIXTURE_ROOT / f"fixtures/mounted_port_comparator_{kind}-java.csv").open() as f:
        rows = list(csv.DictReader(f))
    columns = ("running", "angle", "source", "output", "timer", "comparator", "wire")
    if args.rescue:
        columns += ("source_items", "hopper_items", "received_items")
    diffs = []
    trace = []
    label = f"mounted-{kind}-port-comparator" + ("-lan" if args.multiplayer else "")
    with ExitStack() as controls:
        world = controls.enter_context(fixture_world(
            args, label, structure, render=args.multiplayer, pack=args.pack
        ))
        start = world.clock()
        for tick in range(start + 1, start + (int(rows[0]["world_phase"]) - start) % 20 + 1):
            world.step_to(tick)
        world.commands((
            f"/place template create:{structure.with_suffix('')} {x} 96 -12",
            f"/setblock {coords((meter[0], meter[1] - 1, meter[2]))} minecraft:smooth_stone",
            f"/setblock {coords((wire[0], wire[1] - 1, wire[2]))} minecraft:smooth_stone",
            f"/setblock {coords(wire)} minecraft:redstone_wire",
            f"/setblock {coords(meter)} minecraft:comparator[facing=west]",
        ))
        if args.idle_fluid:
            world.command(f"/setblock {x + 3} 97 -11 minecraft:air")
        if args.idle or args.rescue:
            hopper = (x + 4, 97, -10)
            world.commands((
                f"/setblock {coords((hopper[0], hopper[1] - 1, hopper[2]))} minecraft:redstone_block",
                f"/setblock {coords(hopper)} minecraft:hopper[facing=north,enabled=false]",
            ))
            if "enabled=false" not in world.call("block", *hopper)["state"]:
                raise RuntimeError("The idle fixture requires the powered Hopper to be disabled.")
        operator = world
        if args.multiplayer:
            port = world.call("lan", "open", "0", "commands", "force")["port"]
            name = "BearingMeter"
            scratch = controls.enter_context(TemporaryDirectory(prefix="hc-bmc-"))
            operator = controls.enter_context(multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", name, render=True,
                scenario=label, pack=args.pack,
            ))
            multiplayer.until("the bearing observer to enter", lambda: any(
                player["name"] == name and player["placed"] for player in world.call("lan", "status")["guests"]
            ))
            world.commands((f"/gamemode spectator {name}", f"/tp {name} {x + 5.5} 100 -8.5"))
            multiplayer.until("the actual comparator wire to load", lambda: (
                operator.call("block", *wire)["block"] == "minecraft:redstone_wire"
            ))
        lever = x + 1, 100, -11
        lever_block = "minecraft:lever[face=wall,facing=north,powered="
        lever_state(world, operator, lever, lever_block, False)
        start = world.clock()
        guest_samples = {
            int(current["tick"]) + 1: current["wire"]
            for previous, current in zip(rows, rows[1:])
            if previous["wire"] != current["wire"]
        }
        for row in rows:
            tick = int(row["tick"])
            if tick:
                world.step_to(start + tick)
            bearing = mounted.sample(world, x, uses_fluid)
            timer, output = world.commands((
                f"/data get block {coords(station)} Timer",
                f"/data get block {coords(meter)} OutputSignal",
            ))
            power = wire_power(world, wire)
            actual = (*bearing[:4], mounted.data(timer) or "0", mounted.data(output) or "0", power)
            if args.rescue:
                actual += tuple(bearing[4:])
            expected = tuple(row[key] for key in columns)
            trace.append((tick, *actual))
            error = [
                f"{key}={value}/{wanted}"
                for key, value, wanted in zip(columns, actual, expected, strict=True)
                if value != wanted
            ]
            if error:
                diffs.append((tick, error))
            guest_power = guest_samples.get(tick)
            if args.multiplayer and guest_power == power:
                multiplayer.until("the guest to see the comparator relay", lambda: wire_power(operator, wire) == guest_power)
            if args.rescue and tick == 28:
                remove_power = f"/setblock {hopper[0]} {hopper[1] - 1} {hopper[2]} minecraft:air"
                enable_hopper = f"/setblock {coords(hopper)} minecraft:hopper[facing=north,enabled=true]"
                if operator is world:
                    world.commands((remove_power, enable_hopper))
                else:
                    operator.call("command", remove_power)
                    multiplayer.until("the guest's power removal", lambda: (
                        world.call("block", hopper[0], hopper[1] - 1, hopper[2])["block"] == "minecraft:air"
                    ))
                    operator.call("command", enable_hopper)
                    multiplayer.until("the Hopper to unlock", lambda: (
                        "enabled=true" in world.call("block", *hopper)["state"]
                    ))
            if bearing[0] == "1" and bearing[2] == "0" and bearing[3] == rows[0]["source"]:
                lever_state(world, operator, lever, lever_block, True)
        if args.multiplayer and not diffs and rows[-1]["wire"] == "0":
            world.step_to(world.clock() + 1)
            multiplayer.until("the guest to see the released wire", lambda: wire_power(operator, wire) == "0")
    with (ROOT / f".local/{label}-horizon.csv").open("w") as f:
        writer = csv.writer(f)
        writer.writerow(("tick", *columns))
        writer.writerows(trace)
    if diffs:
        raise RuntimeError(f"{len(diffs)} verified Java samples differ. First {diffs[:10]}, last {diffs[-10:]}.")
    scenario_label = "extraction, disassembly and comparator relay"
    if args.idle or args.idle_fluid:
        scenario_label = "idle release and comparator relay"
    if args.rescue:
        scenario_label = "restart at the last connected tick and comparator relay"
    print(f"Original mounted {scenario_label} matched {len(rows)} Java ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--fluid", action="store_true")
    modes.add_argument("--idle-fluid", action="store_true")
    modes.add_argument("--idle", action="store_true")
    modes.add_argument("--rescue", action="store_true")
    parser.add_argument("--multiplayer", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
