#!/usr/bin/env python3
"""Check Stock Keeper owner isolation and idle/queued save-reopen behavior."""

import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
summary = import_module("test-stock-ticker-summary")
order = import_module("test-stock-ticker-order")
packager = order.packager
TICKER = order.TICKER
BURNER = order.BURNER
BARREL = order.BARREL
PACKAGER = order.PACKAGER
LINK = order.LINK
IRON = order.IRON
FREQUENCY = "[I;548,113,26,3]"
OWNER_A = "StockKeeperA"
OWNER_B = "StockKeeperB"


def package_order(box):
    if not box:
        return None
    data = box["components"]["create:package_order_data"]["order_context"]
    return data["ordered_stacks"]["entries"][0]["count"]


def verify_idle_reopen(host):
    def idle_state():
        machine = packager.block_data(host, PACKAGER)
        assert "HeldBox:" not in machine and "QueuedExitingPackages:" not in machine, machine
        return (
            packager.block_value(host, TICKER, "Freq").replace(" ", ""),
            packager.block_value(host, LINK, "Freq").replace(" ", ""),
            packager.describe_slots(packager.block_value(host, BARREL, "Items"), "Slot"),
            packager.block_value(host, TICKER, "PreviousAddress"),
        )

    before = idle_state()
    assert before[:3] == (FREQUENCY, FREQUENCY, "0:minecraft:iron_ingot=11"), before
    host.restart()
    after = idle_state()
    assert after == before, (before, after)
    print("Idle Ticker, Stock Link, connected inventory, and eleven iron ingots survived cold reopen.")


def run(args):
    mode = "StockTickerOwnership"
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, mode, pack=args.pack, render=False,
                                                   env={"HORIZON_NO_AUDIO": "1"}))
        host.commands((
            "/fill 5 100 -11 17 100 -4 minecraft:stone",
            f"/setblock {packager.xyz(TICKER)} create:stock_ticker",
            f"/data merge block {packager.xyz(TICKER)} {{Freq:{FREQUENCY}}}",
            f"/setblock {packager.xyz(BURNER)} create:blaze_burner[blaze=smouldering]",
            f"/setblock {packager.xyz(BARREL)} minecraft:barrel",
            f"/item replace block {packager.xyz(BARREL)} container.0 with {IRON} 11",
            f"/setblock {packager.xyz(PACKAGER)} create:packager[facing=east]",
            f"/setblock {packager.xyz(LINK)} create:stock_link",
            f"/data merge block {packager.xyz(LINK)} {{Freq:{FREQUENCY}}}",
        ))
        verify_idle_reopen(host)

        scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-stock-owners-")))
        port = host.call("lan", "open", 0, "commands", "force")["port"]
        actor_a = stack.enter_context(mp.joined_client(
            args, scratch, f"127.0.0.1:{port}", OWNER_A, render=True,
            scenario="stock-ticker-owner", pack=args.pack, env={"HORIZON_NO_AUDIO": "1"},
        ))
        actor_b = stack.enter_context(mp.joined_client(
            args, scratch, f"127.0.0.1:{port}", OWNER_B, render=True,
            scenario="stock-ticker-owner", pack=args.pack, env={"HORIZON_NO_AUDIO": "1"},
        ))
        mp.until("both Stock Keeper players to join", lambda: {
            guest["name"] for guest in host.call("lan", "status")["guests"] if guest["placed"]
        } >= {OWNER_A, OWNER_B})

        host.commands((
            f"/tp {OWNER_A} 10.5 101 -5.5",
            f"/tp {OWNER_B} 12.5 101 -5.5",
            f"/item replace entity {OWNER_A} hotbar.0 with minecraft:stick",
            f"/item replace entity {OWNER_B} hotbar.0 with minecraft:stick",
        ))
        for actor in (actor_a, actor_b):
            mp.until("each owner to arrive with a Stick", lambda actor=actor:
                     actor.call("state")["player"]["position"][1:] == [101.0, -5.5]
                     and mp.count(actor, "minecraft:stick") == 1)
            actor.call("select", "minecraft:stick")
            actor.call("options-set", "guiScale", "2")

        summary.open_menu(actor_a, BURNER, (11.5, 101.65, -7.5))
        origin_a, height_a = order.panel(actor_a, scratch / "owner-a.png")
        summary.open_menu(actor_b, BURNER, (11.5, 101.65, -7.5))
        origin_b, height_b = order.panel(actor_b, scratch / "owner-b.png")
        order.place_order(actor_a, origin_a, height_a, "Guest Depot", iron=2, copper=0)
        mp.until("owner A's address to reach the Ticker", lambda:
                 packager.block_value(host, TICKER, "PreviousAddress").strip('"') == "Guest Depot")
        assert mp.count(actor_a, IRON) == 0 and mp.count(actor_a, "minecraft:stick") == 1
        summary.stock(host, 4)
        order.place_order(actor_b, origin_b, height_b, "Host Depot", iron=9, copper=0)
        mp.until("owner B's address and order to reach the Ticker", lambda:
                 packager.block_value(host, TICKER, "PreviousAddress").strip('"') == "Host Depot")
        assert mp.count(actor_b, IRON) == 0 and mp.count(actor_b, "minecraft:stick") == 1

        state = order.snapshot(host)
        assert state[0] == "Host Depot", state
        held = order.snbt(packager.block_value(host, PACKAGER, "HeldBox"))
        queued = order.snbt(packager.block_value(host, PACKAGER, "QueuedExitingPackages"))
        assert order.package_state(held) == "Guest Depot:2:0", held
        assert order.package_state(queued[0]["item_stack"]) == "Host Depot:4:0", queued
        assert package_order(queued[0]["item_stack"]) == 9, queued
        assert state[3:5] == (0, 0), state
        print("Two LAN guests sent distinct orders and addresses; each kept its own inventory. "
              "Owner B requested nine iron while only four remained, and the Packager shipped four.")

        before_reopen = state
        host.restart()
        after_reopen = order.snapshot(host)
        assert after_reopen[:5] == before_reopen[:5], (before_reopen, after_reopen)
        assert 0 <= after_reopen[5] <= before_reopen[5], (before_reopen, after_reopen)
        assert packager.block_value(host, TICKER, "Freq").replace(" ", "") == FREQUENCY
        held_after = order.snbt(packager.block_value(host, PACKAGER, "HeldBox"))
        queued_after = order.snbt(packager.block_value(host, PACKAGER, "QueuedExitingPackages"))
        assert order.package_state(held_after) == "Guest Depot:2:0", held_after
        assert order.package_state(queued_after[0]["item_stack"]) == "Host Depot:4:0", queued_after
        assert package_order(queued_after[0]["item_stack"]) == 9, queued_after
        host.step_to(host.clock() + 1)
        resumed = order.snapshot(host)
        assert resumed[:5] == after_reopen[:5], (after_reopen, resumed)
        assert resumed[5] == max(0, after_reopen[5] - 1), (after_reopen, resumed)
        print("Ticker address, inventory, held parcel, and partially fulfilled queued order survived cold reopen.")
        print("The reopened Packager resumed its saved animation while retaining both parcels.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
