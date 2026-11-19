#!/usr/bin/env python3
"""Replay the original Requester ghost slots and settings through Horizon's live menu."""

import argparse
from contextlib import ExitStack
import csv
import re
from importlib import import_module
from pathlib import Path
from shutil import which
from subprocess import check_output
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
filters = import_module("test-list-filter-editor")
packager = import_module("test-packager-redstone")
snbt = import_module("test-frogport-menu").clipboard_snbt
POS = (10, 101, -8)
COPPER = "minecraft:copper_ingot"
SCREEN = "mod"


def settings(host):
    raw = packager.block_value(host, POS, "EncodedRequest")
    order = snbt(raw)
    entries = order["ordered_stacks"]["entries"]
    return (
        ",".join(f'{entry["item_stack"]["id"]}={entry["count"]}' for entry in entries),
        packager.block_value(host, POS, "EncodedAddress").strip('"'),
        int(packager.block_value(host, POS, "AllowPartial").rstrip("b")) != 0,
    )


def expected(row):
    return row["order"], row["address"], row["allow_partial"] == "true"


def open_screen(actor, position=POS):
    x, y, z = position
    actor.call("look-at", x + .5, y + .5, z + .35)
    mp.until("the player to target the Requester", lambda:
             (actor.call("looking-at").get("block") or {}).get("pos") == list(position))
    actor.call("wait", 4)
    actor.call("mouse", "right", "click")
    mp.until("the Requester configuration screen to open", lambda:
             actor.call("state")["screen"] == SCREEN)


def capture(actor, path):
    actor.call("scroll-at", 16, 16, 0)
    actor.call("wait", 5)
    actor.call("screenshot", path)


