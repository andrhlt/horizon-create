#!/usr/bin/env python3
"""Exercise Copper Valve angle selection and short activation from a LAN guest."""
import argparse
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

spec = spec_from_file_location("multiplayer_fixture", ROOT / "tools/test-multiplayer.py")
multiplayer = module_from_spec(spec)
spec.loader.exec_module(multiplayer)
spec = spec_from_file_location("valve_fixture", ROOT / "tools/test-copper-valve-handle.py")
valve = module_from_spec(spec)
spec.loader.exec_module(valve)
GUEST = "ValveGuest"


def replay(args, scratch):
    with fixture_world(args, "CopperValveLAN", render=True, pack=args.pack) as host:
        valve.setup(host)
        host.step_to(host.clock() + 1)
        host.command("/tp @s 12.50 101.0 -7.50")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(
            args, scratch, address, GUEST, render=True, scenario="valve-lan", pack=args.pack,
        ) as guest:
            multiplayer.until("the valve guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/tp {GUEST} 11.500 101.000 -9.500",
            ))
            multiplayer.until("the valve guest to reach the handle", lambda: (
                guest.call("state")["player"]["position"] == [11.5, 101.0, -9.5]
                and guest.call("block", *valve.HANDLE)["state"].startswith("create:copper_valve_handle[facing=east")
            ))
            valve.configure(guest, 0, 137)
            multiplayer.until("the host to receive the signed setting", lambda: valve.sample(host)[0] == -137)
            if valve.sample(host)[1] != 0:
                raise RuntimeError("Setting a valve angle activated the rotation generator.")

            valve.activate(guest, check_press=host)
            multiplayer.until("the host to receive the short tap", lambda: valve.sample(host)[1] == 17)
            start = host.clock()
            speed = []
            for tick in range(1, 18):
                host.step_to(start + tick)
                speed.append(valve.sample(host)[-1])
            if speed != [-32.0] * 16 + [0.0]:
                raise RuntimeError(f"The guest's signed valve pulse failed to match Java: {speed}.")
            if (remaining := valve.sample(host)[5]) != 3:
                raise RuntimeError(f"The guest's valve cooldown should start at 3, got {remaining}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    with TemporaryDirectory(prefix="hc-vl-") as scratch:
        replay(parser.parse_args(), Path(scratch))
    print("A survival LAN guest configured −137° and produced the original signed shaft pulse from a short tap.")


if __name__ == "__main__":
    main()
