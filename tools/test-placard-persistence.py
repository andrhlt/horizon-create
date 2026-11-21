#!/usr/bin/env python3
"""Check stored-item and live pulse state across Placard world reopen."""

import argparse
from pathlib import Path
from importlib import import_module

from fixture_world import fixture_world

mp = import_module("test-multiplayer")
probe = import_module("test-nozzle")
PLACARD = (5, 170, 21)


def item_tag(control):
    return control.command(f"/data get block {' '.join(map(str, PLACARD))} Item")


def run(args):
    with fixture_world(args, "Placard-persistence", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 1 169 16 10 169 27 minecraft:stone",
            "/setblock 5 170 20 minecraft:stone",
            f"/setblock {' '.join(map(str, PLACARD))} create:placard[face=wall,facing=south]",
            f'/data merge block {" ".join(map(str, PLACARD))} {{Item:{{id:"minecraft:diamond",count:1}}}}',
            "/gamemode survival",
            "/tp @s 5.5 170 23.5",
            "/item replace entity @s hotbar.0 with minecraft:diamond",
        ))
        if "minecraft:diamond" not in item_tag(control):
            raise RuntimeError("The Placard did not retain its idle displayed diamond before save.")

        control.restart()
        control.call("wait", 3)
        if "minecraft:diamond" not in item_tag(control):
            raise RuntimeError("The idle displayed diamond was lost on world reopen.")

        control.call("select", "minecraft:diamond")
        probe.aim(control, (5.5, 170.5, 21.5), PLACARD)
        control.call("mouse", "right", "click")
        mp.until("matching diamond to activate the Placard", lambda:
                 "powered=true" in probe.state(control, PLACARD))
        active_ticks = control.command(f"/data get block {' '.join(map(str, PLACARD))} PoweredTicks")
        control.restart()
        control.call("wait", 3)
        if "minecraft:diamond" not in item_tag(control):
            raise RuntimeError("The active Placard's displayed item was lost on world reopen.")
        if "powered=true" not in probe.state(control, PLACARD):
            raise RuntimeError("The active pulse was not retained on world reopen.")
        reopened_ticks = control.command(f"/data get block {' '.join(map(str, PLACARD))} PoweredTicks")
        before = int(active_ticks.rsplit(" ", 1)[-1])
        after = int(reopened_ticks.rsplit(" ", 1)[-1])
        if after > before or after <= 0:
            raise RuntimeError(f"The Placard pulse timer did not resume across reopen: {before} -> {after}")
        for _ in range(25):
            control.step_to(control.clock() + 1)
        mp.until("the resumed pulse to expire", lambda:
                 "powered=false" in probe.state(control, PLACARD))
        if "minecraft:diamond" not in item_tag(control):
            raise RuntimeError("Pulse expiry changed the stored item.")
    print("Idle Placard contents and an active redstone pulse survived save/reopen and resumed without losing the item.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