def origin(path):
    w, h = filters.dimensions(path)
    return ((w / 2 - 232) // 2, (h / 2 - 228) // 2)


def ghost_pixels(ffmpeg, path, panel, index):
    x, y = filters.point(panel, (27 + 20 * index, 28))
    return check_output((
        ffmpeg, "-v", "error", "-i", str(path), "-vf", f"crop=32:16:{x*2:.0f}:{y*2:.0f}",
        "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
    ))


def carried(actor, item, count):
    stack = actor.call("inventory").get("carried") or {}
    return stack.get("item") == item and stack.get("count", 0) == count


def use(host, actor, player, rows, images, ffmpeg):
    xyz = packager.xyz
    host.commands((
        "/fill 6 100 -12 15 100 -4 minecraft:smooth_stone",
        f"/setblock {xyz(POS)} create:redstone_requester",
        f'/data merge block {xyz(POS)} {{EncodedAddress:"Smelting",AllowPartial:0b,EncodedRequest:'
        '{ordered_stacks:{entries:[{item_stack:{id:"minecraft:iron_ingot",count:1},count:8},'
        '{item_stack:{id:"minecraft:gold_ingot",count:1},count:3}]},ordered_crafts:[]}}',
        f"/tp {player} 10.5 101 -5.5",
        f"/gamemode survival {player}",
        f"/item replace entity {player} hotbar.0 with {COPPER} 5",
    ))
    feet = (10.5, 101, -5.5)
    mp.until("the actor to reach the Requester with five Copper Ingots", lambda: (
        actor.call("state")["player"]["position"] == list(feet)
        and mp.count(actor, COPPER) == 5
    ))
    actor.call("options-set", "guiScale", "2")
    start = host.clock() - 2
    initial, sample, closed, configured = rows

    open_screen(actor)
    shot = images / "initial.png"
    capture(actor, shot)
    panel = origin(shot)
    assert settings(host) == expected(initial)
    assert carried(actor, None, 0)
    before = [ghost_pixels(ffmpeg, shot, panel, i) for i in range(3)]
    assert before[0] != before[2] and before[1] != before[2]
    assert host.clock() == start + int(initial["tick"])

    host.step_to(start + int(sample["tick"]))
    for point in ((12, 207), (32, 33), (72, 33)):
        filters.click(actor, panel, point)
        actor.call("wait", 4)
    mp.until("five Copper Ingots to remain on the cursor", lambda: carried(actor, COPPER, 5))
    shot = images / "sampled.png"
    capture(actor, shot)
    after = [ghost_pixels(ffmpeg, shot, panel, i) for i in range(3)]
    assert after[0] != before[0] and after[2] != before[2]
    assert after[1] == before[1]
    assert settings(host) == expected(sample)
    assert host.clock() == start + int(sample["tick"])

    filters.click(actor, panel, (12, 207))
    mp.until("all five Copper Ingots to return to the player", lambda:
             carried(actor, None, 0) and mp.count(actor, COPPER) == 5)
    filters.click(actor, panel, (52, 33))
    actor.call("wait", 5)
    host.step_to(start + int(closed["tick"]))
    filters.click(actor, panel, (209, 104))
    mp.until("the ghost slots to close and compact", lambda:
             actor.call("state")["screen"] == "playing" and settings(host) == expected(closed))

    # The configuration packet in Java applies quantities after ghost slot compaction.
    # Reopening the compacted slots lets the replay submit those same amounts by scrolling.
    open_screen(actor)
    reopened = images / "reopened.png"
    capture(actor, reopened)
    panel = origin(reopened)
    for index, steps in ((0, 4), (1, 1)):
        x, y = filters.point(panel, (32 + 20 * index, 33))
        for _ in range(steps):
            actor.call("scroll-at", x, y, 1)
            actor.call("wait", 5)
    actor.call("click-at", *filters.point(panel, (64, 72)), "right")
    actor.call("type", configured["address"])
    filters.click(actor, panel, (20, 103))
    capture(actor, images / "configured.png")
    filters.click(actor, panel, (209, 104))
    try:
        mp.until("the Java order amounts, address and partial toggle to save", lambda:
                 actor.call("state")["screen"] == "playing" and settings(host) == expected(configured))
    except RuntimeError as error:
        raise AssertionError((settings(host), expected(configured))) from error
    assert mp.count(actor, COPPER) == 5
    assert host.clock() == start + int(configured["tick"])
    print(f"Matched {len(rows)} Java Requester menu snapshots and retained all five sample ingots.")


def use_tuned_requester(host, actor, player, images):
    with (ROOT / "fixtures/stock-link-requester-tuning-java.csv").open() as source:
        tuning, placement = csv.DictReader(source)
    requester = tuning["type"]
    source, machine, link = (11, 100, -8), (12, 100, -8), (12, 101, -8)
    target = (14, 101, -8)
    xyz = packager.xyz
    host.commands((
        f"/setblock {xyz(source)} minecraft:barrel",
        f"/item replace block {xyz(source)} container.0 with {COPPER} 4",
        f"/setblock {xyz(machine)} create:packager[facing=east]",
        f"/setblock {xyz(link)} create:stock_link",
        f"/item replace entity {player} hotbar.1 with {requester}",
        f"/tp {player} 12.5 101 -5.5",
    ))
    now = host.clock()
    frequency = packager.block_value(host, link, "Freq")
    mp.until("the untuned Requester to reach the actor", lambda: mp.count(actor, requester) == 1)
    actor.call("select", requester)
    actor.call("look-at", 12.5, 101.16, -7.5)
    mp.until("the Stock Link to be in reach", lambda:
             (actor.call("looking-at").get("block") or {}).get("pos") == list(link))
    actor.call("wait", 5)
    actor.call("mouse", "right", "click")

    def tuned():
        item = actor.call("inventory")["held"] or {}
        components = item.get("components") or ""
        if requester in components and re.sub(r"\s", "", frequency) in re.sub(r"\s", "", components):
            return item
        return None

    item = mp.until("the Requester item to copy the Java frequency", tuned)
    assert item["count"] == int(tuning["held_count"])
    assert host.clock() == now
    now += int(placement["tick"]) - int(tuning["tick"])
    host.step_to(now)

    host.command(f"/tp {player} 14.5 101 -5.5")
    mp.until("the actor to approach the placement position", lambda:
             actor.call("state")["player"]["position"] == [14.5, 101, -5.5])
    actor.call("look-at", 14.5, 101, -7.5)
    mp.until("the support face to be targeted", lambda:
             (actor.call("looking-at").get("block") or {}).get("pos") == [14, 100, -8])
    actor.call("wait", 5)
    actor.call("mouse", "right", "click")
    mp.until("the tuned Requester to be placed and spent", lambda: (
        actor.call("block", *target)["state"].startswith(requester)
        and mp.count(actor, requester) == int(placement["held_count"])
    ))
    assert packager.block_value(host, target, "Freq") == frequency
    assert host.clock() == now
    print("The Requester tuned on the Stock Link and kept that frequency on placement.")

    open_screen(actor, target)
    shot = images / "tuned-order.png"
    capture(actor, shot)
    panel = origin(shot)
    filters.click(actor, panel, (12, 207), shift=True)
    actor.call("wait", 8)
    x, y = filters.point(panel, (32, 33))
    for _ in range(2):
        actor.call("scroll-at", x, y, 1)
    filters.click(actor, panel, (64, 72))
    actor.call("type", "Warehouse")
    filters.click(actor, panel, (209, 104))
    mp.until("the configured order to reach the host", lambda:
             packager.block_value(host, target, "EncodedAddress").strip('"') == "Warehouse")
    order = snbt(packager.block_value(host, target, "EncodedRequest"))["ordered_stacks"]["entries"]
    assert len(order) == 1 and order[0]["count"] == 3 and order[0]["item_stack"]["id"] == COPPER, order
    host.command("/setblock 15 101 -8 minecraft:redstone_block")
    assert packager.block_value(host, target, "Success") == "1b"
    contents = packager.block_value(host, machine, 'HeldBox.components."create:package_contents"')
    address = packager.block_value(host, machine, 'HeldBox.components."create:package_address"')
    assert "minecraft:copper_ingot=3" in packager.describe_slots(contents, "slot")
    assert address.strip('"') == "Warehouse"
    assert packager.describe_slots(packager.block_value(host, source, "Items"), "Slot") == f"0:{COPPER}=1"
    assert host.clock() == now
    print("The menu-programmed Requester shipped three Copper Ingots from its tuned network.")


def run(args):
    mode = "LAN" if args.lan else "Solo"
    env = {"HORIZON_NO_AUDIO": "1"}
    ffmpeg = which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to compare the rendered Requester ghost slots")
    with (ROOT / "fixtures/stock-link-requester-menu-java.csv").open() as file:
        rows = list(csv.DictReader(file))
    with ExitStack() as resources:
        host = resources.enter_context(fixture_world(
            args, f"RequesterMenu{mode}", pack=args.pack, render=not args.lan, env=env,
        ))
        scratch = Path(resources.enter_context(TemporaryDirectory(prefix="hc-requester-menu-")))
        actor, player = host, "@s"
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            player = "RequesterGuest"
            actor = resources.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True, scenario="requester-menu",
                pack=args.pack, env=env,
            ))
            mp.until("the Requester menu guest to join", lambda: any(
                g["name"] == player and g["placed"] for g in host.call("lan", "status")["guests"]
            ))
        images = args.screenshots or scratch
        images.mkdir(parents=True, exist_ok=True)
        use(host, actor, player, rows, images, ffmpeg)
        use_tuned_requester(host, actor, player, images)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--screenshots", type=Path)
    run(parser.parse_args())
