#!/usr/bin/env python3
"""Start a Windmill Bearing and reverse its loaded shaft from another Horizon client."""

import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

multiplayer = import_module("test-multiplayer")
windmill = import_module("test-windmill")
GUEST = "WindmillGuest"


def run(args, scratch):
    with fixture_world(args, "Windmill-LAN", render=True, pack=args.pack) as host:
        windmill.setup(host)
        windmill.operate(host)
        host.step_to(host.clock() + 1)
        pos = windmill.WINDMILLS[1]
        x, y, z = pos
        windmill.configure(host, pos, True)
        if windmill.observe(host, pos, 8, 0, 1)["shaft_rpm"] != -1:
            raise RuntimeError("The host did not reverse the loaded Windmill")
        host.command("/tp @s 5.5 181.0 24.5")
        session = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{session['port']}"
        with multiplayer.joined_client(
            args, scratch, address, GUEST, render=True, scenario="windmill-lan", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to finish joining", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((f"/gamemode survival {GUEST}", f"/tp {GUEST} {x + 0.5} {float(y)} {z - 2.5}"))
            multiplayer.until("the guest to reach the bearing", lambda: (
                guest.call("state")["player"]["position"] == [x + 0.5, float(y), z - 2.5]
            ))
            host.step_to(host.clock() + 1)
            windmill.configure(guest, pos, False, teleport=False)
            multiplayer.until("the guest to reverse the loaded windmill",
                lambda: windmill.observe(host, pos, 8, 0, 1)["shaft_rpm"] == 1)
            actual = windmill.observe(host, pos, 8, 0, 1)
            if (actual["captured"], actual["stress"], actual["capacity"]) != (8, 2, 512):
                raise RuntimeError(f"Windmill load after guest reversal differed: {actual}")
    print("The host and guest each reversed the same loaded Windmill through the original direction board.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    with TemporaryDirectory(prefix="hc-windmill-lan-") as scratch:
        run(parser.parse_args(), Path(scratch))
