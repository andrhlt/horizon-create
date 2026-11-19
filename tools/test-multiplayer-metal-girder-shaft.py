#!/usr/bin/env python3
"""Check authoritative wet girder shaft use with a host and guest."""
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


shaft = load("test-metal-girder-shaft")
multiplayer = load("test-multiplayer")


def verify(args):
    with fixture_world(args, "MetalGirderShaftLAN", render=True, pack=args.pack) as host:
        shaft.setup(host, 0)
        host.step_to(host.clock() + 1)
        shaft.interact(host, 0, True)
        host.step_to(host.clock() + 1)
        encased = ("encased", "z", "false", "false", "true", "true", "true", "1", "32.0000", "32.0000")
        loose = ("girder", "x", "true", "false", "true", "true", "true", "1", "0.0000", "0.0000")
        if shaft.sample(host, 0, 0)[2:] != encased:
            raise RuntimeError("Host could not power the wet girder by inserting one shaft.")
        host.command("/tp @s 11.500 101 -8.500")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hc-girder-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, GUEST, render=True, scenario="multiplayer-girder-shaft", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/item replace entity {GUEST} hotbar.0 with {shaft.WRENCH} 1",
            ))
            multiplayer.until("the guest to receive the wrench", lambda: (
                guest.call("inventory")["counts"].get(shaft.WRENCH) == 1
            ))

            def teleport(feet):
                coordinates = " ".join(f"{value:.3f}" for value in feet)
                host.command(f"/tp {GUEST} {coordinates}")
                multiplayer.until("guest arrival at the girder", lambda: (
                    guest.call("state")["player"]["position"] == list(feet)
                ))

            for inserting, want, held in ((False, loose, 1), (True, encased, 0)):
                shaft.interact(guest, 0, inserting, teleport=teleport)
                host.step_to(host.clock() + 1)
                got = shaft.sample(host, 0, 0)[2:]
                if got != want:
                    raise RuntimeError(f"Guest interaction expected {want}, got {got}")
                state = host.call("block", *shaft.BASE)["state"]
                multiplayer.until("guest state and shaft inventory to match", lambda: (
                    guest.call("block", *shaft.BASE)["state"] == state
                    and guest.call("inventory")["counts"].get(shaft.SHAFT, 0) == held
                ))
    print("The host powered a wet girder. The guest took and reinserted the shaft, preserving water and switching output 32→0→32 RPM.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
