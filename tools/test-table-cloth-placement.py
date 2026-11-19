#!/usr/bin/env python3
"""Exercise Table Cloth adjacent placement, blocked edges, and sneak bypass."""
import argparse
from pathlib import Path
from fixture_world import fixture_world
from tempfile import TemporaryDirectory
import importlib.util
import time

spec = importlib.util.spec_from_file_location("multiplayer", Path(__file__).with_name("test-multiplayer.py"))
multiplayer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multiplayer)


def expect(world, pos, expected):
    state = world.call("block", *pos)["state"]
    if state != expected:
        raise RuntimeError(f"Expected {expected} at {pos}, got {state}")


def run(args):
    with fixture_world(args, "Cloth-placement", render=True, pack=args.pack) as world:
        world.commands((
            "/fill 4 94 -14 14 94 -4 minecraft:smooth_stone",
            "/fill 4 95 -14 14 97 -4 minecraft:air",
            "/setblock 9 95 -9 create:red_table_cloth",
            "/tp @s 9.5 97 -9.5",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:blue_table_cloth 4",
        ))
        multiplayer.until("the cloth inventory to reach the player", lambda:
                          world.call("inventory")["counts"].get("create:blue_table_cloth") == 4)
        world.call("select", "create:blue_table_cloth")
        world.call("look-at", 9.5, 95.0625, -8.2)
        world.call("wait", 2)
        hit = world.call("state")["looking_at"]["block"]["point"]
        world.call("mouse", "right", "click")
        neighbors = [(10, 95, -9), (8, 95, -9), (9, 95, -8), (9, 95, -10)]
        placed = multiplayer.until("the adjacent cloth", lambda: [
            pos for pos in neighbors if world.call("block", *pos)["state"] == "create:blue_table_cloth[entity=false]"
        ])
        if len(placed) != 1:
            raise RuntimeError(f"Expected one adjacent cloth, got {placed}")
        def distance(pos):
            return sum((pos[i] + 0.5 - hit[i]) ** 2 for i in range(3))
        if distance(placed[0]) > min(map(distance, neighbors)) + 1e-8:
            raise RuntimeError(f"Cloth landed at {placed[0]}, not the nearest edge to {hit}")
        if world.call("inventory")["counts"].get("create:blue_table_cloth") != 3:
            raise RuntimeError("Adjacent placement did not consume exactly one cloth")
        world.commands((
            "/setblock 10 95 -9 minecraft:stone",
            "/setblock 8 95 -9 minecraft:stone",
            "/setblock 9 95 -8 minecraft:stone",
            "/setblock 9 95 -10 minecraft:stone",
        ))
        world.call("interact", 9, 95, -9, "up")
        expect(world, (9, 96, -9), "minecraft:air")
        if world.call("inventory")["counts"].get("create:blue_table_cloth") != 3:
            raise RuntimeError("Blocked helper consumed a cloth")

        world.command("/setblock 9 95 -10 minecraft:air")
        world.command("/tp @s 9.5 97 -9.5")
        world.call("key", "shift", "down")
        world.call("wait", 4)
        if not world.call("state")["player"]["sneaking"]:
            raise RuntimeError("Player did not enter the sneaking state")
        world.call("interact", 9, 95, -9, "up")
        world.call("key", "shift", "up")
        expect(world, (9, 95, -10), "minecraft:air")
        expect(world, (9, 96, -9), "create:blue_table_cloth[entity=false]")
        if world.call("inventory")["counts"].get("create:blue_table_cloth") != 2:
            raise RuntimeError("Sneaking normal placement did not consume exactly one cloth")
    print("Adjacent placement, blocked-edge handling, and sneak bypass passed in survival.")


def run_lan(args):
    with fixture_world(args, "Cloth-placement-lan", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 4 94 -14 14 94 -4 minecraft:smooth_stone",
            "/fill 4 95 -14 14 97 -4 minecraft:air",
            "/setblock 9 95 -9 create:red_table_cloth",
        ))
        port = host.call("lan", "open", 0, "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-cloth-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", "ClothGuest", render=True,
            scenario="table-cloth-placement", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to join", lambda: any(
                p["name"] == "ClothGuest" and p["placed"] for p in host.call("lan", "status")["guests"]
            ))
            host.commands((
                "/tp ClothGuest 9.5 97 -9.5",
                "/gamemode survival ClothGuest",
                "/item replace entity ClothGuest hotbar.0 with create:blue_table_cloth 4",
            ))
            multiplayer.until("guest cloth inventory", lambda: guest.call("inventory")["counts"].get("create:blue_table_cloth") == 4)
            guest.call("select", "create:blue_table_cloth")
            guest.call("interact", 9, 95, -9, "up")
            neighbors = [(10, 95, -9), (8, 95, -9), (9, 95, -8), (9, 95, -10)]
            def placed(control):
                return [pos for pos in neighbors if control.call("block", *pos)["block"] == "create:blue_table_cloth"]
            authoritative = multiplayer.until("host to see adjacent cloth", lambda: placed(host))
            multiplayer.until("guest to see adjacent cloth", lambda: placed(guest) == authoritative)
            if len(authoritative) != 1:
                raise RuntimeError(f"Expected one adjacent cloth, got {authoritative}")
            multiplayer.until("one cloth consumed", lambda: guest.call("inventory")["counts"].get("create:blue_table_cloth") == 3)
            for x, y, z in neighbors:
                host.command(f"/setblock {x} {y} {z} minecraft:stone")
            multiplayer.until("guest to see blocked edges", lambda: all(guest.call("block", *pos)["block"] == "minecraft:stone" for pos in neighbors))
            host.command("/tp ClothGuest 9.5 97 -9.5")
            guest.call("interact", 9, 95, -9, "up")
            time.sleep(0.5)
            expect(host, (9, 96, -9), "minecraft:air")
            if guest.call("inventory")["counts"].get("create:blue_table_cloth") != 3:
                raise RuntimeError("Blocked guest click consumed a cloth")
    print("LAN guest adjacent placement and blocked-edge handling passed on host and guest.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda x: Path(x).resolve())
    parser.add_argument("--pack", type=lambda x: Path(x).resolve())
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    (run_lan if args.lan else run)(args)

if __name__ == "__main__":
    main()
