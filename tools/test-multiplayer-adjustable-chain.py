#!/usr/bin/env python3
"""Verify an independent LAN guest can adjust the chain gearshift's output."""

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


chain = load("test-adjustable-chain-gearshift")
multiplayer = load("test-multiplayer")
GUEST = "ChainGuest"


def verify(args, scratch):
    with fixture_world(args, "AdjustableChainLAN", render=True, pack=args.pack) as host:
        chain.setup(host)
        host.command("/tp @s 9.5 101 -8.5")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(
            args, scratch, address, GUEST, render=True, scenario="multiplayer-adjustable-chain",
            pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.command(f"/gamemode survival {GUEST}")
            host.command(f"/tp {GUEST} 5.5 101 -8.5")
            multiplayer.until("the guest to reach the lever", lambda: (
                guest.call("state")["player"]["position"] == [5.5, 101.0, -8.5]
            ))
            lever = chain.LEVERS[0]
            multiplayer.until("the guest to see the lever", lambda: (
                guest.call("block", *lever)["state"].startswith("create:analog_lever")
            ))

            host.step_to(host.clock() + 1)
            guest.call("interact", *lever)
            multiplayer.until("the server to receive the lever click", lambda: (
                chain.value(chain.block_data(host, lever), "State", int) == 1
            ))
            start = host.clock()
            for tick in range(1, 17):
                host.step_to(start + tick)
            multiplayer.until("the guest to see the powered gearshift", lambda: (
                "powered=true" in guest.call("block", *chain.FORWARD)["state"]
            ))
            rpm = chain.value(chain.block_data(host, chain.FORWARD_OUTPUT), "Speed", float)
            if rpm != 27.0:
                raise RuntimeError(f"Expected guest input to raise the output to 27 RPM, got {rpm}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-chain-lan-") as scratch:
        verify(args, Path(scratch))
    print("A survival guest powered the gearshift and raised the server output to 27 RPM.")


if __name__ == "__main__":
    main()
