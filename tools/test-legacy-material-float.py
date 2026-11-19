#!/usr/bin/env python3
"""Compare the first eight dropped-item ticks for the two legacy Create metals."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
MATERIALS = ("create:shadow_steel", "create:refined_radiance", "minecraft:iron_ingot")
HEIGHT = 174.5


def query(host, selector, field):
    return host.command(f"/data get entity {selector} {field}").rsplit(" ", 1)[-1]


def void_conversion(args):
    with (ROOT / "fixtures" / "legacy-material-void-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    height = -73.0
    selector = "@e[type=minecraft:item,tag=LegacyVoid,limit=1]"
    with fixture_world(args, "LegacyMaterialVoid", pack=args.pack, render=False,
                       env={"HORIZON_NO_AUDIO": "1"}) as host:
        host.commands(("/setblock 10 168 25 minecraft:stone", "/tp @s 10.5 169 25.5"))
        start = host.clock()
        host.command(f'/summon minecraft:item 10.5 {height} 22.5 '
                     '{Item:{id:"create:chromatic_compound",count:3},Motion:[0d,-0.6d,0d],'
                     'PickupDelay:32767s,Tags:["LegacyVoid"]}')
        differences = []
        for index, row in enumerate(rows):
            tick = int(row["tick"])
            assert tick == index, row
            if tick:
                host.step_to(start + tick)
            item = query(host, selector, "Item.id").strip('"')
            count = int(query(host, selector, "Item.count"))
            numeric = (
                float(query(host, selector, "Pos[1]").removesuffix("d")) - height,
                float(query(host, selector, "Motion[1]").removesuffix("d")),
                float(query(host, selector, "fall_distance").removesuffix("d")),
            )
            flags = tuple(query(host, selector, field) == "1b" for field in ("NoGravity", "Silent"))
            expected = tuple(float(row[field]) for field in ("y", "motion_y", "fall_distance"))
            if ((item, count, *flags) != (row["item"], int(row["count"]),
                                         row["no_gravity"] == "true", row["silent"] == "true")
                    or any(abs(a - b) > 3e-7 for a, b in zip(numeric, expected, strict=True))):
                differences.append((tick, row, item, count, numeric, flags))
        assert not differences, differences[:9]
    print(f"Shadow Steel void conversion matched all {len(rows)} Java samples.")


def run(args):
    with (ROOT / "fixtures" / "legacy-material-float-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    env = {"HORIZON_NO_AUDIO": "1"}
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(
            args, "LegacyMaterialFloat", pack=args.pack, render=False, env=env))
        guest = None
        host.commands(("/fill 8 168 19 16 168 27 minecraft:stone", "/tp @s 10.5 169 25.5"))
        if args.lan:
            port = host.call("lan", "open", "0", "commands")["port"]
            scratch = Path(sessions.enter_context(TemporaryDirectory(prefix="hc-legacy-float-", dir="/private/tmp")))
            guest = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", "LegacyFloatGuest", render=True,
                scenario="legacy-material-float", pack=args.pack, env=env))
            mp.until("the observer to join", lambda: any(
                player["name"] == "LegacyFloatGuest" and player["placed"]
                for player in host.call("lan", "status")["guests"]))
            host.command("/tp LegacyFloatGuest 11.5 169 25.5")
        start = host.clock()
        for slot, name in enumerate(MATERIALS):
            host.command(f'/summon minecraft:item {10.5 + slot * 2} {HEIGHT} 22.5 '
                         f'{{Item:{{id:"{name}",count:1}},Motion:[0d,0d,0d],'
                         f'PickupDelay:32767s,Tags:["LegacyFloat{slot}"]}}')
        latest = 0
        differences = []
        for row in rows:
            tick = int(row["tick"])
            while latest < tick:
                latest += 1
                host.step_to(start + latest)
            slot = MATERIALS.index(row["item"])
            selector = f"@e[type=minecraft:item,tag=LegacyFloat{slot},limit=1]"
            height = float(query(host, selector, "Pos[1]").removesuffix("d")) - HEIGHT
            velocity = float(query(host, selector, "Motion[1]").removesuffix("d"))
            # Vanilla omits the tag when false.
            gravity = query(host, selector, "NoGravity") == "1b"
            expected = float(row["y"]), float(row["motion_y"]), row["no_gravity"] == "true"
            actual = height, velocity, gravity
            if row["item"] == "minecraft:iron_ingot":
                # Horizon's vanilla drag uses a float32 coefficient.
                matches = all(abs(a - b) < 1e-7 for a, b in zip(actual[:2], expected[:2], strict=True))
                matches &= gravity == expected[2]
            else:
                matches = actual == expected
            if not matches:
                differences.append((tick, row["item"], expected, actual))
        assert not differences, differences[:9]
        if guest:
            def visible_metals():
                drops = guest.call("entities", 14, "minecraft:item")["entities"]
                return {entry["item"]["item"]: entry["pos"][1] for entry in drops
                        if entry["item"]["item"] in MATERIALS[:2]} == dict.fromkeys(MATERIALS[:2], HEIGHT)

            mp.until("both floating metals to reach the guest at the original height", visible_metals)
        print(f"Legacy materials: all {len(rows)} Java item-tick observations passed."
              + (" LAN guest saw both metals float." if guest else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--void", action="store_true")
    args = parser.parse_args()
    if args.void:
        void_conversion(args)
    else:
        run(args)
