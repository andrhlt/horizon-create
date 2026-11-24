#!/usr/bin/env python3
"""Check a configured Table Cloth issues a saved shop list within network stock."""

import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

mp = import_module("test-multiplayer")
TICKER = (10, 101, -8)
CLOTH = (9, 101, -8)
FREQUENCY = "[I;476,91,26,3]"
BUYER = "ClothBuyer"


def setup(host, player, *, stock):
    ticker = " ".join(map(str, TICKER))
    cloth = " ".join(map(str, CLOTH))
    host.commands((
        "/gamerule spawn_mobs false",
        "/fill 5 100 -11 17 100 -4 minecraft:stone",
        f"/setblock {ticker} create:stock_ticker",
        f"/data merge block {ticker} {{Freq:{FREQUENCY}}}",
        "/setblock 11 101 -8 create:blaze_burner[blaze=smouldering]",
        "/setblock 14 101 -8 minecraft:barrel",
        "/setblock 15 101 -8 create:packager[facing=east]",
        "/setblock 15 102 -8 create:stock_link",
        f"/data merge block 15 102 -8 {{Freq:{FREQUENCY}}}",
        f"/setblock {cloth} create:red_table_cloth[entity=true]",
        f"/data merge block {cloth} {{OwnerUUID:[I;1,2,3,4],Filter:{{id:\"minecraft:emerald\",count:1}},FilterAmount:3,RequestData:{{encoded_request:{{ordered_stacks:{{entries:[{{item_stack:{{id:\"minecraft:iron_ingot\",count:1}},count:2}}]}},ordered_crafts:[]}},encoded_target_address:\"Shop\",target_offset:[1,0,0],target_dim:\"minecraft:overworld\",is_valid:1b}}}}",
        f"/tp {player} 8.5 102 -8.5",
        f"/gamemode survival {player}",
    ))
    if stock:
        host.command("/item replace block 14 101 -8 container.0 with minecraft:iron_ingot 8")


def buy(actor, host, player):
    host.command(f"/tp {player} 8.5 102 -8.5")
    mp.until("buyer to receive the configured shop block", lambda:
             actor.call("block", *CLOTH)["state"] == "create:red_table_cloth[entity=true]")
    mp.until("buyer to reach the cloth", lambda: (
        actor.call("state")["player"]["position"][0] == 8.5
        and actor.call("state")["player"]["position"][1] >= 101.0
        and actor.call("state")["player"]["position"][2] == -8.5
    ))
    actor.call("look-at", 9.5, 101.2, -8.5)
    actor.call("wait", 3)
    actor.call("interact", *CLOTH, "up")
    mp.until("a shopping list to be issued", lambda:
             (actor.call("inventory")["held"] or {}).get("item") == "create:shopping_list")
    held = actor.call("inventory")["held"]
    saved = host.command(f"/data get entity {player} SelectedItem")
    assert "shop_owner" in saved and "shop_network" in saved and "purchases" in saved, saved
    assert "Shop" in saved, saved
    return held


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--empty-stock", action="store_true")
    args = parser.parse_args()

    with fixture_world(args, "TableClothShop", render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as host:
        setup(host, "@s", stock=not args.empty_stock)
        if args.empty_stock:
            host.command("/item replace entity @s hotbar.0 with minecraft:emerald")
            host.call("select", "minecraft:emerald")
            host.call("look-at", 9.5, 101.2, -8.5)
            host.call("wait", 3)
            host.call("interact", *CLOTH, "up")
            mp.until("empty shop stock to refuse a purchase", lambda:
                     (host.call("inventory")["held"] or {}).get("item") == "minecraft:emerald")
            assert host.call("inventory")["counts"].get("create:shopping_list", 0) == 0
            print("A configured Table Cloth refused an order with no network stock.")
            return

        if args.lan:
            with TemporaryDirectory(prefix="hc-table-cloth-shop-") as scratch:
                port = host.call("lan", "open", 0, "commands", "force")["port"]
                with mp.joined_client(args, Path(scratch), f"127.0.0.1:{port}", BUYER,
                                      render=True, scenario="table-cloth-shop", pack=args.pack,
                                      env={"HORIZON_NO_AUDIO": "1"}) as guest:
                    mp.until("buyer guest to join", lambda: any(
                        entry["name"] == BUYER and entry["placed"]
                        for entry in host.call("lan", "status")["guests"]))
                    host.command(f"/gamemode survival {BUYER}")
                    buy(guest, host, BUYER)
                    print("A LAN buyer received a shopping list from a configured cloth.")
        else:
            buy(host, host, "@s")
            host.restart()
            held = host.call("inventory")["held"]
            assert (held or {}).get("item") == "create:shopping_list", held
            print("A configured Table Cloth issued a shopping list that survived world reopen.")


if __name__ == "__main__":
    main()
