#!/usr/bin/env python3
"""Verify a guest disconnects and uncases a motor-driven host cog."""

import argparse
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

GUEST = "CasedCogGuest"


def load(name):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cogs = load("test-brass-cogwheel-casing")
multiplayer = load("test-multiplayer")


def teleport(host, guest, pos):
    coordinates = " ".join(f"{value:.3f}" for value in pos)
    host.command(f"/tp {GUEST} {coordinates}")
    multiplayer.until("guest position at the cog", lambda:
                      guest.call("state")["player"]["position"] == list(pos))


def verify(args):
    with fixture_world(args, "BrassCogwheelCasingLAN", render=True, pack=args.pack) as host:
        cogs.setup(host)
        host.step_to(host.clock() + 1)
        cogs.act(host, 3)
        host.step_to(host.clock() + 1)
        if cogs.sample(host, 0)[1:] != ("encased", "x", "true", "true", "2", "24.0000", "24.0000"):
            raise RuntimeError("Host did not preserve both faces, casing stack, and 24 RPM.")
        host.command("/tp @s 11.5 101 -8.5")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hc-cased-cog-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, GUEST, render=True, scenario="multiplayer-cased-cog", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/item replace entity {GUEST} hotbar.0 with {cogs.WRENCH} 1",
            ))
            teleport(host, guest, (10.65, 101, -9.5))
            multiplayer.until("the guest to receive the wrench", lambda: (
                guest.call("inventory")["counts"].get(cogs.WRENCH) == 1
            ))
            host.step_to(host.clock() + 1)
            cogs.act(guest, 6, teleport=False)
            host.step_to(host.clock() + 1)
            if cogs.sample(host, 0)[1:] != ("encased", "x", "false", "true", "2", "24.0000", "0.0000"):
                raise RuntimeError("Guest did not toggle the east end off while keeping power on the cog.")
            teleport(host, guest, (8.5, 101, -12.5))
            cogs.act(guest, 14, teleport=False)
            host.step_to(host.clock() + 1)
            if cogs.sample(host, 0)[1:] != ("cog", "x", "false", "false", "2", "24.0000", "24.0000"):
                raise RuntimeError("Guest did not uncase the cog and reconnect its shaft output.")
    print("The host cased a 24 RPM cog. The guest toggled its output off, then uncased it and restored 24 RPM.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
