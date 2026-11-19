#!/usr/bin/env python3
"""Verify a guest receives both original loot products for a wet encased girder."""
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


replay = load("test-metal-girder-pickup")
shaft = replay.shaft
multiplayer = load("test-multiplayer")


def verify(args):
    with fixture_world(args, "MetalGirderPickupLAN", render=True, pack=args.pack) as host:
        replay.setup(host, 1)
        host.step_to(host.clock() + 1)
        if replay.sample(host, 0, 1)[2:] != ("encased", "0", "0", "0", "0", "32.0000"):
            raise RuntimeError("Host setup did not start from 32 RPM and an empty shaft inventory.")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hc-gp-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, GUEST, render=True, scenario="multiplayer-girder-pickup", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/item replace entity {GUEST} hotbar.0 with {shaft.WRENCH} 1",
            ))
            multiplayer.until("the guest to receive a wrench", lambda: (
                guest.call("inventory")["counts"].get(shaft.WRENCH) == 1
            ))

            def teleport(feet):
                coordinates = " ".join(f"{value:.3f}" for value in feet)
                host.command(f"/tp {GUEST} {coordinates}")
                multiplayer.until("guest arrival at the girder", lambda: (
                    guest.call("state")["player"]["position"] == list(feet)
                ))

            replay.pickup(guest, teleport=teleport)
            host.step_to(host.clock() + 1)
            if replay.sample(host, 0, 1)[2:] != ("water", "0", "0", "0", "0", "0.0000"):
                raise RuntimeError("Guest pickup did not leave water and stop the host's output.")
            multiplayer.until("guest to see the water and receive one item of each kind", lambda: (
                guest.call("block", *shaft.BASE)["state"].startswith("minecraft:water")
                and guest.call("inventory")["counts"].get(shaft.GIRDER) == 1
                and guest.call("inventory")["counts"].get(shaft.SHAFT) == 1
            ))
    print("The guest crouch-picked the powered wet girder and received one shaft and girder. The host saw water, no loose items and zero RPM.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
