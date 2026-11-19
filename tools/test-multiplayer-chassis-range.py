#!/usr/bin/env python3
"""Verify a survival LAN guest can configure a matching Chassis group."""

import argparse
from pathlib import Path
from runpy import run_path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

range_fixture = run_path(str(ROOT / "tools/test-chassis-range.py"))
multiplayer = run_path(str(ROOT / "tools/test-multiplayer.py"))
CHASSIS = ((8, 201, 42), (8, 201, 43), (8, 201, 44))
BOARD = {"row": "Distance", "last_column": "15"}
GUEST = "RangeGuest"


def run(args):
    configure = range_fixture["settings"]
    ranges = range_fixture["values"]
    until = multiplayer["until"]
    with fixture_world(args, "Chassis-Range-LAN", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 4 200 40 7 200 45 minecraft:smooth_stone",
            "/tp @s 5.5 201 42.5 -90 24",
            "/setblock 8 201 42 create:linear_chassis[axis=x]",
            "/setblock 8 201 43 create:linear_chassis[axis=x]",
            "/setblock 8 201 44 create:secondary_linear_chassis[axis=x]",
            "/item replace entity @s hotbar.0 with create:wrench",
        ))
        host.call("select", "create:wrench")
        configure(host, BOARD, 1)
        observed = ranges(host, *CHASSIS)
        if observed != ["2", "8", "8"]:
            raise RuntimeError(f"Host's individual range selection produced {observed}.")
        host.command("/tp @s 5.5 201 44.5 -90 24")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hcr-") as scratch, multiplayer["joined_client"](
            args, Path(scratch), address, GUEST, render=True, scenario="chassis-range-lan", pack=args.pack,
        ) as guest:
            until("the guest to enter", lambda: any(
                player["name"] == GUEST and player["placed"] for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/tp {GUEST} 5.5 201 42.5 -90 24",
                f"/item replace entity {GUEST} hotbar.0 with create:wrench",
            ))
            until("the guest to receive the wrench", lambda: guest.call("inventory")["counts"].get("create:wrench") == 1)
            guest.call("select", "create:wrench")
            host.step_to(host.clock() + 1)
            until("the guest to see the chassis", lambda: guest.call("block", *CHASSIS[0])["block"] == "create:linear_chassis")
            configure(guest, BOARD, 15, bulk=True)
            until("both matching chassis to update from the guest", lambda: ranges(host, *CHASSIS) == ["16", "16", "8"])
    print("A host set one chassis to 2. A survival LAN guest set both matching chassis to 16 and left the neighboring variant at 8.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
