#!/usr/bin/env python3
"""Replay the original Flatten mound through the Worldshaper's real settings and use."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

ui = import_module("test-worldshaper-screen")
mp = import_module("test-multiplayer")
connected = import_module("test-worldshaper-connected")
BASE = connected.BASE
ENV = {"HORIZON_NO_AUDIO": "1"}


def expected_cells(row):
    changes = {}
    for cell in row["changed_cells"].split("|"):
        x, y, z, states = cell.split(":", 3)
        before, after = states.split(">", 1)
        changes[(int(x), int(y), int(z))] = (before, after)
    return changes


def run(args, scratch):
    with (ROOT / "fixtures/worldshaper_flatten-java.csv").open() as source:
        cases = list(csv.DictReader(source))
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, "WorldshaperFlatten", render=not args.lan,
                                                    pack=args.pack, env=ENV))
        actor, player = host, "@s"
        if args.lan:
            player = "ShaperFlatten"
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            actor = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario="worldshaper-flatten", pack=args.pack, env=ENV))
            mp.until("the guest to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]))
        host.command(f"/gamemode survival {player}")
        host.commands((
            "/fill 6 169 16 14 169 28 minecraft:stone",
            "/fill 6 170 20 14 175 28 minecraft:air",
            "/setblock 10 170 22 minecraft:stone",
            f"/tp {player} 10.5 170 25.5",
            f"/item replace entity {player} hotbar.0 with {ui.ITEM}[minecraft:custom_data={{marker:17}}]",
        ))
        mp.until("the fresh Worldshaper", lambda: mp.count(actor, ui.ITEM) == 1)
        actor.call("select", ui.ITEM)
        ui.open_editor(actor)
        for label in ("Width: ", "Height: ", "Length: "):
            x, y = ui.widget(actor, label)
            actor.call("script", script=f"scroll-at {x} {y} 1\n" * 6)
        mp.until("the 7 by 7 by 7 Cuboid", lambda: all(
            any(button["label"] == expected for button in actor.call("screen")["buttons"])
            for expected in ("Width: 7", "Height: 7", "Length: 7")))
        actor.call("click-at", *ui.widget(actor, "Flatten"))
        actor.call("click-at", *ui.widget(actor, "Merged"))
        actor.call("click-at", *ui.widget(actor, "Confirm"))
        mp.until("the editor to close", lambda: actor.call("state")["screen"] == "playing")
        def configured():
            data = host.command(f"/data get entity {player} SelectedItem")
            return (all(part in data for part in (
                '"create:shaper_brush": "cuboid"', '"create:placement_pattern": "solid"',
                '"create:shaper_brush_params": [I; 7, 7, 7]', '"create:shaper_tool": "flatten"',
                '"create:shaper_placement_options": "merged"', 'marker: 17'))
                and '"create:shaper_block_used"' not in data)
        mp.until("Flatten settings without a selected block", configured)
        offsets = [(x, y, z) for x in range(-5, 6) for y in range(-5, 6) for z in range(-5, 6)]
        for case in cases:
            if args.case and case["case"] != args.case:
                continue
            host.command("/tick step 4")
            actor.call("wait", 8)
            name = case["case"]
            expected = expected_cells(case)
            host.command("/fill -18 106 -15 -6 118 -3 minecraft:air")
            if name == "up":
                host.commands(("/fill -15 109 -12 -9 112 -6 minecraft:stone",
                               "/fill -13 113 -10 -11 113 -8 minecraft:stone",
                               "/setblock -12 114 -9 minecraft:stone",
                               f"/tp {player} -11.5 116 -8.5"))
                look = (-11.5, 114.5, -8.5)
                hit = (-12, 114, -9)
                feet = (-11.5, 116, -8.5)
            else:
                host.commands(("/fill -12 109 -12 -9 115 -6 minecraft:stone",
                               "/fill -13 111 -10 -13 113 -8 minecraft:stone",
                               "/setblock -14 112 -9 minecraft:stone",
                               "/setblock -18 109 -9 minecraft:stone",
                               f"/tp {player} -17.5 110 -8.5"))
                look = (-13.5, 112.5, -8.5)
                hit = (-14, 112, -9)
                feet = (-17.5, 110, -8.5)
            mp.until("the actor to reach the mound", lambda: all(
                abs(actor.call("state")["player"]["position"][axis] - feet[axis]) < .2
                for axis in (0, 2)))
            actor.call("look-at", *look)
            mp.until(f"the original {name} face", lambda:
                     (block := actor.call("looking-at").get("block")) and block["pos"] == list(hit)
                     and block["face"] == case["hit_face"])
            before = connected.observe(host, offsets)
            assert all(before[pos] == value[0] for pos, value in expected.items())
            mp.until(f"the {name} face immediately before use", lambda:
                     (block := actor.call("looking-at").get("block")) and block["pos"] == list(hit)
                     and block["face"] == case["hit_face"])
            actor.call("mouse", "right", "click")
            first = next(iter(expected))
            try:
                mp.until("the summit to flatten", lambda: host.call("block", *(a + b for a, b in zip(BASE, first)))
                         ["block"] == expected[first][1])
            except RuntimeError:
                pass
            after = connected.observe(host, offsets)
            actual = {pos: (before[pos], after[pos]) for pos in offsets if before[pos] != after[pos]}
            assert actual == expected, (name, expected, actual)
            assert mp.count(actor, ui.ITEM) == 1
            print(f"Flatten {name}: all {len(expected)} Java changes and the surrounding volume match.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--case", choices=("up", "west"))
    with TemporaryDirectory(prefix="hc-wsf-", dir="/private/tmp") as scratch:
        run(parser.parse_args(), Path(scratch))
