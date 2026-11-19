#!/usr/bin/env python3
"""Verify a LAN guest can reverse the host's hand crank in survival."""

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


multiplayer = load("test-multiplayer")
crank = load("test-hand-crank")
GUEST = "CrankGuest"


def verify(args, scratch):
    with fixture_world(args, "HandCrankLAN", render=True) as host:
        crank.setup(host)
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(
            args, scratch, address, GUEST, render=True, scenario="multiplayer-hand-crank",
        ) as guest:
            multiplayer.until(
                "the independent guest to be placed",
                lambda: any(p["name"] == GUEST and p["placed"]
                            for p in host.call("lan", "status")["guests"]),
            )
            host.command(f"/gamemode survival {GUEST}")
            host.command(f"/tp {GUEST} 5.5 101 -8.5")
            multiplayer.until("the guest to teleport", lambda: (
                guest.call("state")["player"]["position"] == [5.5, 101.0, -8.5]
            ))
            multiplayer.until("the guest to see the crank", lambda: (
                guest.call("block", *crank.CRANK)["state"].startswith("create:hand_crank")
            ))

            host.call("interact", *crank.CRANK)
            host.step_to(host.clock() + 1)
            speed = crank.tag_value(host.command(f"/data get block {crank.REAR}"), "Speed")
            if speed != 32.0:
                raise RuntimeError(f"The host should drive the shaft at +32 RPM, got {speed}.")

            guest.call("key", "shift", "down")
            guest.call("wait", 4)
            try:
                guest.call("interact", *crank.CRANK)
                coords = " ".join(map(str, crank.CRANK))
                multiplayer.until("the server to receive the reverse click", lambda: (
                    "Backwards: 1b" in host.command(f"/data get block {coords}")
                ))
            finally:
                guest.call("key", "shift", "up")
            host.step_to(host.clock() + 1)
            speed = crank.tag_value(host.command(f"/data get block {crank.REAR}"), "Speed")
            if speed != -32.0:
                raise RuntimeError(f"The guest should reverse the shaft to −32 RPM, got {speed}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-crank-lan-") as scratch:
        verify(args, Path(scratch))
    print("The LAN host drove the shaft at +32 RPM and the guest reversed it to −32 RPM.")


if __name__ == "__main__":
    main()
