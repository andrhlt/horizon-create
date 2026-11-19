#!/usr/bin/env python3
"""Verify a guest can place a waterlogged Metal Girder on the host."""
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


girders = load("test-metal-girder-placement")
multiplayer = load("test-multiplayer")


def verify(args):
    with fixture_world(args, "GirderPlacementLAN", render=True, pack=args.pack) as host:
        girders.setup(host, 3)
        host.command("/fill 4 100 -15 15 100 -5 minecraft:smooth_stone")
        host.command("/tp @s 11.500 101 -8.500")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hc-gp-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, GUEST, render=True, scenario="multiplayer-girder-placement", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            support, feet, aim, face = girders.CASES[3]
            position = " ".join(f"{coordinate:.3f}" for coordinate in feet)
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/tp {GUEST} {position}",
                f"/item replace entity {GUEST} hotbar.0 with {girders.GIRDER} 2",
            ))
            multiplayer.until("the guest to arrive and receive two girders", lambda: (
                guest.call("state")["player"]["position"] == list(feet)
                and guest.call("inventory")["counts"].get(girders.GIRDER) == 2
            ))
            guest.call("select", girders.GIRDER)
            guest.call("look-at", *aim)
            guest.call("wait", 2)
            hit = guest.call("looking-at").get("block")
            if not hit or hit["pos"] != list(support) or hit["face"] != face:
                raise RuntimeError(f"Guest missed the support's south face: {hit}")
            guest.call("mouse", "right", "down")
            guest.call("wait", 1)
            guest.call("mouse", "right", "up")
            want = ("girder", "z", "false", "true", "false", "false", "true", "2")
            multiplayer.until("the host's original wet beam state", lambda: girders.sample(host, 0, 3)[2:] == want)
            state = host.call("block", *girders.TARGET)["state"]
            multiplayer.until("the guest's authoritative beam and inventory", lambda: (
                guest.call("block", *girders.TARGET)["state"] == state
                and guest.call("inventory")["counts"].get(girders.GIRDER) == 1
            ))
    print("A survival guest placed one Z-axis beam into source water and both clients saw the same wet state.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
