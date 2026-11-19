#!/usr/bin/env python3
"""Verify different cased cog variants in a live host and guest world."""
import argparse
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

GUEST = "EncasedGearGuest"


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gears = load(ROOT / "tools/test-encased-cogwheel-family.py")
multiplayer = load(ROOT / "tools/test-multiplayer.py")


def verify(args):
    with fixture_world(args, "EncasedCogwheelFamilyLAN", render=True, pack=args.pack) as host:
        gears.setup(host)
        host.step_to(host.clock() + 1)
        gears.interact(host, 3, 0)
        host.step_to(host.clock() + 1)
        if gears.sample(host, 0, 0)[2:] != ("encased", "x", "true", "true", "2", "24.0000", "24.0000", "-24.0000"):
            raise RuntimeError("Host Andesite Small Cog lost its inventory or gear ratio.")
        host.command("/tp @s 11.500 101 -8.500")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hc-encased-cog-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, GUEST, render=True, scenario="multiplayer-encased-family", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            casing = gears.VARIANTS[2][1]
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/item replace entity {GUEST} hotbar.0 with {casing} 2",
                f"/item replace entity {GUEST} hotbar.1 with {gears.WRENCH} 1",
            ))
            multiplayer.until("the guest to receive two casings and a wrench", lambda: (
                guest.call("inventory")["counts"].get(casing) == 2
                and guest.call("inventory")["counts"].get(gears.WRENCH) == 1
            ))

            def teleport(feet):
                coordinates = " ".join(f"{value:.3f}" for value in feet)
                host.command(f"/tp {GUEST} {coordinates}")
                multiplayer.until("guest arrival at the cog", lambda: guest.call("state")["player"]["position"] == list(feet))

            for tick, want in (
                (3, ("encased", "x", "true", "true", "2", "24.0000", "24.0000", "-48.0000")),
                (6, ("encased", "x", "false", "true", "2", "24.0000", "0.0000", "-48.0000")),
                (10, ("bare", "x", "false", "false", "2", "24.0000", "24.0000", "-48.0000")),
            ):
                gears.interact(guest, tick, 2, teleport=teleport)
                host.step_to(host.clock() + 1)
                got = gears.sample(host, tick, 2)[2:]
                if got != want:
                    raise RuntimeError(f"Guest interaction {tick} expected {want}, got {got}")
                target = gears.positions(2)[0]
                final = host.call("block", *target)["state"]
                multiplayer.until("the guest to see authoritative state and inventory", lambda:
                                  guest.call("block", *target)["state"] == final
                                  and guest.call("inventory")["counts"].get(casing) == 2)
    print("Host Andesite small and guest Brass large encasing preserved gear mesh at -24 and -48 RPM. Guest toggling only changed the axial output.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
