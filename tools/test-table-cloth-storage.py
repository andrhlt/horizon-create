#!/usr/bin/env python3
"""Exercise physical Table Cloth display storage, persistence, and LAN sync."""
import argparse
import importlib.util
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from fixture_world import fixture_world, ROOT

spec = importlib.util.spec_from_file_location("multiplayer", Path(__file__).with_name("test-multiplayer.py"))
multiplayer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multiplayer)
POS = (9, 95, -9)
ITEMS = ("minecraft:apple", "minecraft:diamond", "minecraft:stick", "minecraft:stone")


def wait(description, test):
    return multiplayer.until(description, test, 10)


def prepare(host, player="@s"):
    host.commands((
        "/fill 4 94 -14 14 94 -4 minecraft:smooth_stone",
        "/fill 4 95 -14 14 97 -4 minecraft:air",
        "/setblock 9 95 -9 create:red_table_cloth",
        f"/tp {player} 9.5 97 -9.5",
        f"/gamemode survival {player}",
    ))


def state(control):
    return control.call("block", *POS)["state"]


def stored(host, items):
    result = host.command("/data get block 9 95 -9 Items")
    if any(item not in result for item in items):
        return False
    offsets = [result.find(item) for item in items]
    return offsets == sorted(offsets) and result.count('id:') == len(items)


def set_hand(host, actor, player, item):
    host.command(f"/item replace entity {player} hotbar.0 with {item}")
    if item != "minecraft:air":
        wait(item + " in hand", lambda: actor.call("inventory")["counts"].get(item, 0) >= 1)
        actor.call("select", item)


def click(actor):
    actor.call("interact", *POS, "up")


def sequence(host, actor, player, *, restart=False):
    for index, item in enumerate(ITEMS):
        set_hand(host, actor, player, item)
        click(actor)
        wait("active cloth", lambda: state(host) == "create:red_table_cloth[entity=true]")
        wait("ordered display inventory", lambda: stored(host, ITEMS[:index + 1]))
        yaw = actor.call("state")["player"]["yaw"]
        facing = (math.floor(yaw / 90 + 0.5) + 2) % 4
        actual = host.command("/data get block 9 95 -9 Facing")
        if not actual.rstrip().endswith(str(facing)):
            raise RuntimeError(f"Expected facing {facing} opposite player yaw {yaw}: {actual}")
        wait("one item inserted", lambda: actor.call("inventory")["counts"].get(item, 0) == 0)
        if restart and index == 1:
            host.restart()
            wait("display after restart", lambda: stored(host, ITEMS[:2]))
    set_hand(host, actor, player, "minecraft:gold_ingot")
    click(actor)
    wait("full display unchanged", lambda: stored(host, ITEMS))
    if actor.call("inventory")["counts"].get("minecraft:gold_ingot") != 1:
        raise RuntimeError("A full display consumed a fifth item")
    actor.call("look-at", 9.5, 95.2, -8.5)
    actor.call("wait", 4)
    screenshot = "table-cloth-items.png" if actor is host else "table-cloth-items-lan.png"
    actor.call("screenshot", ROOT / ".local" / screenshot)
    for index, item in enumerate(reversed(ITEMS)):
        set_hand(host, actor, player, "minecraft:air")
        click(actor)
        wait("last display item returned", lambda: actor.call("inventory")["counts"].get(item, 0) == 1)
        remaining = ITEMS[:len(ITEMS) - index - 1]
        if remaining:
            wait("remaining ordered items", lambda: stored(host, remaining))
        else:
            wait("inactive cloth", lambda: state(host) == "create:red_table_cloth[entity=false]")
            result = host.command("/data get block 9 95 -9")
            if "table_cloth" in result:
                raise RuntimeError(f"Empty cloth retained its block entity: {result}")


def run(args):
    with fixture_world(args, "Table-cloth-storage", render=True, pack=args.pack) as host:
        prepare(host)
        sequence(host, host, "@s", restart=True)
        host.command("/kill @e[type=minecraft:item]")
        for item in ITEMS[:2]:
            set_hand(host, host, "@s", item)
            click(host)
            wait("stored before breaking", lambda: item in host.command("/data get block 9 95 -9 Items"))
        set_hand(host, host, "@s", "minecraft:air")
        host.command("/tp @s 9.5 97 -9.5")
        broken = host.call("break", *POS, "--timeout", 20)
        drops = broken.get("drops", {})
        picked_up = broken.get("picked_up", {})
        for item in ITEMS[:2]:
            if drops.get(item, 0) + picked_up.get(item, 0) != 1:
                raise RuntimeError(f"Breaking the cloth did not drop {item}: {broken}")
    print("Four insertions, full rejection, persistence, LIFO removal, final BE removal, and break drops passed.")


def run_lan(args):
    with fixture_world(args, "Table-cloth-storage-lan", render=True, pack=args.pack) as host:
        port = host.call("lan", "open", 0, "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-cloth-storage-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", "ClothGuest", render=True,
            scenario="table-cloth-storage", pack=args.pack,
        ) as guest:
            wait("guest join", lambda: any(p["name"] == "ClothGuest" and p["placed"] for p in host.call("lan", "status")["guests"]))
            prepare(host, "ClothGuest")
            wait("guest cloth", lambda: state(guest) == "create:red_table_cloth[entity=false]")
            sequence(host, guest, "ClothGuest")
    print("LAN guest insertions, full rejection, and LIFO removal passed against host state.")


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
