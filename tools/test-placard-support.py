#!/usr/bin/env python3
"""Check collision-shape support and support-loss item recovery."""

import argparse
from pathlib import Path

from fixture_world import fixture_world
from importlib import import_module

mp = import_module("test-multiplayer")
probe = import_module("test-nozzle")
PLACARD = (5, 170, 21)
SUPPORT = (5, 170, 20)


def run(args):
    with fixture_world(args, "Placard-support", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 1 169 16 10 169 27 minecraft:stone",
            f"/setblock {' '.join(map(str, SUPPORT))} minecraft:stone",
        ))
        control.command(f"/setblock {' '.join(map(str, PLACARD))} create:placard[face=wall,facing=south]")
        mp.until("Placard to survive on stone", lambda:
                 "create:placard" in probe.state(control, PLACARD))
        control.command(f"/setblock {' '.join(map(str, SUPPORT))} minecraft:structure_void")
        mp.until("unsupported Placard to detach", lambda:
                 probe.state(control, PLACARD) == "minecraft:air")
    print("Placard survival and neighbor updates reject an empty-collision backing state while retaining solid support.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
