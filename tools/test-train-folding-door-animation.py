#!/usr/bin/env python3
"""Match Java folding-door panel transforms and station timing on a train."""

import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world, last_command_message, run_command_harness

animation = import_module("test-train-door-animation")
train = animation.train
mp = animation.mp
GUEST = "FoldDoorViewer"
NORTH_SOUTH = (
    ("andesite", "north", "left", -1),
    ("copper", "south", "right", 1),
)
EAST_WEST = (
    ("andesite", "east", "left", -1),
    ("copper", "west", "right", 1),
)
HALVES = ("lower", "upper")


def place_doors(world, doors):
    x, y, z = train.X + 4, train.Y + 3, train.Z
    for kind, facing, hinge, dz in doors:
        replies = world.commands((
            f"/setblock {x} {y - 1} {z + dz} minecraft:oak_planks",
            f"/setblock {x} {y} {z + dz} create:{kind}_door[facing={facing},hinge={hinge},half=lower]",
            f"/setblock {x} {y + 1} {z + dz} create:{kind}_door[facing={facing},hinge={hinge},half=upper]",
        ))
        for dy in range(2):
            info = world.call("block", x, y + dy, z + dz)
            assert info["block"] == f"create:{kind}_door", (replies, info)
    world.command(
        f"/summon minecraft:marker {x + .5} {y - 1} {z + .5} "
        "{CreateSuperGlue:1b,From:[-0.5d,0d,-1.5d],To:[0.5d,3d,1.5d]}"
    )


def panel_paths(dz, dy):
    x, y, z = train.X + 4, train.Y + 3 + dy, train.Z + dz
    mounted = f"CreateTrain.Blocks[{{Pos:[I;3,{2 + dy},{dz}]}}]"
    selector = (f"@e[type=minecraft:block_display,x={x},y={y},z={z},distance=..0.2,"
                "nbt={transformation:{scale:[1.0f,1.0f,1.0f]}},limit=1,sort=nearest]")
    return (
        f"/data get entity {train.ENTITY} {mounted}.CreateElevatorDoorProgress",
        f"/data get entity {train.ENTITY} {mounted}.BlockState.Properties.open",
        f"/data get entity {selector} block_state",
        *(f"/data get entity {selector} transformation.translation[{axis}]" for axis in range(3)),
        *(f"/data get entity {selector} transformation.{part}_rotation[{axis}]"
          for part in ("left", "right") for axis in range(4)),
    )


def check_panel(replies, row, kind, dy):
    label = (row["step"], kind, row["facing"], row["hinge"], row["half"])
    progress = animation.number(replies[0])
    expected_progress = float(row["progress"])
    assert isclose(progress, expected_progress, abs_tol=2e-6), (label, progress, expected_progress)
    assert replies[1].endswith('"false"' if int(row["step"]) < 9 else '"true"'), (label, replies[1])
    state = animation.conductor.entry.snbt(replies[2].partition("entity data: ")[2])
    if isinstance(state, str):
        # Horizon serializes a default display state as its bare ID.
        block, pane = state, "left"
    else:
        block, pane = state["id"], state["properties"]["pane"]
    assert (block, pane) == (f"create:{kind}_door_fold", row["pane"]), (label, state)
    x, y, z, lx, ly, lz, lw, rx, ry, rz, rw = map(animation.number, replies[3:])
    expected = (float(row["x"]), float(row["y"]) - dy, float(row["z"]))
    assert all(isclose(a, b, abs_tol=2e-6) for a, b in zip((x, y, z), expected, strict=True)), (label, (x, y, z), expected)
    assert all(isclose(axis, 0, abs_tol=2e-6) for axis in (lx, lz, rx, rz)), (label, lx, lz, rx, rz)
    qy, qw = ly * rw + lw * ry, lw * rw - ly * ry
    expected_qy, expected_qw = float(row["qy"]), float(row["qw"])
    direction = 1 if qy * expected_qy + qw * expected_qw >= 0 else -1
    assert isclose(qy * direction, expected_qy, abs_tol=2e-6), (label, qy, row)
    assert isclose(qw * direction, expected_qw, abs_tol=2e-6), (label, qw, row)


