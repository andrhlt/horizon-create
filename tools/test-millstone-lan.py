#!/usr/bin/env python3
"""Check a LAN guest can feed and collect from the original Millstone fixture."""

import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
STRUCTURE = Path("gametest/processing/wheat_milling.nbt")
GUEST = "MillstoneGuest"
WHEAT = "minecraft:wheat"
FLOUR = "create:wheat_flour"
BARREL = (5, 102, -11)
MILL = (5, 98, -11)
HOPPER = (5, 97, -11)
CHEST = (4, 97, -11)
LEVER = (4, 102, -11)


def item_count(nbt, item):
    total = 0
    for stack in re.findall(r'\{([^{}]*\bid: "[a-z0-9_.-]+:[^{}]+)\}', nbt):
        found = re.search(r'\bid: "([a-z0-9_.-]+:[^" ]+)"', stack)
        if not found or found[1] != item:
            continue
        count = re.search(r"\b(?:count|Count): (\d+)", stack)
        total += int(count[1]) if count else 1
    return total


def menu_count(actor, item):
    return sum(slot.get("stack", {}).get("count", 0)
               for slot in actor.call("menu").get("slots", [])
               if slot.get("slot", -1) >= 300 and (slot.get("stack") or {}).get("item") == item)


def host_block_items(host, pos):
    return item_count(host.command(f"/data get block {' '.join(map(str, pos))} Items"), WHEAT)


def host_flour(host, pos):
    return item_count(host.command(f"/data get block {' '.join(map(str, pos))} Items"), FLOUR)


def machine_flour(host):
    return sum(host_flour(host, pos) for pos in (MILL, HOPPER))


def find_stack_slot(actor, item, *, minimum=0):
    return next((slot["slot"] for slot in actor.call("menu").get("slots", [])
                 if slot["slot"] >= minimum and (slot.get("stack") or {}).get("item") == item), None)


def open_container(actor, host, pos, stand, face):
    x, y, z = pos
    sx, sy, sz = stand
    player = "@s" if actor is host else GUEST
    host.command(f"/tp {player} {sx} {sy} {sz}")
    mp.until("player to reach the container", lambda: actor.call("state")["player"]["position"]
             == [float(sx), float(sy), float(sz)])
    host.step_to(host.clock() + 1)
    actor.call("look-at", x + 0.5, y + 0.5, z + 0.5)
    actor.call("interact", x, y, z, face)
    try:
        mp.until("container menu to open", lambda: actor.call("screen")["screen"] == "container")
    except RuntimeError as error:
        raise RuntimeError(
            f"{error}; screen={actor.call('screen')}, target={actor.call('block', x, y, z)}, "
            f"player={actor.call('state')['player']['position']}"
        ) from error


def run(args, scratch):
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(
            args, "MillstoneLAN", STRUCTURE, render=True, pack=args.pack,
        ))
        host.command("/place template create:gametest/processing/wheat_milling 3 96 -12")
        host.commands((
            f"/setblock {LEVER[0]} {LEVER[1]} {LEVER[2]} "
            "minecraft:lever[face=wall,facing=west,powered=false]",
            "/setblock 5 101 -13 minecraft:smooth_stone",
            "/setblock 4 96 -13 minecraft:smooth_stone",
            "/setblock 4 96 -10 minecraft:smooth_stone",
            f"/item replace block {BARREL[0]} {BARREL[1]} {BARREL[2]} container.13 with minecraft:air",
            f"/item replace block {BARREL[0]} {BARREL[1]} {BARREL[2]} container.0 with minecraft:air",
        ))
        network = host.call("lan", "open", "0", "commands", "force")
        guest = stack.enter_context(mp.joined_client(
            args, scratch, f"127.0.0.1:{network['port']}", GUEST, render=True,
            scenario="millstone-lan", pack=args.pack, env={"HORIZON_NO_AUDIO": "1"},
        ))
        mp.until("the Millstone guest to join", lambda: any(
            player["name"] == GUEST and player["placed"]
            for player in host.call("lan", "status")["guests"]
        ))
        host.commands((
            f"/gamemode survival {GUEST}",
            f"/clear {GUEST}",
            f"/item replace entity {GUEST} hotbar.0 with {WHEAT} 1",
        ))
        mp.until("guest wheat inventory to synchronize", lambda: mp.count(guest, WHEAT) == 1)

        open_container(guest, host, BARREL, (5.5, 102, -12.5), "north")
        wheat_slot = find_stack_slot(guest, WHEAT)
        if wheat_slot is None:
            visible = [(slot.get("slot"), slot.get("stack")) for slot in guest.call("menu").get("slots", [])
                       if slot.get("stack")]
            raise RuntimeError(f"Guest wheat did not appear in the open Barrel menu: {visible}")
        guest.call("click-slot", wheat_slot, "shift")
        mp.until("guest wheat to enter the Barrel", lambda:
                 host_block_items(host, BARREL) == 1 and mp.count(guest, WHEAT) == 0)
        mp.until("guest to observe the Barrel wheat", lambda: menu_count(guest, WHEAT) == 1)
        guest.call("close")
        mp.until("guest to close the input Barrel", lambda: guest.call("screen")["screen"] != "container")

        start = host.clock()
        for tick in range(1, 101):
            host.step_to(start + tick)
            if (host_flour(host, CHEST) >= 1 and machine_flour(host) == 0
                    and item_count(host.command(f"/data get block {' '.join(map(str, MILL))} Items"), WHEAT) == 0):
                break
        else:
            raise RuntimeError("Host-authoritative Millstone output did not reach the output chest.")
        flour_count = host_flour(host, CHEST)

        # Clear the fixture block above the chest after processing so the guest
        # can open the output inventory.
        host.command("/setblock 4 98 -11 minecraft:air")
        open_container(guest, host, CHEST, (4.5, 97, -12.5), "north")
        mp.until("guest chest view to show host-produced flour", lambda:
                 menu_count(guest, FLOUR) == flour_count)
        output_slot = find_stack_slot(guest, FLOUR, minimum=300)
        if output_slot is None:
            raise RuntimeError("Guest could not see the Millstone flour in the output chest.")
        guest.call("click-slot", output_slot, "shift")
        mp.until("guest flour inventory and host chest to converge", lambda:
                 mp.count(guest, FLOUR) == flour_count and host_flour(host, CHEST) == 0)
        guest_inventory = item_count(
            host.command(f"/data get entity {GUEST} Inventory"), FLOUR,
        )
        if guest_inventory != flour_count:
            raise RuntimeError(
                f"Host and guest inventory state disagreed after chest collection: "
                f"host sees {guest_inventory}, guest sees {mp.count(guest, FLOUR)}; expected {flour_count}."
            )
        mp.until("guest chest view to converge to empty", lambda:
                 menu_count(guest, FLOUR) == 0)
        guest.call("close")

    print(f"LAN guest supplied one wheat and collected {flour_count} host-produced flour; both clients converged.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=lambda path: Path(path).resolve(strict=True), default=ROOT / ".local/create.hmod")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-millstone-lan-") as scratch:
        run(args, Path(scratch))


if __name__ == "__main__":
    main()
