#!/usr/bin/env python3
"""Verify a live LAN guest observes host gauge load changes."""

import argparse
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

import importlib.util


def load_multiplayer():
    path = Path(__file__).with_name("test-multiplayer.py")
    spec = importlib.util.spec_from_file_location("multiplayer_gauges_harness", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


multiplayer = load_multiplayer()
GUEST = "GaugeGuest"
GAUGE = (6, 102, -10)


def advance(host, ticks):
    for _ in range(ticks):
        host.command("/tick step 1")


def trace_lines(log):
    return [line for line in log.read_text(encoding="utf-8").splitlines()
            if line.startswith("CREATE_GOGGLES ")]


def latest_readout(log):
    lines = trace_lines(log)
    if not lines:
        raise RuntimeError("Guest produced no CREATE_GOGGLES readout")
    return lines[-1]


def verify(args, scratch):
    guest_log = scratch / GUEST / "ctl.log"
    with fixture_world(args, "GaugeLAN", render=True, pack=args.pack) as host:
        host.commands((
            "/forceload add 0 -10",
            "/fill 9 100 -12 12 100 -8 minecraft:smooth_stone",
            "/fill 7 99 -13 7 99 -8 minecraft:smooth_stone",
            "/fill 6 100 -13 6 100 -8 minecraft:smooth_stone",
            "/fill 8 100 -13 8 100 -8 minecraft:smooth_stone",
            "/setblock 7 100 -13 minecraft:smooth_stone",
            "/setblock 7 100 -8 minecraft:smooth_stone",
            "/setblock 6 100 -10 create:water_wheel[facing=up]",
            "/setblock 6 101 -10 create:cogwheel[axis=y]",
            "/setblock 6 102 -10 create:stressometer[facing=east,axis_along_first=true]",
            "/setblock 6 103 -10 create:speedometer[facing=east,axis_along_first=true]",
            "/setblock 7 100 -9 minecraft:water",
            "/fill 6 101 -9 6 101 -6 create:millstone",
        ))
        advance(host, 70)
        if host.clock() != 76:
            raise RuntimeError(f"Host did not reach the loaded warmup tick: {host.clock()}")
        initial = host.call("command", f"/data get block {GAUGE[0]} {GAUGE[1]} {GAUGE[2]}")["chat"][-1]
        if not re.search(r"Stress:\s*128\.0f", initial):
            raise RuntimeError(f"Host did not reach the loaded 4-mill state: {initial}")
        host.command(f"/tp @s 10.5 101 -10.5")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(
            args, scratch, address, GUEST, render=True, scenario="multiplayer-gauges",
            pack=args.pack, env={"CREATE_GOGGLES_TRACE": "1"},
        ) as guest:
            multiplayer.until("guest join", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.call("command", f"/gamemode creative {GUEST}")
            host.call("command", f"/tp {GUEST} 10.5 101 -10.5")
            host.call("command", f"/item replace entity {GUEST} armor.head with create:goggles")
            guest.call("look-at", 6.5, 102.4, -9.5)
            guest.call("wait", 3)
            loaded_readout = latest_readout(guest_log)
            if "Network Stress" not in loaded_readout or "Stress" not in loaded_readout:
                raise RuntimeError(f"Guest loaded readout did not contain stress output: {loaded_readout}")

            host.command("/fill 6 101 -9 6 101 -7 minecraft:air")
            advance(host, 3)
            guest.call("wait", 3)
            recovered_readout = latest_readout(guest_log)
            if recovered_readout == loaded_readout:
                raise RuntimeError("Guest readout did not change after host removed three millstones")
            if "Network Stress" not in recovered_readout:
                raise RuntimeError(f"Guest recovery readout lost stress output: {recovered_readout}")

    print("Live LAN guest observed loaded and reduced stressometer readouts after host mill removal.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-multiplayer-gauges-") as scratch:
        verify(args, Path(scratch))


if __name__ == "__main__":
    main()
