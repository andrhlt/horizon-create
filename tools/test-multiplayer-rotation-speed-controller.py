#!/usr/bin/env python3
"""Check that the host and LAN guest share the controller's signed setting."""

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


def verify(args, scratch):
    with fixture_world(args, "SpeedControllerLAN", render=True, pack=args.pack) as host:
        controller.setup(host)
        host.step_to(host.clock() + 1)
        controller.configure(host, controller.ABOVE, 1, 64)
        host.step_to(host.clock() + 1)
        previous = output(host)
        if previous != 64.0:
            raise RuntimeError(f"The host's setting should drive the shaft at 64 RPM, got {previous}.")
        host.command("/tp @s 10.5 101 -7.5")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(
            args, scratch, address, GUEST, render=True, scenario="multiplayer-speed-controller",
            pack=args.pack,
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
            multiplayer.until("the guest to see the speed controller", lambda: (
                guest.call("block", *controller.ABOVE)["state"].startswith("create:rotation_speed_controller")
            ))

            controller.choose_setting(guest, controller.ABOVE, 0, 32)
            host.step_to(host.clock() + 1)
            speed = output(host)
            if speed != -32.0:
                raise RuntimeError(f"The guest's setting should reverse the shaft to −32 RPM, got {speed}.")

            p = (6, 101, -7)
            top = (6, 102, -7)
            host.commands((
                f"/setblock {controller.coords(p)} create:rotation_speed_controller[axis=x]",
                f"/setblock {controller.coords(top)} minecraft:air",
                f"/tp {GUEST} 4.0 101 -6.5",
                f"/item replace entity {GUEST} hotbar.0 with create:large_cogwheel 2",
            ))
            multiplayer.until("the guest to reach the second controller", lambda: (
                guest.call("state")["player"]["position"] == [4.0, 101.0, -6.5]
            ))
            multiplayer.until("the guest to see the large cog stack", lambda: (
                guest.call("inventory")["counts"].get("create:large_cogwheel") == 2
            ))
            guest.call("select", "create:large_cogwheel")
            guest.call("look-at", 6.01, 101.2, -6.5)
            guest.call("mouse", "right", "down")
            guest.call("wait", 1)
            guest.call("mouse", "right", "up")
            multiplayer.until("the guest to place the cog on the server", lambda: (
                host.call("block", *top)["state"].startswith("create:large_cogwheel[axis=z")
            ))
            multiplayer.until("the guest's stack to decrement once", lambda: (
                guest.call("inventory")["counts"].get("create:large_cogwheel") == 1
            ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-speed-controller-lan-") as scratch:
        verify(args, Path(scratch))
    print("The host set 64 RPM, and the guest set −32 RPM and attached a large cog to a second controller.")


if __name__ == "__main__":
    main()
