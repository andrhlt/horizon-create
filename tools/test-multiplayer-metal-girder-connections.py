#!/usr/bin/env python3
"""Verify a guest's placed post joins the host's waterlogged Girder shaft."""
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


connections = load("test-metal-girder-connections")
multiplayer = load("test-multiplayer")


def verify(args):
    with fixture_world(args, "GirderConnectionsLAN", render=True, pack=args.pack) as host:
        connections.setup(host)
        host.command("/fill 4 100 -24 14 100 -5 minecraft:smooth_stone")
        x, y, z = connections.origin(2)
        host.command(f"/tp @s {x + 3.5:.3f} {y}.000 {z + 1.5:.3f}")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hc-gc-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, GUEST, render=True, scenario="multiplayer-girder-connections", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            feet = (x + 0.5, y, z - 2.5)
            coords = " ".join(f"{coordinate:.3f}" for coordinate in feet)
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/tp {GUEST} {coords}",
                f"/item replace entity {GUEST} hotbar.0 with {connections.GIRDER} 1",
            ))
            multiplayer.until("the guest to arrive and receive one girder", lambda: (
                guest.call("state")["player"]["position"] == list(feet)
                and guest.call("inventory")["counts"].get(connections.GIRDER) == 1
            ))
            guest.call("select", connections.GIRDER)
            guest.call("look-at", x + 0.5, y + 0.92, z + 0.5)
            guest.call("wait", 2)
            hit = guest.call("looking-at").get("block")
            if not hit or hit["pos"] != [x, y, z] or hit["face"] != "up":
                raise RuntimeError(f"Guest missed the encased girder's top face: {hit}")
            guest.call("mouse", "right", "down")
            guest.call("wait", 1)
            guest.call("mouse", "right", "up")
            expected = ("x", "false", "false", "true", "false", "true")
            multiplayer.until("the host's attached wet cap", lambda: connections.sample(host, 0, 2)[2:] == expected)
            state = host.call("block", x, y, z)["state"]
            multiplayer.until("the guest's matching cap, post, and inventory", lambda: (
                guest.call("block", x, y, z)["state"] == state
                and guest.call("block", x, y + 1, z)["state"].startswith(connections.GIRDER)
                and guest.call("inventory")["counts"].get(connections.GIRDER, 0) == 0
            ))
            host.command(f"/setblock {x} {y + 1} {z} minecraft:air")
            wanted = ("x", "false", "false", "false", "false", "true")
            multiplayer.until("the host cap to detach", lambda: connections.sample(host, 0, 2)[2:] == wanted)
            state = host.call("block", x, y, z)["state"]
            multiplayer.until("the guest to see the detached wet block", lambda: guest.call("block", x, y, z)["state"] == state)
    print("A guest placed a post over the wet encased girder, and both clients saw its cap attach and detach.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
