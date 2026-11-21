#!/usr/bin/env python3
"""Check that a LAN guest can collect output produced by a powered Mechanical Saw."""

import argparse
import importlib
from pathlib import Path
import tempfile

from fixture_world import fixture_world

mp = importlib.import_module("test-multiplayer")
SAW = (8, 97, 8)
MOTOR = (8, 97, 7)
GUEST_POSITION = (10.3, 98.0, 8.5)


def run(args):
    with tempfile.TemporaryDirectory(prefix="hc-saw-lan-") as directory:
        with fixture_world(args, "MechanicalSawLAN", render=True, pack=args.pack) as host:
            host.commands((
                "/fill 5 95 5 12 95 12 minecraft:smooth_stone",
                f"/setblock {MOTOR[0]} {MOTOR[1]} {MOTOR[2]} create:creative_motor[facing=south]{{ScrollValue:96}}",
                f"/setblock {SAW[0]} {SAW[1]} {SAW[2]} create:mechanical_saw[facing=up]",
                "/setblock 9 97 8 minecraft:smooth_stone",
                "/setblock 10 97 8 minecraft:smooth_stone",
                f'/data merge block {SAW[0]} {SAW[1]} {SAW[2]} {{Filter:{{id:"minecraft:bamboo_mosaic",count:1}}}}',
                "/setworldspawn 1000 100 1000",
                "/gamemode survival",
            ))
            host.command("/tick unfreeze")
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            with mp.joined_client(args, Path(directory), f"127.0.0.1:{port}", "SawGuest", render=True,
                                  scenario="mechanical-saw", pack=args.pack) as guest:
                mp.until("the guest to join", lambda: any(
                    player["name"] == "SawGuest" and player["placed"]
                    for player in host.call("lan", "status")["guests"]
                ))
                host.command("/gamemode survival SawGuest")
                host.command(f"/tp SawGuest {GUEST_POSITION[0]} {GUEST_POSITION[1]} {GUEST_POSITION[2]}")
                host.command(
                    '/summon minecraft:item 8.5 97.79 8.5 {Item:{id:"minecraft:bamboo_planks",count:1},Motion:[0.0d,0.0d,0.0d]}'
                )
                try:
                    mp.until("the guest to collect the saw's Bamboo Mosaic", lambda:
                        mp.count(guest, "minecraft:bamboo_mosaic") == 1, seconds=20)
                except RuntimeError as error:
                    raise RuntimeError(
                        f"{error}; saw={host.command(f'/data get block {SAW[0]} {SAW[1]} {SAW[2]}')}; "
                        f"guest={guest.call('inventory')}; entities={host.call('entities', 12, 'minecraft:item')['entities']}"
                    ) from error
                if mp.count(guest, "minecraft:bamboo_planks") != 0:
                    raise RuntimeError(f"Guest received output but input was duplicated: {guest.call('inventory')}")
    print("The LAN guest collected the powered saw's filtered Bamboo Mosaic output.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
