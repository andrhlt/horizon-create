#!/usr/bin/env python3
"""Check survival Depot acquisition, idle reopen, and pushing Funnel custody."""

import argparse
from importlib import import_module
from pathlib import Path
import re

from fixture_world import fixture_world

crafting = import_module("test-survival-crafting")
lifecycle = import_module("test-press-lifecycle")
DEPOT = "create:depot"
ALLOY = "create:andesite_alloy"
CASING = "create:andesite_casing"
IRON = "minecraft:iron_ingot"
GOLD = "minecraft:gold_ingot"
PLACEMENT = (5, 105, -11)


def position(coords):
    return " ".join(map(str, coords))


def contents(control, coords):
    reply = control.command(f"/data get block {position(coords)}")
    if not re.search(r'\bid: "(?:create:depot|minecraft:barrel)"', reply):
        raise RuntimeError(f"Cannot read inventory at {coords}: {reply}")
    entries = re.search(r"\bItems: \[([^\]]*)\]", reply)
    stacks = {}
    for item in re.findall(r"\{([^{}]*)\}", entries[1] if entries else ""):
        slot = int(re.search(r"\bSlot: (\d+)", item)[1])
        name = re.search(r'\bid: "([^"]+)"', item)[1]
        count = int(re.search(r"\bcount: (\d+)", item)[1])
        stacks[slot] = (name, count)
    return stacks


def player_counts(control, *names):
    counts = control.call("inventory")["counts"]
    return tuple(counts.get(name, 0) for name in names)


def survival(args):
    with fixture_world(args, "DepotSurvivalReopen", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 4 104 -13 8 104 -9 minecraft:smooth_stone",
            "/tp @s 7.5 105 -10.5",
            "/gamemode survival @s",
            f"/item replace entity @s hotbar.0 with {ALLOY}",
            f"/item replace entity @s hotbar.1 with {CASING}",
            f"/item replace entity @s hotbar.2 with {IRON} 3",
            f"/item replace entity @s hotbar.3 with {GOLD} 2",
        ))
        control.call("open-inventory")
        for ingredient, grid in ((ALLOY, 100), (CASING, 103)):
            crafting.distribute(control, crafting.inventory_slot(control, ingredient), (grid,))
        crafting.craft(control, DEPOT, 1)
        control.call("close")
        assert player_counts(control, DEPOT, ALLOY, CASING) == (1, 0, 0)
        control.call("select", DEPOT)
        control.call("interact", 5, 104, -11, "up")
        assert control.call("block", *PLACEMENT)["block"] == DEPOT
        assert player_counts(control, DEPOT) == (0,)

        control.call("select", IRON)
        control.call("interact", *PLACEMENT, "up")
        assert contents(control, PLACEMENT) == {0: (IRON, 3)}
        assert player_counts(control, IRON, GOLD) == (0, 2)
        control.call("select", GOLD)
        control.call("interact", *PLACEMENT, "up")
        assert contents(control, PLACEMENT) == {0: (GOLD, 2)}
        assert player_counts(control, IRON, GOLD) == (3, 0)
        for _ in range(24):
            control.step_to(control.clock() + 1)

        control.restart()
        assert control.call("block", *PLACEMENT)["block"] == DEPOT
        assert contents(control, PLACEMENT) == {0: (GOLD, 2)}
        control.call("command", "/gamemode survival @s")
        control.call("select", 9)
        control.call("interact", *PLACEMENT, "up")
        assert contents(control, PLACEMENT) == {}
        assert player_counts(control, IRON, GOLD) == (3, 2)
    print("Survival crafting and placement consumed both ingredients and the Depot item. "
          "Manual use swapped the complete stacks, and both gold ingots were retrieved after idle reopen.")


def occupied_funnel(args):
    with fixture_world(args, "DepotPushingCustody", pack=args.pack) as control:
        control.commands((
            "/fill 2 103 -15 12 103 -8 minecraft:smooth_stone",
            "/fill 2 104 -15 12 110 -8 minecraft:air",
            "/gamemode spectator @s",
            "/tp @s 8.5 105 -10.5",
        ))
        for z, occupying in ((-13, IRON), (-9, GOLD)):
            depot, funnel, supply = (5, 104, z), (5, 105, z), (6, 105, z)
            control.commands((
                f"/setblock {position(depot)} {DEPOT}",
                f"/setblock {position(supply)} minecraft:barrel",
            ))
            control.step_to(control.clock() + 1)
            control.commands((
                f"/item replace block {position(depot)} container.0 with {occupying} 3",
                f"/item replace block {position(supply)} container.0 with {IRON}",
                f"/setblock {position(funnel)} create:brass_belt_funnel[facing=west,shape=pushing]",
            ))
            for _ in range(16):
                control.step_to(control.clock() + 1)
                assert contents(control, depot) == {0: (occupying, 3)}, (z, occupying)
                assert contents(control, supply) == {0: (IRON, 1)}, (z, occupying)

            # Clear the fixture's obstruction without disturbing the Funnel or supply.
            control.command(f"/item replace block {position(depot)} container.0 with minecraft:air")
            lifecycle.wait_until(control, lambda: contents(control, depot) == {0: (IRON, 1)},
                                 f"the Funnel to feed the cleared {occupying} rig", timeout=20)
            assert contents(control, supply) == {}, (z, occupying)
    print("Pushing Funnels rejected both matching and different stacks for 16 ticks per rig, "
          "then transferred exactly one ingot per rig after the Depots were cleared.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--funnel", action="store_true")
    args = parser.parse_args()
    (occupied_funnel if args.funnel else survival)(args)
