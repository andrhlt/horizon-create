#!/usr/bin/env python3
"""Compare the original Package damage, cargo, egg, and sound cases in Horizon."""
import argparse
import csv
from importlib import import_module
from math import floor
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

package = import_module("test-package-open")
placement = import_module("test-package-placement")
SELECTOR = "@e[type=create:package,limit=1]"
ITEM = "create:cardboard_package_12x12"
CARGO = (
    '{id:"create:cardboard_package_12x12",count:1,components:{'
    '"create:package_address":"Destruction Fixture","create:package_contents":['
    '{slot:0,item:{id:"minecraft:stone",count:3}},'
    '{slot:2,item:{id:"minecraft:pig_spawn_egg",count:2}}]}}'
)
SKIP = {"fire_once", "fire_twice"}
DAMAGE = {
    "generic": "generic", "fall": "fall", "kill": "generic_kill",
    "void": "out_of_world", "explosion": "explosion",
}


def entities(peer, kind):
    return peer.call("entities", 16, kind)["entities"]


def inventory_drops(peer):
    return sorted(f"{entry['item']['item']}|{entry['item']['count']}"
                  for entry in entities(peer, "minecraft:item"))


def forecast(row, position):
    location = tuple(floor(value) + 0.5 for value in position)
    for cue in row["sounds"].split(";"):
        if cue:
            sound, category, volume, pitch = cue.split("|")
            yield (sound, int(category), location, float(volume), float(pitch))


def step(host):
    host.step_to(host.clock() + 1)


def act(host, actor, name, source, position):
    if source in DAMAGE:
        host.call("command", f"/damage {SELECTOR} 1 minecraft:{DAMAGE[source]}")
        return
    if source == "kill-command":
        host.call("command", f"/kill {SELECTOR}")
        return
    x, y, z = position
    if source == "melee":
        host.call("command", f"/clear {name}")
        placement.editor.wait_for(actor, "the player to attack barehanded", lambda:
            actor.call("inventory")["held"] is None
        )
        actor.call("look-at", x, y + .375, z)
        placement.editor.wait_for(actor, "the original package to be selected by the ray", lambda:
            (actor.call("looking-at").get("entity") or {}).get("type") == "create:package"
            and actor.call("looking-at")["kind"] == "entity"
        )
        actor.call("mouse", "left", "click")
        return
    if source == "blast":
        host.command(f"/summon minecraft:tnt {x + .75} {y + .44} {z} {{fuse:1s,explosion_power:1}}")
        step(host)
        return
    if source in ("water", "waterlogged"):
        cell = tuple(map(floor, position))
        block = "minecraft:water" if source == "water" else "minecraft:oak_stairs[waterlogged=true]"
        host.command(f"/setblock {placement.editor.xyz(cell)} {block}")
        step(host)
        host.call("command", f"/setblock {placement.editor.xyz(cell)} minecraft:air")
        return
    raise AssertionError(source)


def run_case(host, actor, name, row, sounds):
    source = row["source"]
    host.call("command", f"/kill {SELECTOR}")
    host.call("command", "/tp @e[type=minecraft:pig] 44 100 44")
    host.call("command", "/kill @e[type=minecraft:item]")
    placement.teleport(host, actor, name, package.FEET)
    assert package.seed_package(host, actor, name, CARGO) == ITEM
    placement.approach(host, actor, name, placement.DIRECTIONS["north"])
    placement.action(host, actor)
    peers = (host,) if actor is host else (host, actor)
    for peer in peers:
        placement.editor.wait_for(peer, "the intact package to appear", lambda:
            len(placement.witness(peer)) == 1
        )
    initial = placement.witness(host)[0]
    assert initial["health"] == 5, initial
    sounds.extend(forecast(row, initial["pos"]))
    act(host, actor, name, source, initial["pos"])
    target_removed = row["removed"] == "true"
    expected_items = row["items"].split(";") if row["items"] else []

    def matched(peer):
        box = placement.witness(peer)
        return (
            len(box) == int(not target_removed)
            and (not box or box[0]["id"] == initial["id"] and box[0]["health"] == float(row["health"]))
            and inventory_drops(peer) == expected_items
            and len(entities(peer, "minecraft:pig")) == int(row["pigs"])
            and package.playback(peer) == sounds
        )

    for peer in peers:
        try:
            placement.editor.wait_for(peer, f"the original package outcome for {source}", lambda:
                matched(peer)
            )
        except RuntimeError as error:
            raise AssertionError(source, placement.witness(peer), inventory_drops(peer),
                                 entities(peer, "minecraft:pig"), package.playback(peer), row) from error
    print(f"{source}: original removal, spills, egg and audio", flush=True)


def measured(args, scratch):
    with (ROOT / "fixtures/package-destruction-java.csv").open(newline="") as data:
        recorded = list(csv.DictReader(data))
    rows = [row for row in recorded if row["source"] not in SKIP]
    rows.append({**next(row for row in rows if row["source"] == "kill"), "source": "kill-command"})
    if args.case:
        rows = [row for row in rows if row["source"] in args.case]
        assert len(rows) == len(args.case), args.case
    world = "PackageDamageGuest" if args.lan else "PackageDamageHost"
    with fixture_world(args, world, render=True, pack=args.pack) as host:
        host.commands((
            "/fill 4 100 -16 16 100 -4 minecraft:obsidian",
            "/fill 4 101 -16 16 112 -4 minecraft:air",
            f"/setblock {placement.editor.xyz(placement.TARGET)} minecraft:obsidian",
        ))
        with package.filters.actor_for(host, args, scratch if args.lan else None) as (actor, name):
            host.call("command", f"/gamemode survival {name}")
            sounds = []
            for row in rows:
                run_case(host, actor, name, row, sounds)
    print(f"{'Guest' if args.lan else 'Host'} matched {len(rows)} original Package damage/contact cases.")


def main():
    os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-package-damage-") as scratch:
        measured(args, Path(scratch))


if __name__ == "__main__":
    main()
