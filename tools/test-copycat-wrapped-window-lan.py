#!/usr/bin/env python3
"""Observe a painted Panel's changes as its same-material neighbour is added and removed."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

wrapped = import_module("test-copycat-wrapped-window")
lan = import_module("test-copycat-window-lan")
multiplayer = import_module("test-multiplayer")
X, Y, Z = lan.X, lan.Y, lan.Z
GUEST = "CwWrapGuest"


def run(args, scratch):
    pack = wrapped.diagnostic_pack(args.pack or ROOT / ".local/create.hmod", scratch)
    with fixture_world(args, "CopycatWrappedWindowLAN", render=True, pack=pack) as host:
        host.commands((
            "/time set noon", "/gamemode spectator",
            lan.window.block(X, Y, Z, lan.PANEL),
            f"/tp @s {X+2.2} {Y-1} {Z+3.8}",
        ))
        wrapped.paint(host, X, Y, Z, lan.OAK)
        host.call("key", "f1", "tap")
        network = host.call("lan", "open", "0", "commands", "force")
        with multiplayer.joined_client(args, scratch, f"127.0.0.1:{network['port']}", GUEST,
                                        scenario="copycat-wrapped-window", render=True, pack=pack) as guest:
            multiplayer.until("guest entered", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            guest.call("key", "f1", "tap")
            host.commands((
                f"/gamemode spectator {GUEST}",
                f"/tp {GUEST} {X+.5} {Y-1} {Z+3.4}",
            ))
            multiplayer.until("guest at the Panel", lambda: (
                abs(guest.call("state")["player"]["position"][2] - (Z+3.4)) < .01
            ))
            clock = host.clock()
            material = host.command(f"/data get block {X} {Y} {Z} Material")
            assert lan.OAK in material
            for state, tile in (("minecraft:air", 0), (lan.OAK, 1), ("minecraft:air", 0)):
                host.command(lan.window.block(X, Y + 1, Z, state))
                for name, player in (("host", host), ("guest", guest)):
                    capture = scratch / f"{name}.png"
                    multiplayer.until(f"{name} saw the painted Panel's Java tile {tile}",
                                      lambda: lan.frame_has_tile(player, capture, tile))
                assert host.command(f"/data get block {X} {Y} {Z} Material") == material
                assert clock == host.clock()
    print("Host and guest saw the painted Panel join and separate during the same frozen server tick.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for attribute in ("ctl", "client", "resources"):
        parser.add_argument(attribute, type=Path)
    parser.add_argument("--pack", type=Path)
    with TemporaryDirectory(prefix="hc-ww-") as directory:
        run(parser.parse_args(), Path(directory))
