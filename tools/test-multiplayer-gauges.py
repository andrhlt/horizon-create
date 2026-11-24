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


def trace_readouts(log):
    result = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.startswith("CREATE_GOGGLES "):
            continue
        _prefix, payload = line.removeprefix("CREATE_GOGGLES ").split(" ", 1)
        try:
            rows = json.loads(payload)
        except json.JSONDecodeError:
            # The client may still be appending its current trace line.
            continue
        result.append((line, "".join(text for row in rows for text, _color, _strike in row)))
    return result


def observe(guest, log, target, marker):
    guest.call("look-at", target[0] + 0.5, target[1] + 0.4, target[2] + 0.5)
    guest.call("wait", 8)
    for raw, text in reversed(trace_readouts(log)):
        if marker in text:
            return raw, text
    raise RuntimeError(f"Guest produced no Goggles readout containing {marker!r}")


def host_data(host, pos):
    return host.call("command", f"/data get block {pos[0]} {pos[1]} {pos[2]}")["chat"][-1]


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
            "/setblock 12 102 -10 create:stressometer[facing=east,axis_along_first=true]",
            "/setblock 12 103 -10 create:speedometer[facing=east,axis_along_first=true]",
            "/setblock 7 100 -9 minecraft:water",
            "/fill 6 101 -9 6 101 -6 create:millstone",
        ))
        advance(host, 70)
        if host.clock() != 76:
            raise RuntimeError(f"Host did not reach the loaded warmup tick: {host.clock()}")
        loaded_stress = host_data(host, (6, 102, -10))
        loaded_speed = host_data(host, (6, 103, -10))
        idle_stress = host_data(host, (12, 102, -10))
        idle_speed = host_data(host, (12, 103, -10))
        if not re.search(r"Stress:\s*128\.0f", loaded_stress) or "Value: 0.5f" not in loaded_stress:
            raise RuntimeError(f"Host loaded stressometer state was unexpected: {loaded_stress}")
        if "Speed: 8.0f" not in loaded_speed or "Value: 0.12" not in loaded_speed:
            raise RuntimeError(f"Host loaded speedometer state was unexpected: {loaded_speed}")
        if "Speed: 0.0f" not in idle_stress or "Value: 0.0f" not in idle_stress:
            raise RuntimeError(f"Host idle stressometer state was unexpected: {idle_stress}")
        if "Speed: 0.0f" not in idle_speed or "Value: 0.0f" not in idle_speed:
            raise RuntimeError(f"Host idle speedometer state was unexpected: {idle_speed}")
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
            host.call("command", f"/tp {GUEST} 8.5 101 -10.5")
            host.call("command", f"/item replace entity {GUEST} armor.head with create:goggles")
            advance(host, 1)
            multiplayer.until("guest to receive the stressometer", lambda: (
                guest.call("block", *GAUGE)["state"].startswith("create:stressometer")
            ))
            for pos in ((6, 102, -10), (6, 103, -10), (12, 102, -10), (12, 103, -10)):
                if guest.call("block", *pos)["state"] != host.call("block", *pos)["state"]:
                    raise RuntimeError(f"Guest block state disagreed with host at {pos}")
            guest.call("look-at", 6.5, 102.4, -9.5)
            multiplayer.until("guest to target the gauge block", lambda: (
                guest.call("state")["looking_at"]["kind"] == "block"
            ))
            host.call("command", f"/tp {GUEST} 11.5 101 -10.5")
            idle_stress_readout = observe(guest, guest_log, (12, 102, -10), "Network Stress")
            idle_speed_readout = observe(guest, guest_log, (12, 103, -10), "Rotation Speed")
            host.call("command", f"/tp {GUEST} 8.5 101 -10.5")
            loaded_stress_readout = observe(guest, guest_log, (6, 102, -10), "Network Stress")
            loaded_speed_readout = observe(guest, guest_log, (6, 103, -10), "Rotation Speed")
            if "No Rotation" not in idle_stress_readout[1] or "None (0 RPM)" not in idle_speed_readout[1]:
                raise RuntimeError("Guest idle readouts did not show no rotation")
            if "Slow (8 RPM)" not in loaded_speed_readout[1] or "50%" not in loaded_stress_readout[1]:
                raise RuntimeError("Guest loaded readouts did not show 8 RPM and 50% stress")

            host.command("/fill 6 101 -9 6 101 -1 create:millstone")
            advance(host, 3)
            overloaded_stress = host_data(host, (6, 102, -10))
            overloaded_speed = host_data(host, (6, 103, -10))
            if "Stress: 288.0f" not in overloaded_stress or "Value: 0.0f" not in overloaded_speed:
                raise RuntimeError("Host did not reach the nine-mill overload state")
            overloaded_stress_readout = observe(guest, guest_log, (6, 102, -10), "Network Stress")
            overloaded_speed_readout = observe(guest, guest_log, (6, 103, -10), "Rotation Speed")

            host.command("/fill 6 101 -8 6 101 -1 minecraft:air")
            advance(host, 3)
            recovered_stress = host_data(host, (6, 102, -10))
            recovered_speed = host_data(host, (6, 103, -10))
            if "Stress: 32.0f" not in recovered_stress or "Value: 0.12" not in recovered_speed:
                raise RuntimeError("Host did not recover to the one-mill state")
            recovered_stress_readout = observe(guest, guest_log, (6, 102, -10), "Network Stress")
            recovered_speed_readout = observe(guest, guest_log, (6, 103, -10), "Rotation Speed")
            if overloaded_speed_readout[0] == recovered_speed_readout[0] or overloaded_stress_readout[0] == recovered_stress_readout[0]:
                raise RuntimeError("Guest readouts did not change across overload recovery")

    print("Live LAN guest observed idle and loaded Speedometer/Stressometer readouts and both changed across host overload/recovery.")


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
