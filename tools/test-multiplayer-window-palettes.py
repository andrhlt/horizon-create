#!/usr/bin/env python3
"""Place and waterlog window panes using separate Horizon players."""

import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

multiplayer = import_module("test-multiplayer")
PANE = "create:oak_window_pane"
GUEST = "WindowGuest"
FIRST = (8, 97, -9)
SECOND = (9, 97, -9)


def shares_state(players, position, **expected):
    for player in players:
        block = player.call("block", *position)
        if block["block"] != PANE:
            return False
        properties = dict(entry.split("=", 1) for entry in block["state"].split("[", 1)[1][:-1].split(","))
        if any(properties.get(name) != value for name, value in expected.items()):
            return False
    return True


def run(args, scratch):
    with fixture_world(args, "Windows-LAN", pack=args.pack, render=True) as host:
        host.commands((
            "/fill 4 96 -13 12 96 -6 minecraft:smooth_stone",
            "/fill 4 97 -13 12 101 -6 minecraft:air",
            "/tp @s 6.5 97 -8.5",
            "/gamemode survival",
            f"/item replace entity @s hotbar.0 with {PANE}",
        ))
        network = host.call("lan", "open", "0", "commands", "force")
        with multiplayer.joined_client(args, scratch, f"127.0.0.1:{network['port']}", GUEST,
                                       render=True, scenario="windows-lan", pack=args.pack) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/tp {GUEST} 10.5 97 -8.5",
                f"/item replace entity {GUEST} hotbar.0 with {PANE}",
            ))
            multiplayer.until("guest inventory and pose", lambda: (
                multiplayer.count(guest, PANE) == 1
                and guest.call("state")["player"]["position"] == [10.5, 97.0, -8.5]
            ))
            players = (host, guest)
            for player, (x, y, z) in zip(players, (FIRST, SECOND), strict=True):
                player.call("select", PANE)
                player.call("interact", x, y - 1, z, "up")
                multiplayer.until("the player's pane to be consumed", lambda: multiplayer.count(player, PANE) == 0)
            multiplayer.until("both pane connections", lambda: (
                shares_state(players, FIRST, east="true")
                and shares_state(players, SECOND, west="true")
            ))
            host.command(f"/item replace entity {GUEST} hotbar.0 with minecraft:water_bucket")
            multiplayer.until("the guest water bucket", lambda: multiplayer.count(guest, "minecraft:water_bucket") == 1)
            guest.call("select", "minecraft:water_bucket")
            guest.call("interact", *SECOND, "east")
            multiplayer.until("the waterlogged connected pane", lambda: (
                shares_state(players, SECOND, west="true", waterlogged="true")
                and multiplayer.count(guest, "minecraft:bucket") == 1
            ))
    print("Host and guest each placed a pane in survival, saw both joins, and saw guest waterlogging.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    with TemporaryDirectory(prefix="hc-window-lan-") as scratch:
        run(parser.parse_args(), Path(scratch))
