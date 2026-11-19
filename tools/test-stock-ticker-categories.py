#!/usr/bin/env python3
"""Compare Java's category assignment through the live Horizon Stock Keeper."""
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

summary = import_module("test-stock-ticker-summary")
mp = summary.mp
menus = summary.menus
order = import_module("test-stock-ticker-order")
TRACE = re.compile(r"CREATE_STOCK_CATEGORY (\d+),(\d+),([^\r\n]*)")
STOCK = (("iron_ingot", 12), ("copper_ingot", 6), ("gold_ingot", 3), ("andesite", 2))


def filter_stack(name, *items):
    entries = ",".join(
        f'{{slot:{index},item:{{id:"minecraft:{item}",count:1}}}}'
        for index, item in enumerate(items)
    )
    return (
        '{id:"create:filter",count:1,components:'
        f'{{"minecraft:custom_name":{{text:"{name}"}},"create:filter_items":[{entries}]}}}}'
    )


def categories(host, *filters):
    host.command(f"/data merge block {summary.xyz(summary.TICKER)} {{Categories:[{','.join(filters)}]}}")


def observed(host, tick):
    log = (host.socket.parent / "ctl.log").read_text(errors="replace")
    return next(((int(count), groups) for at, count, groups in reversed(TRACE.findall(log))
                 if int(at) == tick), None)


def compare(host, tick, row):
    expected = (int(row["categories"]), row["groups"])
    try:
        mp.until(f"the category assignment at tick {row['tick']}", lambda: observed(host, tick) == expected)
    except RuntimeError as error:
        raise AssertionError((row["action"], expected, observed(host, tick))) from error


def pixels(ffmpeg, image, origin, rectangle):
    left, top = (2 * (base + offset) for base, offset in zip(origin, rectangle[:2], strict=True))
    width, height = (2 * edge for edge in rectangle[2:])
    return check_output((
        ffmpeg, "-v", "error", "-i", str(image), "-vf", f"crop={width}:{height}:{left}:{top}",
        "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
    ))


def group_pixels(ffmpeg, image, origin):
    icons = tuple(
        pixels(ffmpeg, image, origin, (28 + 20 * column, 60 + 20 * row, 9, 7))
        for row, column in ((0, 0), (0, 1), (2, 0), (4, 0))
    )
    headings = tuple(
        pixels(ffmpeg, image, origin, (32, 40 + 20 * row, 90, 10))
        for row in (0, 2, 4)
    )
    return icons, headings


def delta(left, right):
    return sum(abs(a - b) for a, b in zip(left, right, strict=True))


def compare_icons(initial, reordered):
    iron, gold, copper, andesite = initial
    new_iron, new_copper, new_gold, new_andesite = reordered
    separation = delta(gold, copper)
    assert separation > 1000, "The original two category item icons did not render distinctly"
    assert delta(gold, new_gold) < separation // 4, "Gold did not move to the second category"
    assert delta(copper, new_copper) < separation // 4, "Copper did not move to the first category"
    assert delta(iron, new_iron) < separation // 4, "Iron did not stay in the first matching category"
    assert delta(andesite, new_andesite) < separation // 4, "Unsorted Andesite moved during category reorder"


def use(host, actor, player, rows, images, ffmpeg):
    xyz = summary.xyz
    ticker, burner = summary.TICKER, summary.BURNER
    frequency = "[I;407,218,26,3]"
    first = filter_stack("Iron and Gold", "iron_ingot", "gold_ingot")
    second = filter_stack("Copper and Iron", "copper_ingot", "iron_ingot")
    host.commands((
        "/fill 5 100 -11 17 100 -4 minecraft:stone",
        f"/setblock {xyz(ticker)} create:stock_ticker",
        f"/data merge block {xyz(ticker)} {{Freq:{frequency}}}",
        f"/setblock {xyz(burner)} create:blaze_burner[blaze=smouldering]",
        "/setblock 14 101 -8 minecraft:barrel",
        "/setblock 15 101 -8 create:packager[facing=east]",
        "/setblock 15 102 -8 create:stock_link",
        f"/data merge block 15 102 -8 {{Freq:{frequency}}}",
        f"/tp {player} 11.5 101 -5.5",
        f"/item replace entity {player} hotbar.0 with minecraft:stick",
    ))
    for slot, (item, count) in enumerate(STOCK):
        host.command(f"/item replace block 14 101 -8 container.{slot} with minecraft:{item} {count}")
    categories(host, first, '{id:"minecraft:andesite",count:1}', second)
    mp.until("the actor to arrive at the Stock Keeper", lambda: (
        actor.call("state")["player"]["position"] == [11.5, 101.0, -5.5]
        and mp.count(actor, "minecraft:stick") == 1
    ))
    actor.call("select", "minecraft:stick")
    actor.call("options-set", "guiScale", "2")
    start = host.clock() - 3
    screenshots = {}
    for row in rows:
        tick = start + int(row["tick"])
        host.step_to(tick)
        if row["action"] == "completed":
            summary.open_menu(actor, burner, (11.5, 101.65, -7.5))
        else:
            categories(host, second, first)
        compare(host, tick, row)
        image = images / f"{row['action']}.png"
        origin, _ = order.panel(actor, image)
        screenshots[row["action"]] = group_pixels(ffmpeg, image, origin)
        assert host.clock() == tick
        print(f"{row['tick']} {row['action']}: {row['categories']} categories, {row['groups']}")
    initial_icons, (first_heading, second_heading, unsorted) = screenshots["completed"]
    reordered_icons, reordered_headings = screenshots["reordered"]
    compare_icons(initial_icons, reordered_icons)
    assert delta(first_heading, second_heading) > 1000, "The named headings must render distinctly"
    assert reordered_headings == (second_heading, first_heading, unsorted), "The headings must reorder with their groups"
    print("Matched both complete snapshots and verified that headings and items reordered with the menu open.")


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
        parser.error("FFmpeg is required for the offscreen category slot comparison")
    with (ROOT / "fixtures/stock-ticker-categories-java.csv").open() as source:
        rows = [row for row in csv.DictReader(source) if row["groups"] != "_"]
    mode = "LAN" if args.lan else "Solo"
    env = {"HORIZON_NO_AUDIO": "1", "CREATE_STOCK_CATEGORY_TRACE": "1"}
    with ExitStack() as resources:
        host = resources.enter_context(fixture_world(
            args, f"StockTickerCategories{mode}", pack=args.pack, render=not args.lan, env=env,
        ))
        scratch = Path(resources.enter_context(TemporaryDirectory(prefix="hc-stock-categories-")))
        player, actor = "@s", host
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            player = "StockGroupGuest"
            actor = resources.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True, scenario="stock-categories",
                pack=args.pack, env={"HORIZON_NO_AUDIO": "1"},
            ))
            mp.until("the Stock Keeper guest to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]
            ))
        images = args.screenshots or scratch
        images.mkdir(parents=True, exist_ok=True)
        use(host, actor, player, rows, images, ffmpeg)


if __name__ == "__main__":
    main()
