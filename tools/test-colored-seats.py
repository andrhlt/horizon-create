#!/usr/bin/env python3
"""Replay original Java seat crafting, waterlogged recoloring and boarding."""

import argparse
import csv
import json
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world
from prepare import model_references

crafting = import_module("test-machine-crafting")
elevator = import_module("test-multiplayer-elevator")
multiplayer = import_module("test-multiplayer")
GUEST = "SeatGuest"
AT = (9, 171, 21)
FEET = (9.5, 171, 23.5)


def craft(host, row):
    dye = f"minecraft:{row['color']}_dye"
    for recipe, slots, count in (
        ("craft_recipe", f"{row['wool']},minecraft:oak_slab", "craft_count"),
        ("recolor_recipe", f"{dye},{row['source']}", "recolor_count"),
    ):
        crafting.replay(host, {"recipe": row[recipe], "width": "2", "slots": slots,
                               "output": row["block"], "count": row[count], "remainder": ""})


def ride(host, actor, player, rows):
    host.commands((
        "/scoreboard objectives add elevator_ride dummy",
        f"/gamemode survival {player}",
    ))
    for row in rows:
        dye = f"minecraft:{row['color']}_dye"
        host.commands((
            f"/clear {player}",
            f"/tp {player} {' '.join(map(str, FEET))}",
            f"/setblock 9 171 21 {row['source']}[waterlogged=true]",
            f"/item replace entity {player} hotbar.0 with {dye}",
        ))
        multiplayer.until(f"{row['source']} and its dye to synchronize", lambda:
                          actor.call("block", *AT)["block"] == row["source"]
                          and actor.call("inventory")["counts"].get(dye) == 1
                          and actor.call("state")["player"]["position"] == list(FEET))
        actor.call("select", dye)
        actor.call("interact", *AT, "up")
        expected = f"{row['after']}[waterlogged={row['waterlogged']}]"
        for client in (host,) if actor is host else (host, actor):
            multiplayer.until(f"recolored {expected}", lambda:
                              client.call("block", *AT)["state"] == expected)
        dye_count = actor.call("inventory")["counts"].get(dye, 0)
        if dye_count != int(row["dye_count"]):
            raise RuntimeError(f"Java keeps {row['dye_count']} {dye}, Horizon keeps {dye_count}.")
        actor.call("select", 9)
        actor.call("interact", *AT, "up")
        mounted = row["boarded"] == "true"
        multiplayer.until(f"expected mounted state {mounted} for {row['block']}", lambda:
                          elevator.ride(host, player) == mounted)
        if mounted:
            actor.call("key", "shift", "down")
            try:
                actor.call("wait", 3)
                host.step_to(host.clock() + 1)
                multiplayer.until(f"player to dismount from {row['block']}", lambda:
                                  not elevator.ride(host, player))
            finally:
                actor.call("key", "shift", "up")
            host.step_to(host.clock() + 1)


def creative_search(host, rows):
    host.call("open-inventory")
    grid = host.call("ui")["widgets"]
    left, top, *_ = next(widget["bounds"] for widget in grid if widget["id"] == "slot-900")
    host.call("click-at", left + 172, top - 30)
    host.call("type", "seat")
    expected = {row["block"] for row in rows}
    def search_results():
        return {widget["stack"]["item"] for widget in host.call("ui")["widgets"] if widget.get("stack")}
    multiplayer.until("all colored seat items in creative search", lambda: expected <= search_results())
    host.call("close")


def check_assets(pack, java, rows):
    resources = [java / "src" / name / "resources" for name in ("main", "generated")]
    names = [row["block"].split(":", 1)[1] for row in rows]
    pending = [f"{folder}/{name}.json" for folder in ("blockstates", "models/item") for name in names]
    checked = set()
    with ZipFile(pack) as archive:
        while pending:
            name = pending.pop()
            if name in checked:
                continue
            checked.add(name)
            relative = "assets/create/" + name
            source = next(root / relative for root in resources if (root / relative).exists()).read_bytes()
            if source != archive.read(relative):
                raise RuntimeError(f"The seat asset differs from Java: {relative}")
            if name.endswith(".json"):
                pending.extend(model_references(json.loads(source)))
        for row, name in zip(rows, names, strict=True):
            info = json.loads(archive.read(f"data/create/horizon/block/{name}.json"))["properties"]
            actual = info["hardness"], info["explosion_resistance"], info["map_color"]
            expected = float(row["hardness"]), float(row["resistance"]), int(row["map_color"])
            if actual != expected:
                raise RuntimeError(f"Java {name} properties {expected} differ from Horizon {actual}.")
    print(f"All {len(checked)} original seat model, blockstate and texture files match Java.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--craft", action="store_true")
    parser.add_argument("--search", action="store_true")
    parser.add_argument("--java-source", type=Path)
    args = parser.parse_args()
    with (ROOT / "fixtures/colored-seats-java.csv").open() as reference:
        rows = list(csv.DictReader(reference))
    if args.java_source:
        check_assets(args.pack or ROOT / ".local/create.hmod", args.java_source, rows)
    with fixture_world(args, "Colored Seats", render=True, pack=args.pack) as host:
        host.command("/fill 6 170 18 13 170 25 minecraft:stone")
        if args.search:
            creative_search(host, rows)
            print("All 16 Create seat colors appear in the live creative search.")
            return
        if args.craft:
            host.commands((
                "/gamemode survival",
                "/fill 8 169 22 16 169 28 minecraft:stone",
                "/fill 11 170 25 15 170 28 minecraft:air",
                "/setblock 12 170 24 minecraft:crafting_table",
                "/tp @s 12.5 170 26.5",
            ))
            for row in rows:
                craft(host, row)
        elif args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            with TemporaryDirectory(prefix="hc-seat-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                scenario="colored-seats", pack=args.pack,
            ) as guest:
                multiplayer.until("the seat guest to join", lambda: any(
                    p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]
                ))
                ride(host, guest, GUEST, rows)
        else:
            ride(host, host, "@s", rows)
    print(f"Matched Java's 16 seat colors with {'32 original recipes' if args.craft else 'recoloring and boarding'}.")


if __name__ == "__main__":
    main()
