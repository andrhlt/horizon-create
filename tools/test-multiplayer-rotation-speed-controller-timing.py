#!/usr/bin/env python3
"""Check controller speed changes are published during the settings action."""

import argparse
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


controller = load("test-rotation-speed-controller")
multiplayer = load("test-multiplayer")
GUEST = "SpeedGuest"


def output(host):
    value = host.command(f"/data get block {controller.coords(controller.SHAFT_OUTPUT)}")
    return controller.tag(value, "Speed", float)


def assert_speed(host, label, expected):
    actual = output(host)
    if actual != expected:
        raise RuntimeError(f"{label}: expected {expected:g} RPM before stepping, got {actual:g}.")


def verify(args, scratch):
    # The controller board is a client screen; keep this interaction test
    # offscreen-rendered so the real settings-release packet is generated.
    with fixture_world(args, "SpeedControllerLANSettingTiming", render=True, pack=args.pack) as host:
        controller.setup(host)
        host.step_to(host.clock() + 1)
        network = host.call("lan", "open", "0", "commands", "force")
        controller.configure(host, controller.ABOVE, 1, 64)
        assert_speed(host, "Host setting acceptance", 64.0)
        host.command("/tp @s 10.5 101 -7.5")
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(
            args, scratch, address, GUEST, render=True,
            scenario="multiplayer-speed-controller-timing", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.command(f"/gamemode survival {GUEST}")
            host.command(f"/tp {GUEST} 4.0 101 -9.5")
            multiplayer.until("the guest to reach the controller", lambda: (
                guest.call("state")["player"]["position"] == [4.0, 101.0, -9.5]
            ))
            host.step_to(host.clock() + 1)
            multiplayer.until("the guest to see the controller", lambda: (
                guest.call("block", *controller.ABOVE)["state"].startswith("create:rotation_speed_controller")
            ))

            host.command("/tp @s 10.5 101 -7.5")
            guest.call("wait", 3)
            controller.choose_setting(guest, controller.ABOVE, 0, 32)
            assert_speed(host, "Guest setting acceptance", -32.0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-sct-") as scratch:
        verify(args, Path(scratch))
    print("Host +64 and guest −32 RPM outputs updated at setting acceptance.")


if __name__ == "__main__":
    main()
