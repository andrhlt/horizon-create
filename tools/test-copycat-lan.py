#!/usr/bin/env python3
"""Replay a player's material application and Wrench removal while a second Horizon client sees it."""

from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world
COPYCAT = import_module("test-copycat")

multiplayer = import_module("test-multiplayer")
window = import_module("test-window-ctm")
GUEST = "CopycatGuest"
GOLD = "minecraft:gold_block"
WRENCH = "create:wrench"
TARGET = (8.99, 170.095, 23.5)

def gold_pixels(player, path):
    player.call("screenshot", path)
    pixels = window.image("ffmpeg", path, scaled=True)
    points = {
        (x, y)
        for y in range(100, 245)
        for x in range(260, 390)
        for r, g, b in (window.rgb_at(pixels, x, y),)
        if r > 120 and r > 1.45 * b and g > 1.35 * b
    }
    largest = 0
    # Wrench reset leaves small separate particles on the same frozen game tick.
    while points:
        region = [points.pop()]
        for x, y in region:
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in points:
                    points.remove(neighbor)
                    region.append(neighbor)
        largest = max(largest, len(region))
    return largest


def run(args, scratch):
    frame = scratch / "material.png"
    with fixture_world(args, "Copycat-LAN", pack=args.pack, render=True) as host:
        host.commands((
            "/time set noon",
            "/fill 6 168 19 12 168 28 minecraft:stone",
            "/setblock 8 170 23 create:copycat_panel[facing=up]",
            "/gamemode spectator",
            "/tp @s 8.5 171.4 26.8",
        ))
        host.call("look-at", 8.5, 170.10, 23.5)
        host.call("key", "f1", "tap")
        network = host.call("lan", "open", "0", "commands", "force")
        with multiplayer.joined_client(args, scratch, f"127.0.0.1:{network['port']}", GUEST,
                                       scenario="copycat-lan", render=True, pack=args.pack) as guest:
            multiplayer.until("guest entered", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/tp {GUEST} 10.5 169.0 23.5",
                f"/item replace entity {GUEST} hotbar.0 with {GOLD}",
            ))
            multiplayer.until("guest can use the Gold Block", lambda: (
                multiplayer.count(guest, GOLD) == 1
                and guest.call("state")["player"]["position"] == [10.5, 169.0, 23.5]
            ))
            guest.call("key", "f1", "tap")
            guest.call("look-at", *TARGET)
            assert gold_pixels(host, frame) == gold_pixels(guest, frame) == 0
            guest.call("select", GOLD)
            start = host.clock()
            guest.call("mouse", "right", "click")
            multiplayer.until("one authoritative material application", lambda: (
                COPYCAT.material_tag(host)[0] == GOLD and multiplayer.count(guest, GOLD) == 0
            ))
            host.call("look-at", 8.5, 170.10, 23.5)
            for name, player in (("host", host), ("guest", guest)):
                screenshot = scratch / f"lan-{name}.png"
                value = gold_pixels(player, screenshot)
                print(name, value, flush=True)
                multiplayer.until(f"the gold appearance on {name}", lambda: gold_pixels(player, screenshot) > 250)
            assert host.clock() == start
            host.command(f"/item replace entity {GUEST} hotbar.0 with {WRENCH}")
            multiplayer.until("guest can use the Wrench", lambda: multiplayer.count(guest, WRENCH) == 1)
            guest.call("select", WRENCH)
            guest.call("mouse", "right", "click")
            multiplayer.until("the copied material was returned once", lambda: (
                COPYCAT.material_tag(host)[0] == "create:copycat_base" and multiplayer.count(guest, GOLD) == 1
            ))
            for name, player in (("host", host), ("guest", guest)):
                screenshot = scratch / f"lan-{name}-wrenched.png"
                print("reset", name, gold_pixels(player, screenshot), flush=True)
                multiplayer.until(f"the original appearance on {name}", lambda: gold_pixels(player, screenshot) < 100)
            assert host.clock() == start
    print("Host and guest saw the same Copycat material application and reset on the action tick.")

if __name__ == "__main__":
    with TemporaryDirectory(prefix="hc-copycat-lan-") as directory:
        run(COPYCAT.parse_args(), Path(directory))
