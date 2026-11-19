#!/usr/bin/env python3
"""Replay Java's connected Worldshaper brushes through the held editor and actual use."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

ui = import_module("test-worldshaper-screen")
mp = import_module("test-multiplayer")
selection = import_module("test-worldshaper-selection")
ITEM = ui.ITEM
BASE = (-12, 112, -9)
ENV = {"HORIZON_NO_AUDIO": "1"}


def observe(host, offsets):
    result = {}
    for start in range(0, len(offsets), 80):
        batch = offsets[start:start + 80]
        script = "".join(f"block {BASE[0]+x} {BASE[1]+y} {BASE[2]+z}\n" for x, y, z in batch)
        result.update((offset, block["block"]) for offset, block in zip(batch, host.call("script", script=script), strict=True))
    return result


def run(args, scratch):
    with (ROOT / "fixtures/worldshaper_surface_cluster-java.csv").open() as source:
        cases = list(csv.DictReader(source))
    with (ROOT / "fixtures/worldshaper_selection-java.csv").open() as source:
        stone = next(row for row in csv.DictReader(source) if row["case"] == "stone")
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, "WorldshaperConnected", render=not args.lan,
                                                    pack=args.pack, env=ENV))
        actor, player = host, "@s"
        if args.lan:
            player = "ShaperConnected"
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            actor = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario="worldshaper-connected", pack=args.pack, env=ENV))
            mp.until("the guest to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]))
        host.command(f"/gamemode survival {player}")
        for name, tool, steps in (("Surface", "Overlay", 3), ("Cluster", "Clear", 4)):
            expected = {(int(row["x"]), int(row["y"]), int(row["z"])): (row["before"], row["after"])
                        for row in cases if row["brush"] == name and row["tool"] == tool}
            assert len(expected) == (23 if name == "Surface" else 5)
            host.commands((
                "/fill 6 169 16 14 169 28 minecraft:stone",
                "/fill 6 170 20 14 175 28 minecraft:air",
                "/setblock 10 170 22 minecraft:gold_block",
                f"/tp {player} 10.5 170 25.5",
                f"/item replace entity {player} hotbar.0 with {ITEM}[minecraft:custom_data={{marker:17}}]",
            ))
            mp.until("the fresh Worldshaper", lambda: "marker" in str(actor.call("inventory")["hotbar"][0]))
            actor.call("select", ITEM)
            selection.select(host, actor, player, (10, 170, 22), {**stone, "name": "minecraft:gold_block"}, 0.3)
            ui.open_editor(actor)
            x, y = ui.widget(actor, "Brush: ")
            actor.call("script", script=f"scroll-at {x} {y} 1\n" * steps)
            mp.until(f"the {name} editor", lambda: any(
                button["label"] == f"Brush: {name}" for button in actor.call("screen")["buttons"]))
            x, y = ui.widget(actor, "Range: ")
            actor.call("script", script=f"scroll-at {x} {y} 1\n" * 3)
            if name == "Cluster":
                actor.call("click-at", *ui.widget(actor, "Follow Diagonals: Off"))
                actor.call("click-at", *ui.widget(actor, "Across Materials: Off"))
            actor.call("click-at", *ui.widget(actor, tool))
            actor.call("click-at", *ui.widget(actor, "Confirm"))
            mp.until("the Worldshaper editor to close", lambda: actor.call("state")["screen"] == "playing")
            params = "4, 1, 1" if name == "Surface" else "4, 0, 0"
            def configured():
                data = host.command(f"/data get entity {player} SelectedItem")
                return all(part in data for part in (
                    f'"create:shaper_brush": "{name.lower()}"',
                    f'"create:shaper_brush_params": [I; {params}]',
                    f'"create:shaper_tool": "{tool.lower()}"',
                    'Name: "minecraft:gold_block"'))
            mp.until(f"the original {name} settings", configured)
            host.commands((
                "/fill -17 107 -14 -7 117 -4 minecraft:air",
                "/setblock -12 110 -6 minecraft:stone",
                "/setblock -12 112 -9 minecraft:stone",
                f"/tp {player} -11.5 111 -5.5",
            ))
            if name == "Surface":
                host.commands(("/fill -14 110 -9 -10 114 -9 minecraft:stone",
                               "/setblock -11 112 -9 minecraft:dirt",
                               "/setblock -13 112 -8 minecraft:obsidian"))
            else:
                host.commands(("/setblock -13 113 -9 minecraft:stone", "/setblock -14 114 -9 minecraft:stone",
                               "/setblock -11 111 -9 minecraft:dirt", "/setblock -10 110 -9 minecraft:stone",
                               "/setblock -12 112 -10 minecraft:bedrock", "/setblock -12 112 -11 minecraft:stone"))
            mp.until("the actor to reach the target", lambda:
                     actor.call("state")["player"]["position"] == [-11.5, 111.0, -5.5])
            actor.call("look-at", -11.5, 112.5, -8.5)
            mp.until("the south face of the original target", lambda:
                     (hit := actor.call("looking-at").get("block")) and hit["pos"] == list(BASE) and hit["face"] == "south")
            offsets = [(x, y, z) for x in range(-5, 6) for y in range(-5, 6) for z in range(-5, 6)]
            before = observe(host, offsets)
            assert all(before[offset] == pair[0] for offset, pair in expected.items())
            actor.call("mouse", "right", "click")
            first = next(iter(expected))
            mp.until(f"the first {name} cell to change", lambda:
                     host.call("block", *(value + delta for value, delta in zip(BASE, first, strict=True)))["block"] == expected[first][1])
            after = observe(host, offsets)
            changed = {offset: (before[offset], after[offset]) for offset in offsets if before[offset] != after[offset]}
            assert changed == expected, (name, expected.keys() - changed.keys(), changed.keys() - expected.keys(),
                                         {p: changed[p] for p in changed.keys() & expected.keys() if changed[p] != expected[p]})
            mp.until("the Worldshaper to remain held", lambda: mp.count(actor, ITEM) == 1)
            print(f"{name} {tool}: all {len(expected)} Java changes and the full surrounding volume match.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--lan", action="store_true")
    with TemporaryDirectory(prefix="hc-wsc-", dir="/private/tmp") as scratch:
        run(parser.parse_args(), Path(scratch))
