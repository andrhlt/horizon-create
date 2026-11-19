#!/usr/bin/env python3
"""Check guest shaft casing, held items and wrench removal on the host’s network."""

import argparse
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

GUEST = "CasingGuest"


def load(name):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


casing = load("test-shaft-casing")
multiplayer = load("test-multiplayer")


def verify(args):
    with fixture_world(args, "ShaftCasingLAN", render=True, pack=args.pack) as host:
        casing.setup(host)
        host.step_to(host.clock() + 1)
        casing.apply(host, 0)
        host.step_to(host.clock() + 1)
        if casing.sample(host, 0, 0)[2:] != ("encased", "x", "false", "2", "24.0000"):
            raise RuntimeError("The host’s shaft did not preserve its axis, casing stack, and 24 RPM.")
        host.command("/tp @s 13.5 101 -8.5")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hc-shaft-casing-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, GUEST, render=True, scenario="multiplayer-shaft-casing", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/tp {GUEST} 16.5 101 -12.1",
                f"/item replace entity {GUEST} hotbar.0 with create:brass_casing 2",
                f"/item replace entity {GUEST} hotbar.1 with create:wrench 1",
            ))
            multiplayer.until("the guest to reach the shaft", lambda: (
                guest.call("state")["player"]["position"] == [16.5, 101.0, -12.1]
            ))
            host.step_to(host.clock() + 1)
            multiplayer.until("the guest to see the brass casing stack", lambda: (
                guest.call("inventory")["counts"].get("create:brass_casing") == 2
            ))
            casing.apply(guest, 1, teleport=False)
            host.step_to(host.clock() + 1)
            pos = casing.LANES[1][0]
            multiplayer.until("the guest’s casing to change the server shaft", lambda: (
                host.call("block", *pos)["state"].startswith("create:brass_encased_shaft[axis=z")
            ))
            multiplayer.until("the guest to keep both brass casings", lambda: (
                guest.call("inventory")["counts"].get("create:brass_casing") == 2
            ))
            casing.apply(guest, 1, wrench=True, teleport=False)
            host.step_to(host.clock() + 1)
            multiplayer.until("the guest to uncase the server shaft", lambda: (
                host.call("block", *pos)["state"].startswith("create:shaft[axis=z")
            ))
            if casing.sample(host, 0, 1)[-1] != "40.0000":
                raise RuntimeError("The guest’s wrench changed the shaft’s network speed.")
    print("The host cased an Andesite shaft, and the guest cased and uncased Brass while preserving 40 RPM and both casings.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
