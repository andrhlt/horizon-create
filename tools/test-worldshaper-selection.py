#!/usr/bin/env python3
"""Replay original Worldshaper block selection in a real Horizon world."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
ITEM = "create:handheld_worldshaper"


def select(host, actor, player, pos, expected, aim_height):
    original = host.call("block", *pos)["state"]
    x, y, z = pos
    actor.call("look-at", x + 0.5, y + aim_height, z + 0.5)
    mp.until("the Worldshaper to aim at the block", lambda:
             (actor.call("looking-at").get("block") or {}).get("pos") == list(pos))
    actor.call("mouse", "left", "click")
    def selected_item():
        return host.command(f"/data get entity {player} SelectedItem")
    def selected():
        data = selected_item()
        return expected["component_id"] in data and f'Name: "{expected["name"]}"' in data
    try:
        mp.until("the Worldshaper to store the selected block", selected)
    except RuntimeError as error:
        raise AssertionError((selected_item(), host.call("block", *pos))) from error
    item = selected_item()
    properties = ("facing", "half", "shape", "waterlogged")
    assert "marker: 17" in item, item
    assert all(f'{prop}: "{expected[prop]}"' in item for prop in properties if expected[prop]), item
    assert host.call("block", *pos)["state"] == original, original
    mp.until("the actor to keep the selected block visible", lambda:
             actor.call("block", *pos)["state"] == original)
    assert mp.count(actor, ITEM) == int(expected["item_count"])


def fill(host, actor, player, long_range, range_boundary):
    with (ROOT / "fixtures/worldshaper_fill-java.csv").open() as source:
        expected = next(csv.DictReader(source))
    saved = (ROOT / "fixtures/worldshaper_fill-components-java.snbt").read_text().strip()
    host.command("/setblock 14 170 27 minecraft:barrel")
    host.command(f'/data merge block 14 170 27 {{Items:[{{Slot:0b,id:"{ITEM}",count:1,components:{saved}}}]}}')
    host.command(f"/item replace entity {player} hotbar.0 from block 14 170 27 container.0")
    data = host.command(f"/data get entity {player} SelectedItem")
    assert "create:shaper_brush_params" in data, data
    mp.until("the configured stack to reach the actor", lambda:
             "create:shaper_brush_params" in str(actor.call("inventory")["hotbar"][0]))
    base = (10, 170, 22)
    target = tuple(value + int(expected[f"changed_d{axis}"])
                   for value, axis in zip(base, "xyz", strict=True))
    assert host.call("block", *target)["block"] == expected["before"]
    def has_material(pos, block):
        if range_boundary:
            coords = " ".join(map(str, pos))
            return "Test passed" in host.command(f"/execute if block {coords} {block}")
        return host.call("block", *pos)["block"] == block
    if range_boundary:
        host.commands((
            "/forceload add 10 22 10 152",
            "/fill 9 169 149 11 169 153 minecraft:stone",
            "/fill 9 170 24 11 173 152 minecraft:air",
            f"/tp {player} 10.5 170 151.1",
        ))
        mp.until("the actor to stand outside Java range", lambda:
                 abs(actor.call("state")["player"]["position"][2] - 151.1) < 0.001)
        actor.call("look-at", 10.5, 170.5, 22.5)
        actor.call("mouse", "right", "click")
        for _ in range(4):
            host.step_to(host.clock() + 1)
        assert has_material(target, expected["before"])
        host.command(f"/tp {player} 10.5 170 150.9")
        mp.until("the actor to stand within Java range", lambda:
                 abs(actor.call("state")["player"]["position"][2] - 150.9) < 0.001)
    if long_range and not range_boundary:
        host.commands((
            "/fill 9 169 41 11 169 43 minecraft:stone",
            "/fill 9 170 24 11 173 43 minecraft:air",
            f"/tp {player} 10.5 170 42.5",
        ))
        actor.call("wait", 4)
    actor.call("look-at", 10.5, 170.4, 22.5)
    def matching_face():
        hit = actor.call("looking-at").get("block")
        return hit and hit["pos"] == list(base) and hit["face"] == expected["hit_face"]
    if long_range or range_boundary:
        assert actor.call("looking-at").get("block") is None, "Target is within normal block reach"
    else:
        mp.until("the beam to hit the original face", matching_face)
    actor.call("mouse", "right", "click")
    mp.until("the attached Fill cell to match Java", lambda:
             has_material(target, expected["after"]))
    assert has_material(base, "minecraft:stone")
    assert mp.count(actor, ITEM) == int(expected["item_count"])
    if range_boundary:
        print("128-block boundary: the 128.1-block shot missed and the 127.9-block shot filled the Java cell.")
    else:
        print("The original 1×1×1 Attached Fill placed Stone in the same Java cell.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--creative", action="store_true")
    parser.add_argument("--fill", action="store_true")
    parser.add_argument("--long-range", action="store_true")
    parser.add_argument("--range-boundary", action="store_true")
    parser.add_argument("--preserve-rejected", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/worldshaper_selection-java.csv").open() as source:
        cases = {row["case"]: row for row in csv.DictReader(source)}
    env = {"HORIZON_NO_AUDIO": "1"}
    mode = "creative" if args.creative else "survival"
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, "WorldshaperSelection", render=not args.lan,
                                                    pack=args.pack, env=env))
        actor, player = host, "@s"
        if args.lan:
            player = "WorldshaperGuest"
            port = host.call("lan", "open", "0", "commands")["port"]
            scratch = Path(sessions.enter_context(TemporaryDirectory(prefix="hc-worldshaper-")))
            actor = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario="worldshaper-selection", pack=args.pack, env=env,
            ))
            mp.until("the guest to be placed", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]
            ))
        host.call("command", f"/gamemode {mode} {player}")
        host.commands((
            "/fill 6 169 20 14 169 28 minecraft:stone",
            "/fill 6 170 20 14 175 28 minecraft:air",
            f"/tp {player} 10.5 170 25.5",
            "/setblock 10 170 22 minecraft:stone",
            "/setblock 12 170 22 minecraft:oak_stairs[facing=east,half=top,shape=inner_left,waterlogged=true]",
            f"/item replace entity {player} hotbar.0 with {ITEM}[minecraft:custom_data={{marker:17}}]",
        ))
        mp.until("the Worldshaper to be held", lambda: mp.count(actor, ITEM) == 1)
        actor.call("select", ITEM)
        select(host, actor, player, (10, 170, 22), cases["stone"], 0.3)
        select(host, actor, player, (12, 170, 22), cases["stairs"], 0.7)
        if args.preserve_rejected:
            host.command("/setblock 8 170 22 minecraft:chest")
            selected = host.command(f"/data get entity {player} SelectedItem").split("following entity data: ")[-1]
            for pos, kind in (((12, 170, 22), "minecraft:oak_stairs"), ((8, 170, 22), "minecraft:chest")):
                actor.call("look-at", pos[0] + 0.5, pos[1] + 0.7, pos[2] + 0.5)
                mp.until("the selection test block to be targeted", lambda:
                         (actor.call("looking-at").get("block") or {}).get("pos") == list(pos))
                actor.call("mouse", "left", "click")
                actor.call("wait", 4)
                assert host.call("block", *pos)["block"] == kind
                assert actor.call("block", *pos)["block"] == kind
                actual = host.command(f"/data get entity {player} SelectedItem").split("following entity data: ")[-1]
                assert actual == selected, actual
            print("Repeated and rejected selections preserved both blocks and the selected component.")
        if args.fill or args.long_range or args.range_boundary:
            fill(host, actor, player, args.long_range, args.range_boundary)
    print("The original Worldshaper Stone and normalized Oak Stairs selections matched Java.")


if __name__ == "__main__":
    main()
