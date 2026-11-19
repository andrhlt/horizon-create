#!/usr/bin/env python3
"""Replay the eight visible transition ticks of paired carriage ports.

To record the reference, apply java-scheduled-train-fluid-port-trace.patch
and java-train-moving-port-trace.patch in a disposable pinned Create checkout.
Run ./gradlew -PparityMovingPortPreview=fluid runGameTestServer, then copy
run/train-moving-port-preview-test-server/world into run/moving-port-client/saves
as MovingPortReference. Run ./gradlew -PparityMovingPortPreview=fluid runClient.
Set onboardAccessibility:false and pauseOnLostFocus:false in the scratch client
options.txt if needed. Repeat with =item, train-moving-item-port-preview-test-server
and MovingItemPortReference. The actor lines around each switch are the reference.
"""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from math import isclose

from fixture_world import ROOT, fixture_world

REFERENCE = Path(__file__).resolve().parent.parent / "fixtures/train_moving_port_render-java.csv"
schedule = import_module("test-scheduled-station-approach")
train = schedule.train
conductor = schedule.conductor
PORT = (train.X + 3, train.Y + 3, train.Z)
POWER = schedule.coordinates((PORT[0], PORT[1], PORT[2] + 3))


def setup(world, kind):
    schedule.place_train_fluid_port(world)
    if kind == "portable_storage_interface":
        world.commands((
            f"/setblock {schedule.coordinates(PORT)} create:{kind}[facing=south]",
            f"/setblock {schedule.coordinates(schedule.PORTABLE_FLUID_POS)} create:{kind}[facing=north]",
        ))
    world.command(f"/setblock {POWER} minecraft:redstone_block")


def value(reply):
    result = reply.partition("entity data: ")[2]
    if not result:
        raise RuntimeError(reply)
    if result.endswith("f"):
        return float(result[:-1])
    return conductor.entry.snbt(result)


def display(state, dx=0):
    x, y, z = PORT
    return (
        f"@e[type=minecraft:block_display,x={x + dx},y={y},z={z},distance=..0.2,"
        f"nbt={{block_state:{state}}},limit=1]"
    )


def verify(world, row, kind, dx=0):
    block = f'CreateTrain.Blocks[{{BlockState:{{Name:"create:{kind}"}}}}]'
    names = ("ExtensionPrevious", "ExtensionProgress", "MovingPortTarget")
    before, after, target = [
        round(value(result), 6)
        for result in world.commands(f"/data get entity {train.ENTITY} {block}.{name}" for name in names)
    ]
    lit = before == target == after
    expected = [float(row["previous"]), float(row["extension"]), row["lit"] == "true"]
    assert [before, after, lit] == expected, (world.clock(), row, before, after, target)
    middle = f"carriage_{kind}_block_middle"
    if lit:
        middle += "_powered"
    head = f"carriage_{kind}_block_top"
    body_state = f'{{id:"create:{kind}"}}'
    middle_state = f'"create:{middle}"'
    head_state = f'"create:{head}"'
    queries = (
        f"/data get entity {display(body_state, dx)} block_state.properties.extended",
        f"/data get entity {display(middle_state, dx)} transformation.translation[2]",
        f"/data get entity {display(head_state, dx)} transformation.translation[2]",
    )
    replies = world.commands(queries)
    model, collar, tip = (value(reply) if "entity data:" in reply else (query, reply)
                          for query, reply in zip(queries, replies))
    assert model == "true", (world.clock(), model)
    # The original south-facing actor points down the positive Z axis.
    assert isclose(collar, after * 0.5 + 0.375, abs_tol=2e-6), (row, collar)
    assert isclose(tip, after, abs_tol=2e-6), (row, tip)


def exercise(world, actor, who, label, kind):
    x, y, z = PORT
    world.command(f"/gamemode spectator {who}")
    actor.call("key", "f1", "tap")
    with REFERENCE.open() as f:
        reference = list(csv.DictReader(f))
    for row in reference:
        if row["action"]:
            world.command(f"/setblock {POWER} minecraft:{row['action']}")
        world.step_to(world.clock() + 1)
        verify(world, row, kind)
        if row["frame"]:
            world.command(f"/tp {who} {x - 3.5} {y + 2.2} {z + 2.3}")
            actor.call("wait", 3)
            actor.call("look-at", x + .5, y + .5, z + 1.5)
            actor.call("wait", 4)
            actor.call("screenshot", ROOT / f".local/{label}-{row['frame']}.png")
    print(f"Moving train port display state, linear chase, collar and tip matched {len(reference)} Java ticks.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    parser.add_argument("--item", action="store_true", help="use paired Portable Storage Interfaces")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    label = "train-moving-item-port-render" if args.item else "train-moving-port-render"
    kind = "portable_storage_interface" if args.item else "portable_fluid_interface"
    if args.multiplayer:
        label += "-guest"
    with fixture_world(args, label, train.STRUCTURE, render=True, pack=args.pack) as world:
        train.setup(world, after_station=lambda world: setup(world, kind), take_controls=False)
        if not args.multiplayer:
            exercise(world, world, "@s", label, kind)
            return
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        guest = conductor.GUEST
        with TemporaryDirectory(prefix="hc-moving-port-guest-") as scratch, conductor.multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", guest,
            render=True, scenario=label, pack=args.pack,
        ) as actor:
            conductor.multiplayer.until("the moving port guest to join", lambda: any(
                link["name"] == guest and link["placed"] for link in world.call("lan", "status")["guests"]
            ))
            exercise(world, actor, guest, label, kind)


if __name__ == "__main__":
    main()