def watch_guest(world, stack, args, label):
    port = world.call("lan", "open", 0, "commands", "force")["port"]
    scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-folding-doors-")))
    guest = stack.enter_context(mp.joined_client(
        args, scratch, f"127.0.0.1:{port}", GUEST, render=True,
        scenario=label, pack=args.pack, env=animation.ENV,
    ))
    mp.until("the door observer to join", lambda: any(
        player["name"] == GUEST and player["placed"] for player in world.call("lan", "status")["guests"]
    ))
    world.command(f"/tp {GUEST} {train.X + 4.5} {train.Y + 3} {train.Z + 4.5}")
    return guest


def check_reopen(args, world, guest_stack, label, panels, oracle):
    saved_tick = world.clock()
    fully_settled_step = 17 if args.reopen == "open" else 8
    guest_stack.close()
    world.stop()
    game = world.socket.parent / "game"
    queries = ["/time query gametime", *(query for *_, paths in panels for query in paths)]
    records = run_command_harness(args, game, label, (
        {"op": "cmd", "cmd": query} for query in queries
    ), animation.ENV)
    messages = [last_command_message(record) for record in records]
    assert int(messages[0].split()[-2]) == saved_tick, (saved_tick, messages[0])
    first = 1
    for kind, facing, hinge, dy, half, paths in panels:
        end = first + len(paths)
        check_panel(messages[first:end], oracle[(fully_settled_step, facing, hinge, half)], kind, dy)
        first = end
    if args.lan:
        world.open()
        guest = watch_guest(world, guest_stack, args, label)
        guest.call("wait", 2)
        for kind, facing, hinge, dy, half, paths in panels:
            check_panel(world.commands(paths), oracle[(fully_settled_step, facing, hinge, half)], kind, dy)
    print(f"Cold {args.reopen} folding-door states and transforms matched Java at saved tick {saved_tick}.")


def run(args):
    with (ROOT / "fixtures/train-folding-door-animation-java.csv").open(newline="") as source:
        oracle = {(int(row["step"]), row["facing"], row["hinge"], row["half"]): row
                  for row in csv.DictReader(source)}
    doors = EAST_WEST if args.east_west else NORTH_SOUTH
    label = "train-folding-doors-lan" if args.lan else "train-folding-doors"
    if args.east_west:
        label += "-east-west"
    if args.reopen:
        label += f"-{args.reopen}-reload"
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, label, train.STRUCTURE, render=True,
                                                  pack=args.pack, env=animation.ENV))
        train.setup(world, before_glue=lambda host: place_doors(host, doors), take_controls=False)
        listeners = [world]
        guest_stack = stack.enter_context(ExitStack())
        if args.lan:
            listeners.append(watch_guest(world, guest_stack, args, label))
        for _ in range(12):
            world.step_to(world.clock() + 1)
        for listener in listeners:
            listener.call("wait", 3)
        baseline = [animation.cues(listener) for listener in listeners]
        station = " ".join(map(str, train.STATION))
        panels = [(kind, facing, hinge, dy, half, panel_paths(dz, dy))
                  for kind, facing, hinge, dz in doors for dy, half in enumerate(HALVES)]
        for step in range(18):
            if step in (0, 9):
                mode = "NONE" if step == 0 else "ALL"
                world.command(f'/data merge block {station} {{DoorControl:"{mode}"}}')
            world.step_to(world.clock() + 1)
            for kind, facing, hinge, dy, half, paths in panels:
                check_panel(world.commands(paths), oracle[(step, facing, hinge, half)], kind, dy)
            for listener, initial in zip(listeners, baseline, strict=True):
                listener.call("wait", 2)
                expected = dict(open=initial["open"] + (2 if step >= 9 else 0),
                                close=initial["close"] + (2 if step >= 7 else 0))
                assert animation.cues(listener) == expected, (step, listener.socket, expected)
            if args.reopen and step == (9 if args.reopen == "open" else 0):
                check_reopen(args, world, guest_stack, label, panels, oracle)
                return
    print("72 mounted andesite and copper folding-door samples and timed cues matched Java.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--east-west", action="store_true")
    parser.add_argument("--reopen", choices=("open", "closed"))
    run(parser.parse_args())
