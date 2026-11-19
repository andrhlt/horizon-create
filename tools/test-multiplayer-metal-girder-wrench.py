#!/usr/bin/env python3
"""Verify real guest wrench toggles both caps of an existing horizontal Girder pair."""
import argparse
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

GUEST = "GirderGuest"


def load(name):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


turn = load("test-metal-girder-wrench")
multiplayer = load("test-multiplayer")


def verify(args):
    with fixture_world(args, "GirderWrenchLAN", render=True, pack=args.pack) as host:
        turn.setup(host, 1)
        host.command("/tp @s 11.500 101 -8.500")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hc-gw-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, GUEST, render=True, scenario="multiplayer-girder-wrench", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/item replace entity {GUEST} hotbar.0 with {turn.WRENCH} 1",
            ))
            multiplayer.until("the guest to receive the wrench", lambda: (
                guest.call("inventory")["counts"].get(turn.WRENCH) == 1
            ))

            def teleport(feet):
                coords = " ".join(f"{coordinate:.3f}" for coordinate in feet)
                host.command(f"/tp {GUEST} {coords}")
                multiplayer.until("guest to reach the lower girder", lambda: (
                    guest.call("state")["player"]["position"] == list(feet)
                ))

            for flag in ("false", "true"):
                turn.turn(guest, 1, teleport=teleport)
                expected = ("x", "true", "false", flag, "false", flag)
                multiplayer.until("the host's pair to change together", lambda: turn.sample(host, 0, 1)[2:] == expected)
                multiplayer.until("the guest to see the same two flags", lambda: (
                    turn.sample(guest, 0, 1)[2:] == expected
                    and guest.call("inventory")["counts"].get(turn.WRENCH) == 1
                ))
    print("A survival guest disconnected and reconnected both caps and both clients saw the same pair state.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
