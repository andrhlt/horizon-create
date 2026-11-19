#!/usr/bin/env python3
"""Replay the steady second idle dock of the moving bearing port.

Apply the stationary receiver Java probe and java-mounted-moving-port-render.patch.
Copy the idle GameTest world to run/bearing-port-client/saves/BearingPortActorReference,
then run ./gradlew -PparityBearingPortClient runClient. Align the server and
moving client outputs at the second idle dock's Timer 13, fixture tick 102.
For --fluid, also apply java-mounted-moving-fluid-port-render.patch and
run with -PparityBearingPortClient=fluid and a fresh BearingPortFluidActorReference
save. The measured steady sampled poses are identical for both materials.
"""

import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

m = import_module("test-mounted-storage")
multiplayer = import_module("test-multiplayer")
REFERENCE = Path(__file__).resolve().parent.parent / "fixtures/mounted_moving_port_render-java.csv"
KEYS = ("DisplayUuid", "PortCollarUuid", "PortTipUuid")


def vector(reply):
    value = reply.split("entity data: ", 1)[1]
    return tuple(float(element.strip().removesuffix("f")) for element in value.strip("[]").split(","))


def rotate(q, v):
    x, y, z, w = q
    tx, ty, tz = 2 * (y*v[2] - z*v[1]), 2 * (z*v[0] - x*v[2]), 2 * (x*v[1] - y*v[0])
    return (v[0] + w*tx + y*tz - z*ty,
            v[1] + w*ty + z*tx - x*tz,
            v[2] + w*tz + x*ty - y*tx)


def selector(uuid):
    return f"@e[type=minecraft:block_display,nbt={{UUID:{uuid}}},limit=1]"


def actor_path(kind):
    return f'MovedBlocks[{{BlockState:{{Name:"create:{kind}"}}}}]'


def observe(world, row, bearing, kind):
    actor = actor_path(kind)
    fields = ("ExtensionPrevious", "ExtensionProgress", *KEYS)
    progress, extension, *uuids = [
        m.data(reply) for reply in world.commands(
            f"/data get block {bearing} {actor}.{key}" for key in fields
        )
    ]
    if not progress or not extension or any(not uuid for uuid in uuids) or len(set(uuids)) != 3:
        raise RuntimeError(f"Moving port pose or part identities missing at tick {row['tick']}.")
    values = float(progress.removesuffix("f")), float(extension.removesuffix("f"))
    expected = float(row["previous"]), float(row["extension"])
    assert all(isclose(a, b, abs_tol=2e-6) for a, b in zip(values, expected, strict=True)), (row, values)
    angle = m.java_float(m.data(world.command(f"/data get block {bearing} Angle")))
    assert angle == row["angle"], (row, angle)

    parts = []
    for uuid in uuids:
        pos, left, state = world.commands(
            f"/data get entity {selector(uuid)} {key}" for key in (
                "transformation.translation", "transformation.left_rotation", "block_state"
            )
        )
        parts.append((vector(pos), vector(left), state))
    body, collar, tip = parts
    assert kind in body[2] and "extended" in body[2] and "true" in body[2], body
    collar_name = "block_middle_powered" if row["lit"] == "true" else "block_middle"
    assert f'carriage_{kind}_{collar_name}"' in collar[2], (row, collar)
    assert f'carriage_{kind}_block_top"' in tip[2], tip
    center = rotate(body[1], (0.5, 0.5, 0.5))
    facing = rotate(body[1], (0, 0, -1))
    for (xyz, q, _), offset in zip((collar, tip), (expected[1] * .5 + .375, expected[1]), strict=True):
        part_facing = rotate(q, (0, 1, 0))
        assert all(isclose(a, b, abs_tol=3e-6) for a, b in zip(part_facing, facing, strict=True)), (
            row, part_facing, facing
        )
        local = rotate(tuple((-x if i < 3 else x) for i, x in enumerate(q)),
                       tuple(x - body[0][i] - center[i] for i, x in enumerate(xyz)))
        assert all(isclose(a, b, abs_tol=3e-6) for a, b in zip(local, (-.5, offset - .5, -.5), strict=True)), (
            row, offset, local
        )
    return tuple(uuids)


