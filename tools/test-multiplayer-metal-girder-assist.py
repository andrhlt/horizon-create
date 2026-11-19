#!/usr/bin/env python3
"""Verify a guest extends an existing wet Girder line without leaving a predicted block."""
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


girders = load("test-metal-girder-assist")
multiplayer = load("test-multiplayer")


def verify(args):
    with fixture_world(args, "GirderAssistLAN", render=True, pack=args.pack) as host:
        girders.setup(host, 4)
        host.command("/tp @s 12.500 101 -19.500")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hc-ga-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, GUEST, render=True, scenario="multiplayer-girder-assist", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/item replace entity {GUEST} hotbar.0 with {girders.GIRDER} 2",
            ))
            multiplayer.until("the guest to receive two girders", lambda: (
                guest.call("inventory")["counts"].get(girders.GIRDER) == 2
            ))

            def teleport(feet):
                position = " ".join(f"{value:.3f}" for value in feet)
                host.command(f"/tp {GUEST} {position}")
                multiplayer.until("guest to reach the guiding girder", lambda: (
                    guest.call("state")["player"]["position"] == list(feet)
                ))

            girders.place(guest, 4, teleport=teleport)
            target = girders.target(4)
            x, y, z = girders.ORIGIN
            ordinary = (x, y + 1, z)
            want = ("girder", "x", "true", "false", "false", "false", "true", "2")
            multiplayer.until("the host's new wet extension", lambda: (
                girders.sample(host, 0, 4)[2:] == want
                and host.call("block", *ordinary)["state"] == "minecraft:air"
            ))
            state = host.call("block", *target)["state"]
            multiplayer.until("the guest's authoritative beam and single-item cost", lambda: (
                guest.call("block", *target)["state"] == state
                and guest.call("block", *ordinary)["state"] == "minecraft:air"
                and guest.call("inventory")["counts"].get(girders.GIRDER) == 1
            ))
    print("The guest extended the host's line into source water, with one used item and no extra block.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
