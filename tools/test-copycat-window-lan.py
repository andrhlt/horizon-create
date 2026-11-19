#!/usr/bin/env python3
"""Check host and guest Oak Window joins during survival Copycat interactions."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

window = import_module("test-window-ctm")
multiplayer = import_module("test-multiplayer")
X, Y, Z = 8, 111, -10
GUEST = "CwGuest"
PANEL = "create:copycat_panel[facing=north]"
OAK = "create:oak_window"
WRENCH = "create:wrench"


def frame_has_tile(player, screenshot, expected):
    player.call("look-at", X + .5, Y + .5, Z + .5)
    player.call("screenshot", screenshot)
    frame = window.image("ffmpeg", screenshot, scaled=True)
    try:
        window.check_frame(frame, 0, expected, "Oak Window", False)
    except RuntimeError:
        return False
    return True


def run(args, scratch):
    pack = window.diagnostic_pack(args.pack or ROOT / ".local/create.hmod", scratch)
    screenshot = scratch / "window.png"
    with fixture_world(args, "CopycatWindowLAN", render=True, pack=pack) as host:
        host.commands((
            "/time set noon", "/gamemode spectator",
            f"/fill {X-3} {Y-2} {Z+2} {X+3} {Y-2} {Z+5} minecraft:stone",
            window.block(X, Y, Z, OAK), window.block(X, Y + 1, Z, PANEL),
            f"/tp @s {X+2.2} {Y-1} {Z+3.8}",
        ))
        host.call("key", "f1", "tap")
        network = host.call("lan", "open", "0", "commands", "force")
        with multiplayer.joined_client(args, scratch, f"127.0.0.1:{network['port']}", GUEST,
                                        scenario="copycat-window-lan", render=True, pack=pack) as guest:
            multiplayer.until("guest entered", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            guest.call("key", "f1", "tap")
            host.commands((
                f"/gamemode survival {GUEST}", f"/tp {GUEST} {X+.5} {Y-1} {Z+3.4}",
                f"/item replace entity {GUEST} hotbar.0 with {OAK}",
            ))
            multiplayer.until("guest equipped an Oak Window", lambda: (
                multiplayer.count(guest, OAK) == 1
                and abs(guest.call("state")["player"]["position"][2] - (Z+3.4)) < .01
            ))
            for name, player in (("host", host), ("guest", guest)):
                multiplayer.until(f"{name} saw the standalone window", lambda: frame_has_tile(player, screenshot, 0))
            start = host.clock()
            guest.call("select", OAK)
            guest.call("look-at", "block", X, Y+1, Z)
            guest.call("mouse", "right", "click")
            multiplayer.until("guest applied the Oak Window", lambda: (
                OAK in host.command(f"/data get block {X} {Y+1} {Z} Material")
                and multiplayer.count(guest, OAK) == 0
            ))
            for name, player in (("host", host), ("guest", guest)):
                multiplayer.until(f"{name} saw tile 1 after the apply", lambda: frame_has_tile(player, screenshot, 1))
                print(f"{name} saw Java tile 1 after material application", flush=True)
            assert host.clock() == start, "The visual transition advanced an extra tick."
            host.command(f"/item replace entity {GUEST} hotbar.0 with {WRENCH}")
            multiplayer.until("guest equipped a Wrench", lambda: multiplayer.count(guest, WRENCH) == 1)
            guest.call("select", WRENCH)
            guest.call("look-at", "block", X, Y+1, Z)
            guest.call("mouse", "right", "click")
            multiplayer.until("guest recovered the oak", lambda: (
                "create:copycat_base" in host.command(f"/data get block {X} {Y+1} {Z} Material")
                and multiplayer.count(guest, OAK) == 1
            ))
            for name, player in (("host", host), ("guest", guest)):
                multiplayer.until(f"{name} saw tile 0 after the reset", lambda: frame_has_tile(player, screenshot, 0))
                print(f"{name} saw Java tile 0 after material reset", flush=True)
            assert host.clock() == start, "The visual transition advanced an extra tick."


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for attribute in ("ctl", "client", "resources"):
        parser.add_argument(attribute, type=Path)
    parser.add_argument("--pack", type=Path)
    with TemporaryDirectory(prefix="hc-cwl-") as directory:
        run(parser.parse_args(), Path(directory))
