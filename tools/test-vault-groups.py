#!/usr/bin/env python3
"""Check bounded Item Vault group formation, sided transfer, and reopen."""

import argparse
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

multiplayer = import_module("test-multiplayer")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read_items(control, pos):
    x, y, z = pos
    reply = control.command(f"/data get block {x} {y} {z} Items")
    if "no elements matching" in reply.lower():
        return ""
    match = re.search(r"has the following block data: (.*)", reply)
    require(match is not None, f"Could not read inventory at {pos}: {reply}")
    return match[1]


def item_count(data, item):
    stacks = re.findall(r"\{[^{}]*\bid: \"" + re.escape(item) + r"\"[^{}]*\}", data)
    return sum(int(count[1]) for stack in stacks
               if (count := re.search(r"\bcount: (\d+)", stack)))


def guest_extracts_from_vault_hopper(control, args):
    address = f"127.0.0.1:{control.call('lan', 'open', '0', 'commands', 'force')['port']}"
    with TemporaryDirectory(prefix="hc-vault-guest-") as scratch:
        with multiplayer.joined_client(args, Path(scratch), address, "VaultGuest", render=True,
                                       scenario="vault-groups-lan") as guest:
            multiplayer.until("vault guest to join", lambda: any(
                player["name"] == "VaultGuest" and player["placed"]
                for player in control.call("lan", "status")["guests"]
            ))
            control.commands(("/gamemode survival VaultGuest", "/tp VaultGuest 11.5 96 12.5"))
            multiplayer.until("guest to see the Hopper draining the vault", lambda:
                              guest.call("block", 11, 95, 10)["block"] == "minecraft:hopper")
            guest.call("interact", 11, 95, 10, "south")
            multiplayer.until("guest to see the extracted paper", lambda: any(
                (slot["stack"] or {}).get("item") == "minecraft:paper"
                for slot in guest.call("menu").get("slots", [])
            ))
            guest.call("click-slot", 300, "shift")
            multiplayer.until("guest to receive the paper", lambda: multiplayer.count(guest, "minecraft:paper") == 1)
            multiplayer.until("host to observe the guest's extraction", lambda:
                              "minecraft:paper" not in read_items(control, (11, 95, 10)))


def run(args):
    with fixture_world(args, "Vault-groups") as control:
        # A two-member horizontal group should expose both local inventories
        # through a hopper attached to either member.
        control.commands((
            "/setblock 10 96 10 create:item_vault[axis=x]",
            "/setblock 11 96 10 create:item_vault[axis=x]",
            "/setblock 10 97 10 minecraft:hopper[facing=down]",
            "/setblock 11 95 10 minecraft:hopper[facing=down]",
            "/item replace block 10 97 10 container.0 with minecraft:paper 1",
        ))
        start = control.clock()
        for tick in range(1, 9):
            control.step_to(start + tick)
        sink = control.command("/data get block 11 95 10 Items")
        require("minecraft:paper" in sink and re.search(r"count: 1", sink),
                f"A hopper below the second vault member did not extract the paper inserted above the first: {sink}")
        if args.lan:
            guest_extracts_from_vault_hopper(control, args)
            sink = read_items(control, (11, 95, 10))
            require("minecraft:paper" not in sink, f"The LAN guest did not extract the paper: {sink}")
        remaining = read_items(control, (10, 96, 10)) + read_items(control, (11, 96, 10))
        require("minecraft:paper" not in remaining, f"The connected vault was not empty after extraction: {remaining}")

        # Remove an empty member to split the group, then fill the survivor.
        # Reopening exercises persistence for the remaining storage.
        control.command("/setblock 11 95 10 minecraft:air")
        control.command("/setblock 10 96 10 minecraft:air")
        start = control.clock()
        for tick in range(1, 4):
            control.step_to(start + tick)
        survivor = control.call("block", 11, 96, 10)["state"]
        require(survivor.startswith("create:item_vault["), f"Removing a member removed the surviving vault: {survivor}")
        control.command("/setblock 11 97 10 minecraft:hopper[facing=down]")
        control.command("/item replace block 11 97 10 container.0 with minecraft:paper 1")
        start = control.clock()
        for tick in range(1, 8):
            control.step_to(start + tick)
        before = (read_items(control, (11, 96, 10)),)
        require("minecraft:paper" in "".join(before), f"The surviving vault did not retain its inserted item: {before}")
        control.command("/item replace block 11 96 10 container.0 with minecraft:paper 64")
        control.commands(
            f"/item replace block 11 96 10 container.{slot} with minecraft:stone 64"
            for slot in range(1, 20)
        )
        full = read_items(control, (11, 96, 10))
        require(item_count(full, "minecraft:paper") == 64 and item_count(full, "minecraft:stone") == 19 * 64,
                f"The 20-slot vault did not reach its full boundary: {full}")
        control.command("/item replace block 11 97 10 container.0 with minecraft:paper 2")
        control.restart()
        after = (read_items(control, (11, 96, 10)),)
        pending = read_items(control, (11, 97, 10))
        require(item_count(after[0], "minecraft:paper") == 64
                and item_count(after[0], "minecraft:stone") == 19 * 64
                and item_count(pending, "minecraft:paper") == 2,
                f"Items were lost or duplicated across reopen: vault={after}, hopper={pending}")
        control.command("/item replace block 11 96 10 container.19 with minecraft:air")
        start = control.clock()
        for tick in range(1, 21):
            control.step_to(start + tick)
        transferred = read_items(control, (11, 96, 10))
        remaining = read_items(control, (11, 97, 10))
        require(item_count(transferred, "minecraft:paper") == 66
                and item_count(transferred, "minecraft:stone") == 18 * 64
                and item_count(remaining, "minecraft:paper") == 0,
                f"The full vault did not reject and then resume the saved hopper transfer: {transferred}")

        # The pinned Java width rule caps the cross-section at 3 and the long
        # axis at width * 3. A complete 3x3x9 group uses the large state.
        control.command("/fill 20 96 20 28 98 22 create:item_vault[axis=x]")
        start = control.clock()
        for tick in range(1, 8):
            control.step_to(start + tick)
        center = control.call("block", 24, 97, 21)["state"]
        require("large=true" in center, f"The supported 3x3x9 vault did not form its large state: {center}")
    print("Item Vault sided group transfer, member split, full/empty boundary, and filled active-transfer reopen passed; 3x3x9 formation passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--lan", action="store_true", help="also have a real guest retrieve the grouped-vault output")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
