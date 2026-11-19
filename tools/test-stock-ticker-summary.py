#!/usr/bin/env python3
"""Replay Java's Stock Keeper summaries through the live Horizon screen."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
import re
from shutil import which
from subprocess import check_output
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
menus = import_module("test-list-filter-editor")
packager = import_module("test-packager-redstone")
TICKER = (10, 101, -8)
BURNER = (11, 101, -8)
SEAT = (9, 101, -8)
FREQUENCY = "[I;476,91,26,3]"
IRON = "minecraft:iron_ingot"
TRACE = re.compile(r"CREATE_STOCK_SUMMARY (\d+),(\d+),(\d+),(\d+),(\d+)")


def xyz(pos):
    return " ".join(map(str, pos))


def stock(host, quantity):
    host.command(f"/item replace block 14 101 -8 container.0 with {IRON} {quantity}")


def trace(host, tick):
    log = (host.socket.parent / "ctl.log").read_text(errors="replace")
    return next((tuple(map(int, row[1:])) for row in TRACE.findall(log) if int(row[0]) == tick), None)


def open_menu(actor, target, aim):
    actor.call("look-at", *aim)
    if isinstance(target, str):
        mp.until("the actor to target the seated pig", lambda:
                 (actor.call("looking-at").get("entity") or {}).get("type") == target)
    else:
        mp.until("the actor to target the Blaze Burner", lambda:
                 (actor.call("looking-at").get("block") or {}).get("pos") == list(target))
    actor.call("wait", 3)
    actor.call("mouse", "right", "click")
    mp.until("the Stock Keeper screen to open", lambda: actor.call("state")["screen"] == "mod")


def crop(actor, image, ffmpeg):
    actor.call("wait", 5)
    actor.call("screenshot", image)
    width, height = (value / 2 for value in menus.dimensions(image))
    rows = max(1, min(17, int((height - 126) // 20)))
    panel = 116 + rows * 20
    x, y = int((width - 226) // 2), int((height - panel) // 2)
    pixels = check_output((
        ffmpeg, "-v", "error", "-i", str(image), "-vf", f"crop=36:36:{2*(x+24)}:{2*(y+37)}",
        "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
    ))
    return pixels, (x, y)


def find_pig(actor):
    for mob in actor.call("mobs", 12)["near"]:
        if mob["kind"] == "minecraft:pig" and mob["passenger"]:
            return mob["pos"]
    return None


def use(host, actor, player, rows, images, ffmpeg):
    host.commands((
        "/gamerule spawn_mobs false",
        "/fill 5 100 -11 17 100 -4 minecraft:stone",
        f"/setblock {xyz(TICKER)} create:stock_ticker",
        f"/data merge block {xyz(TICKER)} {{Freq:{FREQUENCY}}}",
        f"/setblock {xyz(BURNER)} create:blaze_burner[blaze=smouldering]",
        "/setblock 14 101 -8 minecraft:barrel",
        "/setblock 15 101 -8 create:packager[facing=east]",
        "/setblock 15 102 -8 create:stock_link",
        f"/data merge block 15 102 -8 {{Freq:{FREQUENCY}}}",
        f"/tp {player} 11.5 101 -5.5",
        f"/item replace entity {player} hotbar.0 with minecraft:stick",
    ))
    stock(host, 12)
    mp.until("the Keeper actor to arrive with a Stick", lambda: (
        actor.call("state")["player"]["position"] == [11.5, 101.0, -5.5]
        and mp.count(actor, "minecraft:stick") == 1
    ))
    actor.call("select", "minecraft:stick")
    actor.call("options-set", "guiScale", "2")
    start = host.clock() - 3
    crops = {}
    for row in rows:
        tick, *expected = map(int, row.values())
        absolute = start + tick
        host.step_to(absolute)
        if tick == 5:
            stock(host, 3)
        open_menu(actor, BURNER, (11.5, 101.65, -7.5))
        mp.until(f"the authoritative summary at tick {tick}", lambda: trace(host, absolute) is not None)
        actual = trace(host, absolute)
        assert actual == tuple(expected), (tick, actual, expected)
        if tick in (4, 6, 24, 25):
            crops[tick], _ = crop(actor, images / f"tick-{tick}.png", ffmpeg)
        if tick < 27:
            actor.call("key", "escape", "tap")
            mp.until("the actor to close the summary", lambda: actor.call("state")["screen"] == "playing")
            actor.call("wait", 5)
            assert actor.call("state")["screen"] == "playing", ("Late menu reopen", tick)
    assert crops[4] == crops[6] == crops[24], "The stock display changed before the recent summary expired."
    assert crops[25] != crops[24], "The stock display did not change when the recent summary expired."
    fresh, origin = crop(actor, images / "fresh.png", ffmpeg)
    menus.click(actor, origin, (83, 25))
    actor.call("type", "copper")
    hidden, _ = crop(actor, images / "filtered.png", ffmpeg)
    assert hidden != fresh, "Searching for Copper must hide the Iron Ingot slot."
    actor.call("click-at", *menus.point(origin, (83, 25)), "right")
    visible, _ = crop(actor, images / "search-cleared.png", ffmpeg)
    assert visible == fresh, "Clearing the query must restore the stock slot."
    actor.call("key", "escape", "tap")
    mp.until("the summary to close before the keeper swap", lambda: actor.call("state")["screen"] == "playing")

    host.commands((
        f"/setblock {xyz(BURNER)} minecraft:air",
        f"/data merge block {xyz(TICKER)} {{Freq:[I;527,101,26,3]}}",
        "/data merge block 15 102 -8 {Freq:[I;527,101,26,3]}",
        f"/setblock {xyz(SEAT)} create:red_seat",
        "/summon minecraft:pig 9.5 104.25 -7.5",
        f"/tp {player} 9.5 101 -5.5",
    ))
    tick = host.clock()
    for since in range(1, 19):
        host.step_to(tick + since)
    mp.until("the actor to see the pig seated", lambda: find_pig(actor) is not None)
    x, y, z = find_pig(actor)
    open_menu(actor, "minecraft:pig", (x, y + .35, z))
    pig, _ = crop(actor, images / "seated-keeper.png", ffmpeg)
    assert pig == fresh, "The seated keeper must open the same stock summary."
    print(f"Matched {len(rows)} Java ticks for recent and accurate stock totals and contributing links.")
    print("Verified the offscreen stock count, search and seated keeper interaction.")

    stock(host, 8)
    tick = host.clock()
    for elapsed in range(1, 21):
        host.step_to(tick + elapsed)
    stale, _ = crop(actor, images / "held-open-stale.png", ffmpeg)
    assert stale == pig, "The stock total should remain cached at age 20."
    host.step_to(tick + 21)
    mp.until("the open menu to request fresh stock", lambda: trace(host, tick + 21) == (8, 1, 8, 1))
    refreshed, _ = crop(actor, images / "held-open-refreshed.png", ffmpeg)
    assert refreshed != pig, "The open screen did not show the refreshed stock count."
    host.command(f"/setblock {xyz(SEAT)} minecraft:air")
    host.step_to(tick + 22)
    mp.until("the Stock Keeper screen to close after removing its seat",
             lambda: actor.call("state")["screen"] == "playing")
    print("Verified periodic refresh while the screen stays open and closure after keeper removal.")



def tune_and_place(host, actor, player):
    with (ROOT / "fixtures/stock-ticker-tuning-java.csv").open() as source:
        tune, *placements = csv.DictReader(source)
    ticker = tune["type"]
    link = (10, 101, -16)
    targets = ((13, 101, -16), (16, 101, -16))
    host.commands((
        f"/gamemode survival {player}",
        "/fill 8 100 -18 18 100 -12 minecraft:stone",
        f"/setblock {xyz(link)} create:stock_link",
        f"/tp {player} 10.5 101 -13.5",
        f"/item replace entity {player} hotbar.0 with {ticker}",
    ))
    mp.until("the untuned Stock Ticker to reach the actor", lambda: mp.count(actor, ticker) == 1)
    actor.call("select", ticker)
    frequency = packager.block_value(host, link, "Freq")
    start = host.clock() - int(tune["tick"])
    actor.call("look-at", 10.5, 101.16, -15.5)
    mp.until("the actor to aim at the Stock Link", lambda:
             (actor.call("looking-at").get("block") or {}).get("pos") == list(link))
    actor.call("wait", 4)
    actor.call("mouse", "right", "click")

    def tuned():
        held = actor.call("inventory").get("held") or {}
        normalized = re.sub(r"\s", "", held.get("components") or "")
        return held["count"] == int(tune["held"]) if ticker in normalized and re.sub(r"\s", "", frequency) in normalized else False

    mp.until("the Ticker item to copy the typed frequency", tuned)
    for row, (x, y, z) in zip(placements, targets, strict=True):
        host.step_to(start + int(row["tick"]))
        sneak = row["action"] == "sneak_place"
        if sneak:
            host.command(f"/item replace entity {player} hotbar.0 with {ticker}")
            mp.until("the second Stock Ticker to reach the actor", lambda: mp.count(actor, ticker) == 1)
        host.command(f"/tp {player} {x+.5} {y} {z+2.5}")
        mp.until("the actor to approach the placement point", lambda:
                 actor.call("state")["player"]["position"] == [x+.5, y, z+2.5])
        actor.call("look-at", x+.5, y, z+.5)
        mp.until("the actor to aim at the Ticker support", lambda:
                 (actor.call("looking-at").get("block") or {}).get("pos") == [x, y-1, z])
        if sneak:
            actor.call("key", "shift", "down")
        try:
            actor.call("wait", 4)
            actor.call("mouse", "right", "click")
            mp.until(f"the Ticker to face {row['facing']}", lambda:
                     actor.call("block", x, y, z)["state"] == f"{ticker}[facing={row['facing']}]"
                     and mp.count(actor, ticker) == int(row["held"]))
        finally:
            if sneak:
                actor.call("key", "shift", "up")
        same = packager.block_value(host, (x, y, z), "Freq") == frequency
        assert same == (row["same_frequency"] == "true"), (row, same)
    print("Matched Java Stock Ticker frequency, normal facing and sneaking reversal.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    ffmpeg = which("ffmpeg")
    if ffmpeg is None:
        parser.error("FFmpeg is required for the offscreen stock slot comparison")
    with (ROOT / "fixtures/stock-ticker-summary-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    mode = "LAN" if args.lan else "Solo"
    env = {"HORIZON_NO_AUDIO": "1", "CREATE_STOCK_SUMMARY_TRACE": "1"}
    with ExitStack() as resources:
        host = resources.enter_context(fixture_world(
            args, f"StockTickerSummary{mode}", pack=args.pack, render=not args.lan, env=env,
        ))
        scratch = Path(resources.enter_context(TemporaryDirectory(prefix="hc-stock-summary-")))
        actor, player = host, "@s"
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            player = "StockGuest"
            actor = resources.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True, scenario="stock-summary",
                pack=args.pack, env={"HORIZON_NO_AUDIO": "1"},
            ))
            mp.until("the Stock Keeper guest to join", lambda: any(
                g["name"] == player and g["placed"] for g in host.call("lan", "status")["guests"]
            ))
        images = args.screenshots or scratch
        images.mkdir(parents=True, exist_ok=True)
        use(host, actor, player, rows, images, ffmpeg)
        tune_and_place(host, actor, player)


if __name__ == "__main__":
    main()
