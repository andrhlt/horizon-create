#!/usr/bin/env python3
"""Compare Chute output into a Creative Crate with the original 13 ticks."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
ENV = {"HORIZON_NO_AUDIO": "1"}


def run(args, scratch):
    upward = args.upward or args.capacity
    if args.capacity:
        fixture = "upward_chute_capacity"
    else:
        fixture = "creative_crate_upward_chute" if upward else "creative_crate_chute"
    with (ROOT / f"fixtures/{fixture}-java.csv").open() as file:
        rows = list(csv.DictReader(file))
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, "CreativeCrateChute", render=False,
                                                    pack=args.pack, env=ENV))
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            guest = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", "CrateChute", render=True,
                scenario="creative-crate-chute", pack=args.pack, env=ENV))
            mp.until("the guest to join", lambda: any(
                guest_["name"] == "CrateChute" and guest_["placed"]
                for guest_ in host.call("lan", "status")["guests"]))
        else:
            guest = None
        chute_y = 169 if upward else 171
        host.commands((
            "/setblock 9 170 22 " + ("minecraft:chest" if args.capacity else "create:creative_crate"),
            f"/setblock 9 {chute_y} 22 create:chute",
        ))
        if not args.capacity:
            host.command('/data merge block 9 170 22 {Filter:{id:"minecraft:iron_ingot",count:7}}')
        if upward:
            host.commands((
                "/setblock 9 168 22 create:encased_fan[facing=up]",
                "/setblock 9 167 22 create:creative_motor[facing=up]{ScrollValue:256}",
            ))
            for _ in range(3):
                host.step_to(host.clock() + 1)
            fan = host.command("/data get block 9 168 22 Speed")
            assert "256" in fan, fan
        if args.capacity:
            contents = ",".join(f'{{Slot:{slot}b,id:"minecraft:cobblestone",count:{48 if slot == 0 else 64}}}'
                                for slot in range(27))
            host.command(f"/data merge block 9 170 22 {{Items:[{contents}]}}")
        origin = "0.0f" if upward else "1.0f"
        host.command(f'/data merge block 9 {chute_y} 22 '
                     f'{{Item:{{id:"minecraft:gold_ingot",count:5}},ItemPosition:{origin}}}')
        if guest:
            host.command("/tp CrateChute 10.5 170 25.5")
            mp.until("the guest to see the Chute", lambda:
                     guest.call("block", 9, chute_y, 22)["block"] == "create:chute")
        start = host.clock()
        actual = []
        positions = []
        for row in rows:
            tick = int(row["tick"])
            if args.capacity and tick == 8:
                host.command("/item replace block 9 170 22 container.0 with minecraft:gold_ingot 62")
            if args.capacity and tick == 12:
                host.command("/item replace block 9 170 22 container.1 with minecraft:air")
            if tick:
                host.step_to(start + tick)
            chute = host.command(f"/data get block 9 {chute_y} 22")
            if args.capacity:
                for slot, field in enumerate(("first", "second")):
                    box = host.command(f"/data get block 9 170 22 Items[{{Slot:{slot}b}}]")
                    wanted = int(row[field + "_count"])
                    if wanted:
                        assert f'"{row[field]}"' in box and f"count: {wanted}" in box, (tick, field, box)
                    else:
                        assert "Found no elements" in box, (tick, field, box)
            else:
                crate = host.command("/data get block 9 170 22 Filter")
                assert '"minecraft:iron_ingot"' in crate and 'count: 7' in crate, (tick, crate)
            item = re.search(r'\bcount: (\d+)', chute)
            count = int(item[1]) if item else 0
            actual.append(count)
            if upward:
                position = re.search(r"\bItemPosition: (-?[0-9.]+)f", chute)
                assert position, chute
                positions.append(float(position[1]))
        expected = [int(row["held_count"]) for row in rows]
        assert actual == expected, (actual, expected)
        if upward:
            differences = [(row["tick"], row["item_position"], position)
                           for row, position in zip(rows, positions, strict=True)
                           if abs(float(row["item_position"]) - position) > 2e-7]
            assert not differences, differences
        if guest:
            expected_block = "minecraft:chest" if args.capacity else "create:creative_crate"
            assert guest.call("block", 9, 170, 22)["block"] == expected_block
    destination = "full and partially empty Chest" if args.capacity else "Creative Crate and its unchanged filter"
    print(f"Matched all {len(rows)} Java Chute ticks for the {destination}" +
          (" with a LAN observer." if args.lan else "."))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--lan", action="store_true")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--upward", action="store_true")
    modes.add_argument("--capacity", action="store_true")
    with TemporaryDirectory(prefix="hc-crate-chute-", dir="/private/tmp") as scratch:
        run(parser.parse_args(), Path(scratch))
