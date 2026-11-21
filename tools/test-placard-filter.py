#!/usr/bin/env python3
"""Check Java List Filter whitelist matching on a Placard."""

import argparse
from pathlib import Path
from importlib import import_module

from fixture_world import fixture_world

mp = import_module("test-multiplayer")
probe = import_module("test-nozzle")
AT = (5, 170, 21)


def run(args):
    with fixture_world(args, "Placard-filter", render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as control:
        coords = " ".join(map(str, AT))
        control.commands((
            "/fill 1 169 16 10 169 27 minecraft:stone",
            "/setblock 5 170 20 minecraft:stone",
            f"/setblock {coords} create:placard[face=wall,facing=south]",
            f'/data merge block {coords} {{Item:{{id:"create:filter",count:1,components:{{"create:filter_items":[{{slot:0,item:{{id:"minecraft:diamond",count:1}}}}]}}}}}}',
            "/gamemode survival",
            "/tp @s 5.5 170 23.5",
            "/item replace entity @s hotbar.0 with minecraft:emerald",
            "/item replace entity @s hotbar.1 with minecraft:diamond",
        ))
        mp.until("filter to reach the Placard", lambda: "create:filter" in control.command(
            f"/data get block {coords} Item"))
        for item, expected in (("minecraft:emerald", False), ("minecraft:diamond", True)):
            control.call("select", item)
            probe.aim(control, (5.5, 170.5, 21.5), AT)
            control.call("mouse", "right", "click")
            if expected:
                mp.until("whitelisted diamond to activate the Placard", lambda:
                         "powered=true" in probe.state(control, AT))
            else:
                control.step_to(control.clock() + 1)
                if "powered=true" in probe.state(control, AT):
                    raise RuntimeError("A nonmatching emerald activated the diamond-whitelist Placard.")
            if mp.count(control, item) != 1:
                raise RuntimeError(f"Placard filter matching consumed the held {item}.")
    print("The Placard's List Filter rejected an emerald, accepted a diamond, and consumed neither item.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
