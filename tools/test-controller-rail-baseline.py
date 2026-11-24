#!/usr/bin/env python3
"""Check Controller Rail idle/active save reopen and LAN guest observation."""

import argparse
import importlib
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

multiplayer = importlib.import_module("test-multiplayer")
NUMBER = re.compile(r"([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)d\b")


def persistence(args):
    with fixture_world(args, "ControllerRailReopen", pack=args.pack) as control:
        control.commands((
            "/fill 8 169 20 26 169 28 minecraft:stone",
            "/setblock 10 170 22 create:controller_rail[shape=east_west,backwards=false]",
            "/fill 10 170 26 26 170 26 create:controller_rail[shape=east_west,backwards=true]",
            "/setblock 20 169 26 minecraft:redstone_block",
        ))
        control.call("wait", 4)
        tag = "ControllerRailSavedCart"
        selector = f"@e[type=minecraft:minecart,tag={tag},limit=1]"
        control.command(
            f'/summon minecraft:minecart 15.5 171.0625 26.5 '
            f'{{Motion:[0.0d,0.0d,0.0d],Tags:["{tag}"]}}'
        )
        baseline = control.clock()
        control.step_to(baseline + 1)
        control.step_to(baseline + 2)

        def moving_cart():
            pos, motion = control.commands((
                f"/data get entity {selector} Pos",
                f"/data get entity {selector} Motion",
            ))
            position = NUMBER.findall(pos)
            velocity = NUMBER.findall(motion)
            if len(position) != 3 or len(velocity) != 3:
                raise RuntimeError(f"Saved rail cart is missing: Pos={pos!r}, Motion={motion!r}")
            if float(position[0]) <= 15.5 or float(velocity[0]) <= 0:
                raise RuntimeError(f"Powered rail did not move the saved cart east: Pos={pos!r}, Motion={motion!r}")
            return tuple(map(float, position)), tuple(map(float, velocity))

        moving_cart_before = moving_cart()
        idle = control.call("block", 10, 170, 22)["state"]
        active = control.call("block", 15, 170, 26)["state"]
        if "shape=east_west" not in idle or "backwards=false" not in idle:
            raise RuntimeError(f"Idle rail did not reach expected state before save: {idle}")
        if "shape=east_west" not in active or "backwards=true" not in active or "power=15" not in active:
            raise RuntimeError(f"Powered rail did not reach expected active state before save: {active}")
        control.command("/save-all")
        control.restart()
        idle_after = control.call("block", 10, 170, 22)["state"]
        active_after = control.call("block", 15, 170, 26)["state"]
        if idle_after != idle or active_after != active:
            raise RuntimeError(f"Rail state changed across reopen: idle {idle!r}->{idle_after!r}; active {active!r}->{active_after!r}")
        moving_cart_after = moving_cart()
        if moving_cart_after[0][0] < moving_cart_before[0][0] - 1e-6:
            raise RuntimeError(f"Cart position regressed across reopen: {moving_cart_before}->{moving_cart_after}")
        control.step_to(control.clock() + 1)
        moving_cart_after_step = moving_cart()
        if moving_cart_after_step[0][0] <= moving_cart_after[0][0]:
            raise RuntimeError(f"Powered rail did not resume cart movement after reopen: {moving_cart_after}->{moving_cart_after_step}")
    print("Idle and powered rail states survived save/reopen, and cart movement resumed.")


def guest(args):
    with TemporaryDirectory(prefix="hc-controller-rail-lan-") as temp:
        with multiplayer.dedicated(args, Path(temp), scenario="controller-rail-lan", pack=args.pack) as (address, command):
            command("setblock 10 96 10 minecraft:stone")
            command("setblock 10 97 10 create:controller_rail[shape=east_west,backwards=true]")
            command("setblock 10 97 9 minecraft:redstone_block")
            with multiplayer.joined_client(args, Path(temp), address, "RailGuest",
                                           scenario="controller-rail-lan", pack=args.pack) as guest_client:
                command("tp RailGuest 10.5 98 14.5")
                def guest_sees_rail():
                    state = guest_client.call("block", 10, 97, 10)["state"]
                    return (state.startswith("create:controller_rail[")
                            and all(value in state for value in (
                                "shape=east_west", "backwards=true", "waterlogged=false", "power=15")))

                multiplayer.until("guest to observe the powered Controller Rail", guest_sees_rail)
    print("LAN guest observed the host's powered Controller Rail state.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--persistence", action="store_true")
    group.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    (guest if args.lan else persistence)(args)


if __name__ == "__main__":
    main()
