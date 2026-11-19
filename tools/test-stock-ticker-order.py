#!/usr/bin/env python3
"""Replay the Java Stock Keeper order trace through its Horizon controls."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

summary = import_module("test-stock-ticker-summary")
packager = summary.packager
menus = summary.menus
mp = summary.mp
snbt = import_module("test-frogport-menu").clipboard_snbt
TICKER = summary.TICKER
BURNER = summary.BURNER
BARREL = (14, 101, -8)
PACKAGER = (15, 101, -8)
LINK = (15, 102, -8)
IRON = "minecraft:iron_ingot"
COPPER = "minecraft:copper_ingot"
GUEST = "StockOrderGuest"


def totals(items):
    return tuple(sum(item["count"] for item in items if item["id"] == kind) for kind in (IRON, COPPER))


def package_state(box):
    if not box:
        return "_:0:0"
    components = box["components"]
    contents = components["create:package_contents"]
    iron, copper = totals([entry["item"] for entry in contents])
    return f'{components["create:package_address"]}:{iron}:{copper}'


def snapshot(host):
    block_value = packager.block_value
    previous = block_value(host, TICKER, "PreviousAddress").strip('"')
    held = snbt(block_value(host, PACKAGER, "HeldBox"))
    queue = snbt(block_value(host, PACKAGER, "QueuedExitingPackages") or "[]")
    stored = totals(snbt(block_value(host, BARREL, "Items") or "[]"))
    animation = int(block_value(host, PACKAGER, "AnimationTicks"))
    return previous, package_state(held), package_state(queue[0]["item_stack"] if queue else None), *stored, animation


def panel(actor, shot):
    actor.call("wait", 5)
    actor.call("screenshot", shot)
    width, height = (value / 2 for value in menus.dimensions(shot))
    slices = max(1, min(17, int((height - 126) // 20)))
    size = 116 + 20 * slices
    return (int((width - 226) // 2), int((height - size) // 2)), size


def edit_address(actor, origin, height, address):
    actor.call("click-at", *menus.point(origin, (45, height - 32)), "right")
    actor.call("type", address)


def place_order(actor, origin, height, address, *, iron, copper):
    for position, count in (((31, 44), iron), ((51, 44), copper)):
        for _ in range(count):
            menus.click(actor, origin, position)
    edit_address(actor, origin, height, address)
    menus.click(actor, origin, (184, height - 30))


def use(host, actor, player, rows, images):
    xyz = packager.xyz
    frequency = "[I;548,113,26,3]"
    host.commands((
        "/fill 5 100 -11 17 100 -4 minecraft:stone",
        f"/setblock {xyz(TICKER)} create:stock_ticker",
        f"/data merge block {xyz(TICKER)} {{Freq:{frequency}}}",
        f"/setblock {xyz(BURNER)} create:blaze_burner[blaze=smouldering]",
        f"/setblock {xyz(BARREL)} minecraft:barrel",
        f"/item replace block {xyz(BARREL)} container.0 with {IRON} 11",
        f"/item replace block {xyz(BARREL)} container.1 with {COPPER} 4",
        f"/setblock {xyz(PACKAGER)} create:packager[facing=east]",
        f"/setblock {xyz(LINK)} create:stock_link",
        f"/data merge block {xyz(LINK)} {{Freq:{frequency}}}",
        f"/tp {player} 11.5 101 -5.5",
        f"/item replace entity {player} hotbar.0 with minecraft:stick",
    ))
    mp.until("the actor to arrive at the Stock Keeper", lambda: (
        actor.call("state")["player"]["position"] == [11.5, 101.0, -5.5]
        and mp.count(actor, "minecraft:stick") == 1
    ))
    actor.call("select", "minecraft:stick")
    actor.call("options-set", "guiScale", "2")
    start = host.clock() - 3
    origin = height = None
    for row in rows:
        tick = int(row["tick"])
        host.step_to(start + tick)
        if tick == 4:
            summary.open_menu(actor, BURNER, (11.5, 101.65, -7.5))
            origin, height = panel(actor, images / "stock.png")
            place_order(actor, origin, height, "Warehouse", iron=2, copper=3)
        elif tick == 5:
            summary.stock(host, 4)
        elif tick == 6:
            place_order(actor, origin, height, "Smelting", iron=9, copper=0)
        if row["accepted"] == "true":
            mp.until(f"the order to reach the server at fixture tick {tick}", lambda:
                     packager.block_value(host, TICKER, "PreviousAddress").strip('"') == row["previous_address"])
        expected = (
            row["previous_address"], row["held_package"], row["queued_package"],
            int(row["stored_iron"]), int(row["stored_copper"]), int(row["animation"]),
        )
        actual = snapshot(host)
        assert actual == expected, (tick, expected, actual)
        assert host.clock() == start + tick
        if tick in (4, 6):
            actor.call("screenshot", images / f"sent-{tick}.png")
        print(f"{tick}: {actual}")

    queue = snbt(packager.block_value(host, PACKAGER, "QueuedExitingPackages"))
    context = queue[0]["item_stack"]["components"]["create:package_order_data"]["order_context"]
    assert context["ordered_stacks"]["entries"][0]["count"] == 9, context

    edit_address(actor, origin, height, "Depot")
    actor.call("key", "escape", "tap")
    mp.until("the address to save on close", lambda:
             packager.block_value(host, TICKER, "PreviousAddress").strip('"') == "Depot")
    assert len(snbt(packager.block_value(host, PACKAGER, "QueuedExitingPackages"))) == 1
    print(f"Matched {len(rows)} Java order snapshots. Closing with a new address saved the address without shipping.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    with (ROOT / "fixtures/stock-ticker-order-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    env = {"HORIZON_NO_AUDIO": "1"}
    mode = "LAN" if args.lan else "Solo"
    with ExitStack() as resources:
        host = resources.enter_context(fixture_world(
            args, f"StockTickerOrder{mode}", pack=args.pack, render=not args.lan, env=env,
        ))
        scratch = Path(resources.enter_context(TemporaryDirectory(prefix="hc-stock-order-")))
        actor, player = host, "@s"
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            actor = resources.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", GUEST, render=True, scenario="stock-order",
                pack=args.pack, env=env,
            ))
            player = GUEST
            mp.until("the Stock Keeper guest to join", lambda: any(
                guest["name"] == GUEST and guest["placed"] for guest in host.call("lan", "status")["guests"]
            ))
        images = args.screenshots or scratch
        images.mkdir(parents=True, exist_ok=True)
        use(host, actor, player, rows, images)


if __name__ == "__main__":
    main()
