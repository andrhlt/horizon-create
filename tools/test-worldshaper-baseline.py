#!/usr/bin/env python3
"""Exercise creative acquisition, rejection, settings and Worldshaper save/reopen."""
import argparse
from contextlib import contextmanager
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
editor = import_module("test-worldshaper-screen")
creative = import_module("test-create-creative-lan")
ITEM = editor.ITEM
GUEST = "ShaperBaseline"
ENV = {"HORIZON_NO_AUDIO": "1"}
BASE = (10, 170, 22)
FILLED = (10, 170, 23)


@contextmanager
def actor_session(args, host, phase):
    if not args.lan:
        yield host, "@s"
        return
    port = host.call("lan", "open", 0, "commands", "force")["port"]
    with TemporaryDirectory(prefix="hc-shaper-baseline-") as scratch:
        with mp.joined_client(args, Path(scratch), f"127.0.0.1:{port}", GUEST,
                              render=True, scenario=f"shaper-baseline-{phase}",
                              pack=args.pack, env=ENV) as guest:
            mp.until("the Worldshaper guest", lambda: any(
                p["name"] == GUEST and p["placed"]
                for p in host.call("lan", "status")["guests"]))
            yield guest, GUEST


def held(host, player):
    return host.command(f"/data get entity {player} SelectedItem").split("following entity data: ")[-1]


def block_pair(host, actor, expected):
    for control in (host, actor):
        mp.until("the edited blocks to agree", lambda: [
            control.call("block", *pos)["block"] for pos in (BASE, FILLED)] == expected)


def shoot(host, actor, target):
    actor.call("look-at", *(value + 0.5 for value in target))
    mp.until("the Worldshaper target", lambda:
             (actor.call("looking-at").get("block") or {}).get("pos") == list(target))
    actor.call("mouse", "right", "click")
    for _ in range(4):
        host.step_to(host.clock() + 1)


def configure(host, actor, player, tool, placement):
    editor.open_editor(actor)
    actor.call("click-at", *editor.widget(actor, tool))
    actor.call("click-at", *editor.widget(actor, placement))
    actor.call("click-at", *editor.widget(actor, "Confirm"))
    mp.until("the editor to close", lambda: actor.call("state")["screen"] == "playing")
    mp.until("the server settings", lambda:
             f'"create:shaper_tool": "{tool.lower()}"' in held(host, player)
             and f'"create:shaper_placement_options": "{placement.lower()}"' in held(host, player))


def run(args):
    with (ROOT / "fixtures/worldshaper_selection-java.csv").open() as source:
        stone = next(row for row in csv.DictReader(source) if row["case"] == "stone")
    with fixture_world(args, "WorldshaperBaseline", render=not args.lan,
                       pack=args.pack, env=ENV) as host:
        with actor_session(args, host, "idle") as (actor, player):
            host.call("command", f"/gamemode creative {player}")
            host.commands((
                "/fill 6 169 20 14 169 28 minecraft:stone",
                "/fill 6 170 20 14 175 28 minecraft:air",
                "/setblock 10 170 22 minecraft:stone",
                f"/tp {player} 10.5 170 25.5",
            ))
            mp.until("Creative mode", lambda: actor.call("state")["gamemode"] == "creative")
            x, y = creative.creative_grid(actor)
            matches = creative.search(actor, x, y, "worldshaper")
            item = next(w for w in matches if w["stack"]["item"] == ITEM)
            left, top, *_ = item["bounds"]
            actor.call("scroll-at", left + 8, top + 8, 0)
            actor.call("key", "1", "tap")
            actor.call("close")
            mp.until("the Creative inventory Worldshaper", lambda: mp.count(actor, ITEM) == 1)
            actor.call("select", ITEM)
            mp.until("the acquired stack on the server", lambda: ITEM in held(host, player))
            inventory = actor.call("inventory")["counts"]
            # Java TerrainTools does not charge materials. Missing selection/settings,
            # rather than an invented survival cost, is the applicable rejection.
            assert "create:shaper_brush_params" not in held(host, player)
            shoot(host, actor, BASE)
            block_pair(host, actor, ["minecraft:stone", "minecraft:air"])
            configure(host, actor, player, "Fill", "Attached")
            assert "create:shaper_block_used" not in held(host, player)
            shoot(host, actor, BASE)
            block_pair(host, actor, ["minecraft:stone", "minecraft:air"])
            assert actor.call("inventory")["counts"] == inventory
            # Add an unrelated component to check selection/editor preservation too.
            host.command(f'/item replace entity {player} hotbar.0 with {ITEM}[minecraft:custom_data={{marker:17}}]')
            actor.call("select", ITEM)
            mp.until("the marked stack", lambda: "marker" in str(actor.call("inventory")["hotbar"][0]))
            editor.selection.select(host, actor, player, BASE, stone, 0.3)
            configure(host, actor, player, "Fill", "Attached")
            saved = held(host, player)
            assert '"create:shaper_brush_params": [I; 1, 1, 1]' in saved, saved
            assert mp.count(actor, "minecraft:stone") == 0
            print("Creative acquisition and two missing-configuration/selection rejections passed.")
        host.restart()
        with actor_session(args, host, "fill") as (actor, player):
            mp.until("the idle held settings", lambda: held(host, player) == saved)
            actor.call("select", ITEM)
            block_pair(host, actor, ["minecraft:stone", "minecraft:air"])
            shoot(host, actor, BASE)
            block_pair(host, actor, ["minecraft:stone", "minecraft:stone"])
            assert mp.count(actor, ITEM) == 1
            assert mp.count(actor, "minecraft:stone") == 0
            assert held(host, player) == saved
            print("Idle reopen retained selected Stone and 1×1×1 Attached Fill; zero-material Fill passed.")
        host.restart()
        with actor_session(args, host, "clear") as (actor, player):
            mp.until("the post-fill held settings", lambda: held(host, player) == saved)
            actor.call("select", ITEM)
            block_pair(host, actor, ["minecraft:stone", "minecraft:stone"])
            configure(host, actor, player, "Clear", "Merged")
            shoot(host, actor, FILLED)
            block_pair(host, actor, ["minecraft:stone", "minecraft:air"])
            saved = held(host, player)
            assert mp.count(actor, ITEM) == 1
            assert mp.count(actor, "minecraft:stone") == 0
            assert not actor.call("entities", 8, "minecraft:item")["entities"]
            print("Post-fill reopen retained the edit; bounded Clear agreed on host and actor without drops.")
        host.restart()
        with actor_session(args, host, "cleared") as (actor, player):
            mp.until("the Clear settings after reopen", lambda: held(host, player) == saved)
            block_pair(host, actor, ["minecraft:stone", "minecraft:air"])
            assert mp.count(actor, ITEM) == 1
            assert mp.count(actor, "minecraft:stone") == 0
            print("Post-clear reopen retained the world, selected material, Clear settings and stack counts.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    run(parser.parse_args())
