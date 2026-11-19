#!/usr/bin/env python3
"""Check that a Horizon LAN guest can lower a lever raised by the host."""

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
lever = load("test-analog-lever")
GUEST = "AnalogGuest"
SCENARIO = "analog-lever-lan"
ITEM = "minecraft:stone"


def check_level(host, level):
    return lever.read_int(
        host.command(f"/data get block {lever.coords(lever.LEVER)} State"), r"(\d+)$", "State",
    ) == level


def wait_for_wires(host, guest, power):
    tick = host.clock()
    for offset in range(1, 16):
        host.step_to(tick + offset)
    for client in (host, guest):
        multiplayer.until(f"both circuits to show {power} power", lambda: (
            lever.wire_powers(client) == (power, power)
        ))


def run(args, scratch):
    with fixture_world(args, SCENARIO, render=True) as host:
        lever.setup(host)
        host.commands((
            "/setblock 7 179 10 minecraft:smooth_stone",
            f"/item replace entity @s hotbar.0 with {ITEM} 3",
        ))
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(args, scratch, address, GUEST, render=True, scenario=SCENARIO) as guest:
            multiplayer.until("the LAN guest to spawn", lambda: (
                any(player["name"] == GUEST and player["placed"]
                    for player in host.call("lan", "status")["guests"])
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/tp {GUEST} 7.5 180 10.5",
                f"/item replace entity {GUEST} hotbar.0 with {ITEM} 3",
            ))
            multiplayer.until("the guest's setup position and held item", lambda: (
                guest.call("state")["player"]["position"] == [7.5, 180.0, 10.5]
                and multiplayer.count(guest, ITEM) == 3
            ))
            host.call("select", ITEM)
            guest.call("select", ITEM)
            host.call("interact", *lever.LEVER)
            multiplayer.until("the host click to raise the lever", lambda: check_level(host, 1))
            wait_for_wires(host, guest, 1)

            guest.call("key", "shift", "down")
            guest.call("wait", 4)
            try:
                guest.call("look-at", "8.5", "180.17", "8.5")
                guest.call("mouse", "right", "click")
                multiplayer.until("the guest click to lower the lever", lambda: check_level(host, 0))
            finally:
                guest.call("key", "shift", "up")
            wait_for_wires(host, guest, 0)
            for player in (host, guest):
                if multiplayer.count(player, ITEM) != 3:
                    raise RuntimeError("An Analog Lever interaction consumed the held block.")
    print("Host and LAN guest raised and lowered the Analog Lever with a held block and saw both wire updates.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    with TemporaryDirectory(prefix="hc-analog-lan-") as scratch:
        run(parser.parse_args(), Path(scratch))
