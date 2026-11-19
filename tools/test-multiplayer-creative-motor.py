#!/usr/bin/env python3
"""Check live host and guest signed motor settings and server shaft output."""

import argparse
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    multiplayer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(multiplayer)
    return multiplayer


GUEST = "MotorGuest"
multiplayer = load("test-multiplayer")
motor = load("test-creative-motor")


def output(host):
    nbt = host.command(f"/data get block {motor.controller.coords(motor.POSITIONS[1])}")
    return motor.controller.tag(nbt, "Speed", float)


def verify(args):
    with fixture_world(args, "CreativeMotorLAN", render=True, pack=args.pack) as host:
        motor.setup(host)
        host.step_to(host.clock() + 1)
        motor.configure(host, motor.HORIZONTAL, 1, 64)
        host.step_to(host.clock() + 1)
        if output(host) != 64:
            raise RuntimeError("The host’s 64 RPM configuration did not reach the shaft.")
        host.command("/tp @s 9.5 101 -7.5")
        session = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{session['port']}"
        with TemporaryDirectory(prefix="hc-motor-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, GUEST, render=True,
            scenario="multiplayer-creative-motor", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.command(f"/gamemode survival {GUEST}")
            x, y, z = motor.HORIZONTAL
            host.command(f"/tp {GUEST} {x - 2:.1f} {y} {z + 0.5}")
            multiplayer.until("the guest to reach the motor", lambda: (
                guest.call("state")["player"]["position"] == [x - 2, y, z + 0.5]
            ))
            host.step_to(host.clock() + 1)
            multiplayer.until("the guest to see the motor", lambda: (
                guest.call("block", *motor.HORIZONTAL)["state"].startswith("create:creative_motor[")
            ))
            motor.configure(guest, motor.HORIZONTAL, 0, 24, teleport=False)
            host.step_to(host.clock() + 1)
            if output(host) != -24:
                raise RuntimeError("The guest’s −24 RPM configuration did not reach the server shaft.")
    print("The host set the motor to 64 RPM and the guest reversed the server shaft to −24 RPM.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
