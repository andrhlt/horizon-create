#!/usr/bin/env python3
"""Verify original Postbox colors, package inventory, and comparator output."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

menu = import_module("test-frogport-menu")
mp = menu.multiplayer
packager = import_module("test-packager-redstone")
BOX = "create:white_postbox"
POS = (12, 100, -9)
COMPARATOR = (13, 100, -9)
FEET = [12.5, 100.0, -6.5]
GUEST = "PostboxGuest"


def java(name):
    with (ROOT / "fixtures" / f"postbox-{name}-java.csv").open() as source:
        return list(csv.DictReader(source))


def state(row):
    return f'facing={row["facing"]},open={row["open"]},waterlogged={row["waterlogged"]}'


def registered(host):
    for index, row in enumerate(java("defaults")):
        position = 7 + index % 4, 100, -17 + index // 4
        host.command(f'/setblock {packager.xyz(position)} {row["id"]}')
        block = host.call("block", *position)
        assert block["block"] == row["id"], (row, block)
        assert block["state"] == f'{row["id"]}[{state(row)}]', (row, block)
        item = host.command(f'/clear @s {row["id"]} 0')
        assert "No items were found" in item, (row, item)
    recipes = java("crafting")
    replies = host.commands(f'/recipe give @s {row["recipe"]}' for row in recipes)
    for row, reply in zip(recipes, replies, strict=True):
        assert "Unlocked" in reply or "No new recipes were learned" in reply, (row, reply)
    print(f"Loaded all 16 original Postbox block and item IDs and {len(recipes)} recipe IDs.")


def place(host, actor, player):
    target = (10, 100, -8)
    look_from = {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}
    x, y, z = target
    for row in java("placement"):
        dx, dz = look_from[int(row["yaw"])]
        feet = [x + .5 + dx * 2, y, z + .5 + dz * 2]
        fluid = "water" if row["wet"] == "true" else "air"
        host.commands((
            f"/setblock {packager.xyz(target)} minecraft:{fluid}",
            f"/item replace entity {player} hotbar.2 with {BOX}",
            f"/tp {player} {packager.xyz(feet)}",
        ))
        mp.until("the actor to reach the placement point", lambda: actor.call("state")["player"]["position"] == feet)
        actor.call("select", BOX)
        actor.call("look-at", x + .5, y, z + .5)
        actor.call("wait", 3)
        actor.call("interact", x, y - 1, z, "up")
        expected = f"{BOX}[{state(row)}]"
        mp.until(f"the actor to place a Postbox facing {row['facing']} in {fluid}",
                 lambda: host.call("block", *target)["state"] == expected)
        if player != "@s":
            mp.until("the Postbox state to synchronize to the guest",
                     lambda: actor.call("block", *target)["state"] == expected)
    print("All eight original Postbox placements matched facing and waterlogging.")


def craft_all(args):
    crafting = import_module("test-machine-crafting")
    rows = java("crafting")
    env = {"HORIZON_NO_AUDIO": "1"}
    with fixture_world(args, "PostboxCrafting", pack=args.pack, render=True, env=env) as host:
        host.commands((
            "/fill 8 169 22 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
            "/gamemode survival",
        ))
        for row in rows:
            recipe = {**row, "slots": row["inputs"].replace("|", ","), "remainder": ""}
            crafting.replay(host, recipe)
            print(f'{row["recipe"]} matched Java.')
    print(f"All {len(rows)} original Postbox recipes matched in survival.")


def inspect_signal(host, expected):
    at = host.clock()
    for elapsed in range(1, 4):
        host.step_to(at + elapsed)
    reply = packager.block_value(host, COMPARATOR, "OutputSignal")
    assert int(reply) == expected, (reply, expected)


def analog(host):
    for row in java("inventory"):
        used = int(row["filled"])
        stash = ",".join(
            f'{{Slot:{slot}b,id:"{menu.PACKAGE}",count:1}}' for slot in range(used)
        )
        host.command(f'/data merge block {packager.xyz(POS)} {{Items:[{stash}]}}')
        inspect_signal(host, int(row["signal"]))
    print("Postbox comparator levels matched the original empty, 1, 9, and 18 slot inventory samples.")


def interactive(host, actor, player, shots):
    host.commands((
        f"/gamemode survival {player}",
        f"/tp {player} {packager.xyz(FEET)}",
        f"/item replace entity {player} hotbar.1 with minecraft:stone",
        f"/item replace block {packager.xyz(POS)} container.17 with {menu.PACKAGE}",
        "/tick unfreeze",
    ))
    def open_state(wanted):
        return f"open={str(wanted).lower()}" in host.call("block", *POS)["state"]
    mp.until("the actor to arrive at the Postbox", lambda: actor.call("state")["player"]["position"] == FEET)
    actor.call("interact", *POS, "south")
    mp.until("the Postbox to open and show the original 18th slot", lambda:
             menu.stack_item(actor, 317) == menu.PACKAGE and open_state(True))
    actor.call("wait", 4)
    if shots:
        actor.call("screenshot", shots / "open.png")
    actor.call("click-slot", 317)
    actor.call("click-slot", 0)
    mp.until("the package to enter the hotbar", lambda:
             menu.stack_item(actor, 0) == menu.PACKAGE and menu.stack_item(actor, 317) is None)
    actor.call("click-slot", 1)
    actor.call("click-slot", 317)
    mp.until("the Postbox to reject Stone", lambda:
             (actor.call("menu")["carried"] or {}).get("item") == "minecraft:stone"
             and menu.stack_item(actor, 317) is None)
    actor.call("click-slot", 1)
    actor.call("click-slot", 0)
    actor.call("click-slot", 317)
    mp.until("the package to return to the Postbox", lambda: menu.stack_item(actor, 317) == menu.PACKAGE)
    actor.call("click-button", "Frogport Address")
    actor.call("type", "Warehouse")
    actor.call("click-button", "Confirm")
    mp.until("the Postbox to close and save the address", lambda:
             open_state(False) and packager.block_value(host, POS, "AddressFilter") == '"Warehouse"')
    actor.call("interact", *POS, "south")
    mp.until("the package to remain after reopening", lambda:
             open_state(True) and menu.stack_item(actor, 317) == menu.PACKAGE)
    actor.call("close")
    mp.until("the Postbox to close again", lambda: open_state(False))
    host.command("/tick freeze")
    print("Postbox opened and closed, rejected Stone, retained a parcel, and saved the Warehouse address.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--craft", action="store_true")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if args.craft:
        craft_all(args)
        return
    env = {"HORIZON_NO_AUDIO": "1"}
    mode = "LAN" if args.lan else "Solo"
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, f"Postbox{mode}", pack=args.pack, render=not args.lan, env=env))
        host.commands((
            "/fill 8 99 -12 17 99 -5 minecraft:stone",
            f"/setblock {packager.xyz(POS)} {BOX}",
            f"/setblock {packager.xyz(COMPARATOR)} minecraft:comparator[facing=west]",
        ))
        if not args.lan:
            registered(host)
        analog(host)
        actor, player = host, "@s"
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-postbox-")))
            actor = stack.enter_context(mp.joined_client(args, scratch, f"127.0.0.1:{port}", GUEST,
                                                        render=True, scenario="postbox", pack=args.pack, env=env))
            player = GUEST
            mp.until("the Postbox guest to join", lambda: any(
                guest["name"] == GUEST and guest["placed"] for guest in host.call("lan", "status")["guests"]
            ))
        if args.screenshots:
            args.screenshots.mkdir(parents=True, exist_ok=True)
        interactive(host, actor, player, args.screenshots)
        place(host, actor, player)
    print(f"{mode}: standalone Postbox checks passed.")


if __name__ == "__main__":
    main()
