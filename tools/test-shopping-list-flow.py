#!/usr/bin/env python3
"""Exercise Table Cloth shopping list creation, payment, dispatch and ownership."""

import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

mp = import_module("test-multiplayer")
packager = import_module("test-stock-ticker-summary")
order_trace = import_module("test-stock-ticker-order")
snbt = import_module("test-frogport-menu").clipboard_snbt
TICKER = packager.TICKER
BARREL = (14, 101, -8)
PACKAGER = (15, 101, -8)
LINK = (15, 102, -8)
CLOTH = (8, 101, -8)
FREQUENCY = "[I;548,113,26,3]"
OWNER = "ShopListGuest"


def block_data(host, pos, path):
    return packager.packager.block_value(host, pos, path)


def prepare(host, player):
    cloth = " ".join((
        "{OwnerUUID:[I;1,2,3,4],Filter:{id:\"minecraft:gold_ingot\",count:1},FilterAmount:2,",
        "RequestData:{encoded_request:{ordered_stacks:{entries:[{item_stack:{id:\"minecraft:iron_ingot\",count:1},count:3}]},",
        "ordered_crafts:[]},encoded_target_address:\"Warehouse\",target_offset:[I;2,0,0],",
        "target_dim:\"minecraft:overworld\",is_valid:1b}}",
    ))
    host.commands((
        "/fill 5 100 -11 17 100 -4 minecraft:stone",
        f"/setblock {packager.xyz(TICKER)} create:stock_ticker",
        f"/data merge block {packager.xyz(TICKER)} {{Freq:{FREQUENCY}}}",
        f"/setblock {packager.xyz(packager.BURNER)} create:blaze_burner[blaze=smouldering]",
        f"/setblock {packager.xyz(BARREL)} minecraft:barrel",
        f"/item replace block {packager.xyz(BARREL)} container.0 with minecraft:iron_ingot 2",
        f"/setblock {packager.xyz(PACKAGER)} create:packager[facing=east]",
        f"/setblock {packager.xyz(LINK)} create:stock_link",
        f"/data merge block {packager.xyz(LINK)} {{Freq:{FREQUENCY}}}",
        f"/setblock {packager.xyz(CLOTH)} create:red_table_cloth[entity=true]",
        "/setblock 9 102 -8 minecraft:stone",
        f"/data merge block {packager.xyz(CLOTH)} {cloth}",
        f"/tp {player} 9.5 103 -7.5",
        f"/gamemode survival {player}",
        f"/item replace entity {player} hotbar.0 with minecraft:air",
        f"/item replace entity {player} hotbar.8 with minecraft:gold_ingot 2",
    ))


def interact(actor, pos):
    actor.call("look-at", *(coordinate + 0.5 for coordinate in pos))
    actor.call("interact", *pos, "up")
    actor.call("wait", 3)


def flow(host, actor, player, *, reopen):
    interact(actor, CLOTH)
    assert actor.call("inventory")["counts"].get("create:shopping_list", 0) == 0
    assert actor.call("inventory")["counts"].get("minecraft:gold_ingot", 0) == 2
    host.command(f"/item replace block {packager.xyz(BARREL)} container.0 with minecraft:iron_ingot 5")
    interact(actor, CLOTH)
    mp.until("the Shopping List to be created", lambda:
             actor.call("inventory")["counts"].get("create:shopping_list", 0) == 1)
    assert actor.call("inventory")["counts"].get("minecraft:gold_ingot", 0) == 2
    listed = host.command(f"/data get entity {player} SelectedItem")
    assert "create:shopping_list" in listed and "purchases" in listed, listed
    interact(actor, CLOTH)
    assert actor.call("inventory")["counts"].get("create:shopping_list", 0) == 1

    if reopen:
        host.restart()
        mp.until("the saved list to reopen", lambda:
                 host.call("inventory")["counts"].get("create:shopping_list", 0) == 1)
        actor = host
        player = "@s"

    # Insufficient payment must preserve the list, payment and stock.
    host.command(f"/clear {player} minecraft:gold_ingot 1")
    interact(actor, TICKER)
    assert actor.call("inventory")["counts"].get("create:shopping_list", 0) == 1
    assert actor.call("inventory")["counts"].get("minecraft:gold_ingot", 0) == 1
    still_stocked = block_data(host, BARREL, "Items")
    assert "iron_ingot" in still_stocked and "count: 5" in still_stocked, still_stocked
    assert "gold_ingot" not in block_data(host, TICKER, "ReceivedPayments")
    host.command(f"/give {player} minecraft:gold_ingot 1")
    mp.until("the second payment item", lambda:
             actor.call("inventory")["counts"].get("minecraft:gold_ingot", 0) == 2)

    actor.call("select", "create:shopping_list")
    interact(actor, TICKER)
    mp.until("the list to be consumed after dispatch", lambda:
             actor.call("inventory")["counts"].get("create:shopping_list", 0) == 0)
    mp.until("the stock to be withdrawn", lambda:
             "iron_ingot" not in block_data(host, BARREL, "Items")
             or "count: 2" in block_data(host, BARREL, "Items"))
    paid = block_data(host, TICKER, "ReceivedPayments")
    assert "gold_ingot" in paid and "count: 2" in paid, paid
    assert actor.call("inventory")["counts"].get("minecraft:gold_ingot", 0) == 0
    held_box = snbt(block_data(host, PACKAGER, "HeldBox"))
    queue = snbt(block_data(host, PACKAGER, "QueuedExitingPackages") or "[]")
    packages = ([held_box] if held_box else []) + [row["item_stack"] for row in queue]
    dispatched = [order_trace.package_state(package) for package in packages]
    assert dispatched == ["Warehouse:3:0"], dispatched


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()

    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(
            args, "ShoppingListFlowLAN" if args.lan else "ShoppingListFlow",
            pack=args.pack, render=not args.lan, env={"HORIZON_NO_AUDIO": "1"},
        ))
        actor, player = host, "@s"
        if args.lan:
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-shopping-list-")))
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            actor = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", OWNER, render=True,
                scenario="shopping-list", pack=args.pack, env={"HORIZON_NO_AUDIO": "1"},
            ))
            player = OWNER
            mp.until("the LAN buyer to join", lambda: any(
                guest["name"] == OWNER and guest["placed"]
                for guest in host.call("lan", "status")["guests"]
            ))
        prepare(host, player)
        actor.call("key", "1", "tap")
        flow(host, actor, player, reopen=not args.lan)
    print(f"Shopping List transaction passed ({'LAN guest' if args.lan else 'solo with cold reopen'}).")


if __name__ == "__main__":
    main()
