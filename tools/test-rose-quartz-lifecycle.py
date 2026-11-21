#!/usr/bin/env python3
"""Check Rose Quartz palette conversion, drops and persistence in solo or LAN."""

import argparse
from importlib import import_module
from pathlib import Path
from shutil import rmtree
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

crafting = import_module("test-survival-crafting")
multiplayer = import_module("test-multiplayer")

GUEST = "QuartzBuilder"
PALETTES = (
    ("create:rose_quartz_block", "east", (1, 0, 0)),
    ("create:rose_quartz_tiles", "up", (0, 1, 0)),
    ("create:small_rose_quartz_tiles", "south", (0, 0, 1)),
)


def inventory_slot(control, item):
    inventory = control.call("inventory")
    slots = [*inventory["hotbar"], *inventory["main"]]
    return next(entry["slot"] for entry in slots if entry.get("item") == item)


def conversions(actor, player):
    actor.command(f"/gamemode survival {player}")
    actor.commands((
        f"/clear {player}",
        f"/give {player} create:small_rose_quartz_tiles 1",
    ))
    actor.call("open-inventory")
    for source, result in (
        ("create:small_rose_quartz_tiles", "create:rose_quartz_tiles"),
        ("create:rose_quartz_tiles", "create:small_rose_quartz_tiles"),
    ):
        crafting.distribute(actor, inventory_slot(actor, source), (100,))
        crafting.craft(actor, result, 1)
        counts = actor.call("inventory")["counts"]
        if counts.get(result) != 1 or counts.get(source, 0):
            raise RuntimeError(f"The 1:1 palette conversion {source} → {result} left {counts}.")
    actor.call("close")


def place_palettes(host, actor, player):
    positions = []
    for index, (block, face, offset) in enumerate(PALETTES):
        pos = (7 + index * 2, 171, 20)
        support = tuple(cell - step for cell, step in zip(pos, offset, strict=True))
        host.commands((
            f"/setblock {' '.join(map(str, support))} minecraft:stone",
            f"/give {player} {block} 1",
            f"/tp {player} {pos[0] + .5} 171 22.5",
        ))
        multiplayer.until(f"{player} to receive {block}", lambda:
                          multiplayer.count(actor, block) == 1)
        actor.call("select", block)
        actor.call("interact", *support, face)
        multiplayer.until(f"the host to place {block}", lambda:
                          host.call("block", *pos)["block"] == block)
        state = host.call("block", *pos)["state"]
        expected_axis = ("x", "y", "z")[index]
        if index == 0 and f"axis={expected_axis}" not in state:
            raise RuntimeError(f"Java places the Rose Quartz block on axis {expected_axis}; got {state}.")
        multiplayer.until(f"{player} to see placed {block}", lambda:
                          actor.call("block", *pos)["state"] == state)
        multiplayer.until(f"{player} to spend {block}", lambda:
                          multiplayer.count(actor, block) == 0)
        positions.append((pos, block, state))
    return positions


def check_saved_blocks(host, positions):
    for pos, block, state in positions:
        observed = host.call("block", *pos)
        if observed["block"] != block or observed["state"] != state:
            raise RuntimeError(f"Reopened palette at {pos}: expected {state}, got {observed}.")


def save_and_rejoin(args, host, scratch):
    port = host.call("lan", "open", 0, "commands", "force")["port"]
    address = f"127.0.0.1:{port}"
    with multiplayer.joined_client(
        args, scratch, address, GUEST, render=True,
        scenario="rose-quartz-lifecycle", pack=args.pack,
    ) as guest:
        multiplayer.until("the palette guest to join", lambda: any(
            item["name"] == GUEST and item["placed"]
            for item in host.call("lan", "status")["guests"]
        ))
        host.command(f"/gamemode survival {GUEST}")
        positions = place_palettes(host, guest, GUEST)
        host.command(f"/give {GUEST} create:polished_rose_quartz 2")
        multiplayer.until("the guest's polished Rose Quartz to arrive", lambda:
                          multiplayer.count(guest, "create:polished_rose_quartz") == 2)
    multiplayer.until("the palette guest to disconnect", lambda: not any(
        item["name"] == GUEST and item["placed"]
        for item in host.call("lan", "status")["guests"]
    ))
    host.restart()
    check_saved_blocks(host, positions)
    port = host.call("lan", "open", 0, "commands", "force")["port"]
    rmtree(scratch / GUEST / "horizon-mods")
    with multiplayer.joined_client(
        args, scratch, f"127.0.0.1:{port}", GUEST, render=True,
        scenario="rose-quartz-lifecycle-rejoin", pack=args.pack,
    ) as guest:
        multiplayer.until("the palette guest to rejoin", lambda: any(
            item["name"] == GUEST and item["placed"]
            for item in host.call("lan", "status")["guests"]
        ))
        multiplayer.until("the guest inventory to reload", lambda:
                          multiplayer.count(guest, "create:polished_rose_quartz") == 2)
        check_saved_blocks(host, positions)
        for pos, _, state in positions:
            multiplayer.until(f"guest palette state at {pos} to converge", lambda:
                              guest.call("block", *pos)["state"] == state)


def solo(args):
    with fixture_world(args, "Rose-quartz-lifecycle", render=True, pack=args.pack) as host:
        conversions(host, "@s")
        host.command("/clear @s")
        positions = place_palettes(host, host, "@s")
        host.commands((
            "/give @s create:polished_rose_quartz 2",
            "/tick freeze",
        ))
        host.restart()
        check_saved_blocks(host, positions)
        counts = host.call("inventory")["counts"]
        if counts.get("create:polished_rose_quartz") != 2:
            raise RuntimeError(f"The palette material inventory did not survive reopen: {counts}.")
    with fixture_world(args, "Rose-quartz-mining", render=True, pack=args.pack) as host:
        pos = (9, 171, 21)
        feet = (9.5, 171, 23.5)
        host.commands((
            "/fill 6 170 18 13 170 25 minecraft:stone",
            "/gamemode survival",
            f"/tp @s {' '.join(map(str, feet))}",
            "/effect give @s minecraft:haste 240 8 true",
            "/tick unfreeze",
        ))
        multiplayer.until("the miner at the palette fixture", lambda:
                          host.call("state")["player"]["position"] == list(feet))
        for block, _, _ in PALETTES:
            host.commands((
                "/clear @s",
                f"/setblock {' '.join(map(str, pos))} {block}",
                "/item replace entity @s hotbar.0 with minecraft:wooden_pickaxe",
            ))
            host.call("select", "minecraft:wooden_pickaxe")
            result = host.call("break", *pos, "--timeout", 20)
            if result["block"] != "minecraft:air" or result["drops"] != {block: 1}:
                raise RuntimeError(f"Picking {block} should return one block; got {result}.")


def lan(args):
    with fixture_world(args, "Rose-quartz-lifecycle-LAN", render=True, pack=args.pack) as host:
        host.commands(("/tick unfreeze", "/gamemode survival"))
        with TemporaryDirectory(prefix="hc-rose-quartz-lan-") as temp:
            save_and_rejoin(args, host, Path(temp))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        lan(args)
        print("A LAN guest placed the three Java Rose Quartz shapes; block states and its polished material inventory survived host reopen and rejoin.")
    else:
        solo(args)
        print("Both shapeless palette conversions, all three pickaxe drops, three orientations, and saved blocks plus inventory passed.")


if __name__ == "__main__":
    main()