def run(args):
    x = 3 if args.fluid else 14
    kind = "portable_fluid_interface" if args.fluid else "portable_storage_interface"
    template = "mounted_fluid_drain" if args.fluid else "mounted_item_extract"
    structure = Path(f"gametest/contraptions/{template}.nbt")
    bearing = f"{x + 1} 99 -10"
    actor = actor_path(kind)
    lever = f"/setblock {x + 1} 100 -11 minecraft:lever[face=wall,facing=north,powered="
    label = "mounted-moving-fluid-port-render" if args.fluid else "mounted-moving-port-render"
    if args.multiplayer:
        label += "-lan"
    if args.reload:
        label += "-reload"
    images = args.logs or ROOT / ".local"
    images.mkdir(parents=True, exist_ok=True)
    with REFERENCE.open() as f:
        rows = {int(row["tick"]): row for row in csv.DictReader(f)}
    with ExitStack() as resources:
        world = resources.enter_context(fixture_world(args, label, structure, render=True, pack=args.pack))
        now = world.clock()
        for step in range(now + 1, now + (2 - now) % 20 + 1):
            world.step_to(step)
        world.command(f"/place template create:{structure.with_suffix('')} {x} 96 -12")
        if args.fluid:
            world.command(f"/setblock {x + 3} 97 -11 minecraft:air")
        else:
            world.commands((
                f"/setblock {x + 4} 96 -10 minecraft:redstone_block",
                f"/setblock {x + 4} 97 -10 minecraft:hopper[facing=north,enabled=false]",
            ))
        observer = world
        who = "@s"
        if args.multiplayer:
            port = world.call("lan", "open", "0", "commands", "force")["port"]
            scratch = resources.enter_context(TemporaryDirectory(prefix="hc-movingbearing-"))
            who = "BearingMoving"
            observer = resources.enter_context(multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", who, render=True, scenario=label, pack=args.pack
            ))
            multiplayer.until("the moving bearing observer to enter", lambda: any(
                player["name"] == who and player["placed"] for player in world.call("lan", "status")["guests"]
            ))
        world.commands((f"/gamemode spectator {who}", f"/tp {who} {x + 3.3} 99.6 -13"))
        observer.call("wait", 4)
        observer.call("look-at", x + 3.7, 98.4, -9.5)
        observer.call("key", "f1", "tap")
        world.command(f"{lever}false]")
        now = world.clock()
        first_parts = None
        for tick in range(1, max(rows) + 1):
            world.step_to(now + tick)
            if tick in rows:
                parts = observe(world, rows[tick], bearing, kind)
                if first_parts is None:
                    first_parts = parts
                assert first_parts == parts, f"Moving port part identities changed at tick {tick}."
            if args.reload and tick == 109:
                world.call("save")
                world.restart()
                world.step_to(world.clock() + 1)
                restored = tuple(m.data(reply) for reply in world.commands(
                    f"/data get block {bearing} {actor}.{key}" for key in KEYS
                ))
                assert first_parts == restored, (first_parts, restored)
                for uuid in restored:
                    assert world.command(f"/execute if entity {selector(uuid)}").startswith("Test passed")
                break
            if tick in (104, 107, 109, 116, 119):
                observer.call("wait", 7)
                observer.call("screenshot", images / f"{label}-{tick}.png")
        world.command(f"{lever}true]")
        stop = world.clock()
        for step in range(stop + 1, stop + 4):
            world.step_to(step)
        for uuid in first_parts:
            assert not world.command(f"/execute if entity {selector(uuid)}").startswith("Test passed")
        assert m.data(world.command(f"/data get block {bearing} Running")) == "0b"
    if args.reload:
        print("Moving bearing port parts kept all three saved identities through reload and disassembly.")
    else:
        print(f"Matched {len(rows)} original moving port poses, model parts and disassembly cleanup.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--fluid", action="store_true")
    parser.add_argument("--logs", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--multiplayer", action="store_true")
    mode.add_argument("--reload", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
