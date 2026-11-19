#!/usr/bin/env python3
"""Replay original Nixie dye, text retention, and emitted palette cases."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
import json
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
ORANGE = "create:nixie_tube"
BLUE = "create:blue_nixie_tube"
AT = (8, 120, -8)
OTHER = (9, 120, -8)
CONTROL = (10, 120, -8)
POSITION = [8.25, 120.0, -10.5]
SHAPE = "double_face=floor,facing=east,waterlogged=true"


def coords(at):
    return " ".join(map(str, at))


def records(name):
    with (ROOT / "fixtures" / name).open(newline="") as source:
        return list(csv.DictReader(source))


def prepare(world, commands):
    world.call("script", script="".join(f"command {json.dumps(cmd)}\n" for cmd in commands))


def expected_state(world, at, block, shape=SHAPE):
    return world.command(f"/execute if block {coords(at)} {block}[{shape}]") == "Test passed"


def assert_pack(pack, colors):
    with ZipFile(pack) as contents:
        root = "data/create/"
        for entry in colors:
            id = entry["block"].removeprefix("create:")
            block = json.loads(contents.read(f"{root}horizon/block/{id}.json"))
            loot = json.loads(contents.read(f"{root}loot_table/blocks/{id}.json"))
            assert block["properties"]["light"] == 5, block
            assert block["item"] == (entry["block"] == ORANGE), block
            assert loot["pools"][0]["entries"][0]["name"] == ORANGE, loot
            assert f"assets/create/blockstates/{id}.json" in contents.namelist(), id
        shapes = {}
        fields = ("min_x", "min_y", "min_z", "max_x", "max_y", "max_z")
        for row in records("nixie-shapes-java.csv"):
            shapes.setdefault(f'{row["face"]},{row["facing"]}', []).append([float(row[field]) for field in fields])
        base = json.loads(contents.read(f"{root}horizon/block/nixie_tube.json"))
        assert base["shapes"]["values"] == shapes == base["collision_shapes"]["values"]


def dye(world, actor, name, row):
    held = f'minecraft:{row["dye"]}_dye'
    prepare(world, (
        f"/setblock {coords(AT)} {ORANGE}[{SHAPE}]",
        f"/setblock {coords(OTHER)} {BLUE}[{SHAPE}]",
        f"/setblock {coords(CONTROL)} {ORANGE}[double_face=floor,facing=north,waterlogged=true]",
        f""" /data merge block {coords(OTHER)} {{RawCustomText:'"PARITY"',CustomText:'"PARITY"',CustomTextIndex:1}}""".strip(),
        f"/item replace entity {name} hotbar.0 with {held} 3",
    ))
    multiplayer.until(f"the {row['dye']} dye and initial tubes", lambda:
        (actor.call("inventory")["held"] or {}).get("item") == held
        and actor.call("block", *AT)["block"] == ORANGE
        and actor.call("block", *OTHER)["block"] == BLUE)
    actor.call("look-at", 8.25, 120.43, -7.5)
    hit = actor.call("looking-at").get("block")
    assert hit and hit["pos"] == list(AT), hit
    actor.call("mouse", "right", "click")
    multiplayer.until(f"both Java tubes to become {row['first']}", lambda:
        expected_state(world, AT, row["first"]) and expected_state(world, OTHER, row["second"]))
    assert expected_state(world, CONTROL, row["control"], "double_face=floor,facing=north,waterlogged=true"), row
    multiplayer.until("the actor to see the dyed row", lambda:
        actor.call("block", *AT)["block"] == row["first"]
        and actor.call("block", *OTHER)["block"] == row["second"])
    stack = actor.call("inventory")["held"]
    assert stack["item"] == held and stack["count"] == int(row["held"]), (row, stack)
    data = world.command(f"/data get block {coords(OTHER)}")
    assert re.search(rf'CustomTextIndex: {row["text_index"]}\b', data) and "PARITY" in data, (row, data)


def redstone(world, actor):
    start = world.clock()
    for row in records("nixie-power-java.csv"):
        tick = int(row["tick"])
        if tick:
            world.step_to(start + tick)
        if tick in (0, 2):
            block = "minecraft:redstone_block" if tick == 0 else "minecraft:air"
            world.command(f"/setblock 7 120 -8 {block}")
        current = world.command(f"/data get block {coords(AT)}")
        power = re.search(r"RedstoneStrength: (\d+)", current)
        assert (power[1] if power else "0") == row["power"], (row, current)
        assert row["custom_text"] in world.command(f"/data get block {coords(OTHER)}"), row
    assert actor.call("block", *AT)["block"] == "create:black_nixie_tube"


def harvest(world, actor, name):
    tool = "minecraft:iron_pickaxe"
    candidate = "create:purple_nixie_tube"
    prepare(world, (
        f"/setblock {coords(AT)} {candidate}[{SHAPE.replace('true', 'false')}]",
        f"/item replace entity {name} weapon.mainhand with {tool}",
    ))
    multiplayer.until("the dyed tube and pickaxe to reach the actor", lambda:
        actor.call("block", *AT)["block"] == candidate
        and (actor.call("inventory")["held"] or {}).get("item") == tool)
    assert world.command(f"/execute if block {coords(AT)} #minecraft:mineable/pickaxe") == "Test passed"
    actor.call("look-at", 8.25, 120.43, -7.5)
    actor.call("mouse", "left", "down")
    try:
        for _ in range(40):
            world.step_to(world.clock() + 1)
            if world.command(f"/execute if block {coords(AT)} minecraft:air") == "Test passed":
                break
        else:
            raise AssertionError("The dyed tube did not break with an iron pickaxe.")
    finally:
        actor.call("mouse", "left", "up")
    multiplayer.until("the original orange tube drop", lambda:
        any(stack.get("item") == ORANGE and stack.get("count") == 1
            for drop in actor.call("entities", 7, "minecraft:item")["entities"]
            if (stack := drop.get("item"))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--lan", action="store_true")
    modes.add_argument("--visual", action="store_true")
    args = parser.parse_args()
    os.environ.setdefault("HORIZON_NO_AUDIO", "1")
    colors = records("nixie-colors-java.csv")
    dyes = records("nixie-dye-java.csv")
    assert len(colors) == len(dyes) == 16
    assert_pack(args.pack, colors)
    scenario = "NixieColors" + ("Visual" if args.visual else "LAN" if args.lan else "")
    if args.visual:
        os.environ["HORIZON_CREATE_NIXIE_TRACE"] = "1"
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, scenario, render=args.visual, pack=args.pack))
        prepare(world, (
            "/fill 5 119 -12 13 119 -5 minecraft:smooth_stone",
            "/fill 5 120 -12 13 123 -5 minecraft:air",
        ))
        actor, name = world, "@s"
        if args.lan:
            name = "NixieGuest"
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-nixie-")))
            actor = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, scenario="nixie-colors", pack=args.pack,
            ))
            multiplayer.until("the Nixie operator to join", lambda: any(
                guest["name"] == name and guest["placed"] for guest in world.call("lan", "status")["guests"]
            ))
        prepare(world, (f"/gamemode survival {name}", f"/tp {name} {' '.join(map(str, POSITION))}"))
        multiplayer.until("the Nixie operator to settle", lambda: actor.call("state")["player"]["position"] == POSITION)
        for row in dyes:
            dye(world, actor, name, row)
            if args.visual:
                actor.call("wait", 3)
        redstone(world, actor)
        world.command("/setblock 7 120 -8 minecraft:redstone_wire")
        assert world.command("/execute if block 7 120 -8 minecraft:redstone_wire[east=side]") == "Test passed"
        harvest(world, actor, name)
    print(f"Matched all {len(dyes)} Java dye cases with retained text, dye count, and a geometry control. Four redstone samples and the orange survival drop also matched.")
    if args.visual:
        path = ROOT / f".local/horizon-{scenario.lower()}.log"
        observed = set(re.findall(r"CREATE_NIXIE_PALETTE ([^,\n]+,[0-9a-f]{6},[0-9a-f]{6})", path.read_text()))
        expected = {f'{row["block"]},{row["bright_rgb"]},{row["dark_rgb"]}' for row in colors}
        assert expected <= observed, sorted(expected - observed)
        print(f"Renderer emitted all {len(expected)} original base palettes.")


if __name__ == "__main__":
    main()
