#!/usr/bin/env python3
"""Check actual cog rim placement across a host and guest, including prediction."""

import argparse
import csv
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

GUEST = "CogGuest"


def load(name):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cogs = load("test-cogwheel-rim-assist")
multiplayer = load("test-multiplayer")


def verify(args):
    with (ROOT / "fixtures/cogwheel-rim-assist-java.csv").open() as stream:
        _, *rows = list(csv.reader(stream))
    with fixture_world(args, "CogwheelRimLAN", render=True, pack=args.pack) as host:
        host.command("/gamemode survival")
        if cogs.place(host, rows[1]) != tuple(rows[1][4:7]):
            raise RuntimeError("The host's mixed-size placement did not match Java.")
        x, y, z = 23, 101, -10
        host.commands((
            f"/fill {x - 3} {y - 1} {z - 4} {x + 3} {y - 1} {z + 2} minecraft:smooth_stone",
            f"/fill {x - 2} {y} {z - 2} {x + 2} {y + 3} {z + 2} minecraft:air",
            f"/setblock {x} {y} {z} create:large_cogwheel[axis=y]",
            f"/tp @s {x - 2:.1f} {y} {z + 1.5}"
        ))
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hc-cog-assist-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, GUEST, render=True, scenario="multiplayer-cog-assist", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            feet = (x + 0.85, y, z - 2.15)
            coords = " ".join(f"{value:.3f}" for value in feet)
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/tp {GUEST} {coords}",
                f"/item replace entity {GUEST} hotbar.0 with {cogs.LARGE} 2",
            ))
            multiplayer.until("the guest to reach the large cog", lambda: (
                guest.call("state")["player"]["position"] == list(feet)
            ))
            multiplayer.until("the guest to receive two cogs", lambda: (
                guest.call("inventory")["counts"].get(cogs.LARGE) == 2
            ))
            host.step_to(host.clock() + 1)
            guest.call("select", cogs.LARGE)
            guest.call("look-at", x + 0.96, y + 0.62, z + 0.5)
            guest.call("wait", 2)
            hit = guest.call("looking-at")["block"]
            if hit["pos"] != [x, y, z]:
                raise RuntimeError(f"Guest did not hit the intended mounting gear: {hit}")
            guest.call("mouse", "right", "down")
            guest.call("wait", 1)
            guest.call("mouse", "right", "up")
            target = (x + 1, y + 1, z)
            expected = "create:large_cogwheel[axis=x"
            multiplayer.until("the guest's perpendicular cog to reach the host", lambda:
                              host.call("block", *target)["state"].startswith(expected))
            multiplayer.until("the guest to see only the server's placement", lambda: (
                guest.call("block", *target)["state"].startswith(expected)
                and guest.call("block", x, y + 1, z)["state"] == "minecraft:air"
                and guest.call("inventory")["counts"].get(cogs.LARGE) == 1
            ))
    print("The host placed a mixed diagonal and the guest placed a perpendicular large pair, with one consumed and no ghost block.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    verify(args)


if __name__ == "__main__":
    main()
