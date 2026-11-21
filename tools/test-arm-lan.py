#!/usr/bin/env python3
"""Configure and operate a Mechanical Arm as a LAN guest."""

import argparse
import importlib
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

mp = importlib.import_module("test-multiplayer")
INPUT = (6, 97, -11)
OUTPUT = (8, 97, -9)
ARM = (6, 98, -9)
PLAYER = "ArmGuest"


def data(control, pos, key=None):
    command = f"/data get block {' '.join(map(str, pos))}"
    if key:
        command += f" {key}"
    return control.command(command)


def configured_points(host):
    current = data(host, ARM, "InteractionPoints")
    if ('Type: "create:depot"' in current
            and current.count('Mode: "TAKE"') == 1
            and current.count('Mode: "DEPOSIT"') == 1):
        return current
    return False


def run(args):
    with TemporaryDirectory(prefix="hc-arm-lan-") as directory:
        with fixture_world(args, "ArmConfigurationLAN", render=True, pack=args.pack) as host:
            host.commands((
                "/fill 2 96 -13 10 96 -5 minecraft:smooth_stone",
                "/fill 2 97 -13 10 102 -5 minecraft:air",
                f"/setblock {' '.join(map(str, INPUT))} create:depot",
                f"/setblock {' '.join(map(str, OUTPUT))} create:depot",
                "/setblock 6 97 -9 create:creative_motor[facing=up]",
                "/data merge block 6 97 -9 {ScrollValue:64}",
                f"/item replace block {' '.join(map(str, INPUT))} container.0 with minecraft:iron_ingot 1",
                "/setworldspawn 1000 100 1000",
                "/gamemode survival",
            ))
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            with mp.joined_client(
                args, Path(directory), f"127.0.0.1:{port}", PLAYER,
                render=True, scenario="arm-configuration", pack=args.pack,
            ) as guest:
                mp.until("the arm guest to join", lambda: any(
                    player["name"] == PLAYER and player["placed"]
                    for player in host.call("lan", "status")["guests"]
                ))
                host.commands((
                    f"/gamemode survival {PLAYER}",
                    f"/tp {PLAYER} 5.1 97 -8.0 180 20",
                    f"/item replace entity {PLAYER} hotbar.0 with create:mechanical_arm",
                ))
                mp.until("the guest to receive the arm", lambda:
                    guest.call("inventory")["counts"].get("create:mechanical_arm", 0) == 1)
                guest.call("select", "create:mechanical_arm")
                guest.call("interact", *INPUT, "up")
                guest.call("interact", *OUTPUT, "up")
                guest.call("interact", *OUTPUT, "up")
                guest.call("place", *ARM, "create:mechanical_arm")

                configured = mp.until(
                    "the host to observe both guest-configured arm points",
                    lambda: configured_points(host),
                )
                if configured.count("Type: \"create:depot\"") != 2:
                    raise RuntimeError(f"Host did not receive both guest-configured endpoints: {configured}")

                for tick in range(1, 97):
                    host.step_to(host.clock() + 1)
                    if "minecraft:iron_ingot" in data(host, OUTPUT, "Items"):
                        break
                else:
                    raise RuntimeError(
                        "The configured arm did not transfer the ingot in 96 ticks: "
                        f"arm={data(host, ARM)}, held={data(host, ARM, 'HeldItem')}, "
                        f"source={data(host, INPUT, 'Items')}, destination={data(host, OUTPUT, 'Items')}"
                    )
                source = data(host, INPUT, "Items")
                destination = data(host, OUTPUT, "Items")
                if "minecraft:iron_ingot" in source or "minecraft:iron_ingot" not in destination:
                    raise RuntimeError(f"Host saw an inconsistent transfer: {source} / {destination}")
                # Approach the Depot from the east, away from the arm's base
                # and elbow, so the arm does not block the guest's click ray.
                host.command(f"/tp {PLAYER} 10.2 97 -9.5")
                mp.until("the guest to reach the Depot's clear side", lambda:
                    guest.call("state")["player"]["position"] == [10.2, 97.0, -9.5])
                guest.call("look-at", OUTPUT[0] + 0.5, OUTPUT[1] + 0.5, OUTPUT[2] + 0.5)
                guest.call("interact", *OUTPUT, "up")
                mp.until("the guest to collect the transferred ingot", lambda:
                    guest.call("inventory")["counts"].get("minecraft:iron_ingot", 0) == 1)
                if "minecraft:iron_ingot" in data(host, OUTPUT, "Items"):
                    raise RuntimeError("Guest collected the item but the host still sees it in the Depot")
    print("LAN guest programmed both arm endpoints; host and guest observed the completed Depot transfer.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
