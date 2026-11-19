#!/usr/bin/env python3
"""Use the real Wrench against both original portable interface blocks."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

wrench = import_module("test-wrench")
multiplayer = import_module("test-multiplayer")
POSITION = wrench.POSITION
GUEST = "PortWrenchGuest"
REFERENCE = Path(__file__).resolve().parent.parent / "fixtures/portable_interface_wrench-java.csv"


def setup(world):
    world.commands((
        "/setblock 8 176 23 minecraft:smooth_stone",
        "/setblock 9 181 23 minecraft:smooth_stone",
        "/setblock 8 178 21 minecraft:smooth_stone",
        "/setblock 8 178 25 minecraft:smooth_stone",
        "/setblock 6 178 23 minecraft:smooth_stone",
        "/setblock 10 178 23 minecraft:smooth_stone",
    ))


def exercise(world, actor, who):
    world.commands((
        f"/gamemode survival {who}",
        f"/item replace entity {who} hotbar.0 with create:wrench",
    ))
    actor.call("wait", 4)
    actor.call("select", "create:wrench")
    x, y, z = POSITION
    with REFERENCE.open() as f:
        reference = list(csv.DictReader(f))
    differences = []
    for row in reference:
        block, before, face = row["block"], row["before"], row["hit"]
        world.command(f"/setblock {x} {y} {z} create:{block}[facing={before}]")
        px, py, pz = (x + 0.5, y + 2.0, z + 0.5) if row["action"] == "pickup" else wrench.APPROACH[face]
        world.command(f"/tp {who} {px} {py} {pz}")
        actor.call("wait", 3)
        if actor is not world:
            def ready():
                block_id, properties = wrench.state(actor.call("block", *POSITION)["state"])
                ax, ay, az = actor.call("state")["player"]["position"]
                height = y + 0.8 <= ay <= py + 0.1 if row["action"] == "pickup" else abs(ay - py) < 0.01
                return (block_id, properties.get("facing")) == (f"create:{block}", before) and (
                    height and abs(ax - px) < 0.01 and abs(az - pz) < 0.01
                )

            multiplayer.until(f"the wrench target {block} {before} {face}", ready)
        if row["action"] == "pickup":
            wrench.sneak_click(actor, (x + 0.5, y + 0.5, z + 0.5))
        else:
            actor.call("interact", *POSITION, face)
        actor.call("wait", 3)
        actual, properties = wrench.state(world.call("block", *POSITION)["state"])
        if row["action"] == "pickup":
            in_inventory = actor.call("inventory")["counts"].get(f"create:{block}")
            if actual != "minecraft:air" or in_inventory != 1:
                differences.append((row, actual, in_inventory))
        elif (actual, properties.get("facing")) != (f"create:{block}", row["after"]):
            differences.append((row, actual, properties))
    if differences:
        raise RuntimeError(f"{len(differences)} Java portable Wrench mismatches: {differences[:4]}")
    print(f"Matching Java Wrench rotation and pickup for both ports across {len(reference)} actions.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    label = "portable-interface-wrench"
    if args.multiplayer:
        label += "-lan"
    with fixture_world(args, label, render=True, pack=args.pack) as world:
        setup(world)
        if not args.multiplayer:
            exercise(world, world, "@s")
            return
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-pwr-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True, scenario=label, pack=args.pack,
        ) as actor:
            multiplayer.until("a guest at the portable interface", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in world.call("lan", "status")["guests"]
            ))
            exercise(world, actor, GUEST)


if __name__ == "__main__":
    main()
