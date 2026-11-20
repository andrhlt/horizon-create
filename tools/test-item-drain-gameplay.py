#!/usr/bin/env python3
"""Finite Item Drain acquisition, collection, capacity, handoff and reopen checks.

Rules come from pinned ItemDrainBlock/BlockEntity and GenericItemEmptying.
The existing Java replay remains the exact timing reference; these checks add
source-derived gameplay boundaries and Horizon persistence, not Java reload parity.
"""

import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

reference = import_module("test-item-drain")
crafting = import_module("test-survival-crafting")
DRAIN = "create:item_drain"
IRON = "minecraft:iron_ingot"
HONEY = "minecraft:honey_bottle"
BOTTLE = "minecraft:glass_bottle"
POS = "4 97 -9"


def state(world, pos=POS):
    return reference.values(world.command(f"/data get block {pos}"))


def advance(world, ticks):
    start = world.clock()
    for tick in range(1, ticks + 1):
        world.step_to(start + tick)


def require(actual, expected, description):
    if actual != expected:
        raise RuntimeError(f"{description}: expected {expected}, got {actual}")


def seed(world, item, count=1, pos=POS):
    world.commands((
        f"/setblock {pos} {DRAIN}",
        f"/item replace block {pos} container.0 with {item} {count}",
        f"/data merge block {pos} {{HeldItem:{{Pos:0.0f,InDirection:5}}}}",
    ))
    # Native stores container cargo separately; one tick serializes Item into
    # HeldItem before the reader (or a collection action) inspects it.
    advance(world, 1)
    require(state(world, pos)[1:3], (item, count), "Seeded drain cargo")


def tank(world, fluid=None, amount=0):
    contents = f'Fluid:{{id:"{fluid}",amount:{amount}}}' if fluid else ""
    world.command(f"/data merge block {POS} {{Tanks:[{{TankContent:{{{contents}}}}}]}}")


def setup(world):
    world.commands((
        "/fill 2 96 -12 8 96 -6 minecraft:smooth_stone",
        "/setblock 5 97 -9 minecraft:smooth_stone",
        "/tp @s 4.5 97 -6.5",
        "/gamemode survival",
    ))


def collection(args):
    with fixture_world(args, "DrainCollection", render=True, pack=args.pack) as world:
        setup(world)
        seed(world, IRON, 3)
        world.commands((
            "/item replace entity @s hotbar.0 with minecraft:stick",
            "/item replace entity @s hotbar.1 with minecraft:cobblestone",
            "/item replace entity @s hotbar.8 with minecraft:air",
        ))
        world.call("wait", 3)
        # Java lets non-fluid BlockItems place normally without collecting cargo.
        world.call("select", "minecraft:cobblestone")
        world.call("interact", 4, 97, -9, "up")
        require(state(world)[1:3], (IRON, 3), "Block item interaction retained drain cargo")
        require(world.call("block", 4, 98, -9)["state"], "minecraft:cobblestone", "Block placement passed through drain interaction")
        world.command("/setblock 4 98 -9 minecraft:air")
        # ItemDrainBlock.useItemOn falls through tryExchange to collection for sticks.
        world.call("select", "minecraft:stick")
        world.call("interact", 4, 97, -9, "up")
        require(state(world)[1:3], ("minecraft:air", 0), "Stick interaction collected cargo")
        counts = world.call("inventory")["counts"]
        require((counts.get(IRON, 0), counts.get("minecraft:stick", 0)), (3, 1), "Collection inventory conservation")
        world.call("interact", 4, 97, -9, "up")
        require(world.call("inventory")["counts"].get(IRON, 0), 3, "Repeated stick collection did not duplicate cargo")
        world.command(f"/clear @s {IRON}")
        seed(world, IRON, 3)
        world.call("select", 9)
        world.call("interact", 4, 97, -9, "up")
        require(state(world)[1:3], ("minecraft:air", 0), "Empty-hand interaction collected cargo")
        require(world.call("inventory")["counts"].get(IRON, 0), 3, "Empty-hand collection inventory conservation")
        world.call("select", 9)
        world.call("interact", 4, 97, -9, "up")
        require(world.call("inventory")["counts"].get(IRON, 0), 3, "Repeated collection did not duplicate cargo")
    print("Block placement passed through; stick and empty-hand collection each returned cargo once across repeated interactions.")


def acquisition(args):
    with fixture_world(args, "DrainAcquisition", render=True, pack=args.pack) as world:
        setup(world)
        world.commands((
            "/item replace entity @s hotbar.0 with minecraft:iron_bars",
            "/item replace entity @s hotbar.1 with create:copper_casing",
        ))
        world.call("wait", 3)
        world.call("open-inventory")
        crafting.distribute(world, 0, (100,))
        crafting.distribute(world, 1, (102,))
        crafting.craft(world, DRAIN, 1)
        world.call("close")
        world.call("select", DRAIN)
        world.call("interact", 4, 96, -9, "up")
        require(world.call("block", 4, 97, -9)["state"], DRAIN, "Survival crafted drain placement")
        counts = world.call("inventory")["counts"]
        require(tuple(counts.get(item, 0) for item in (DRAIN, "minecraft:iron_bars", "create:copper_casing")), (0, 0, 0), "Craft/place ingredient conservation")
    print("Survival crafting consumed iron bars and copper casing and placed one Item Drain.")


def boundaries(args):
    with fixture_world(args, "DrainBoundaries", render=True, pack=args.pack) as world:
        setup(world)
        for label, fluid, amount in (("incompatible", "minecraft:water", 250), ("full", "create:honey", 1500)):
            seed(world, HONEY)
            tank(world, fluid, amount)
            advance(world, 40)
            require(state(world), (20, HONEY, 1, 0.5, fluid, amount), f"{label} tank stalled without consuming input")
            world.command(f"/item replace entity @s hotbar.0 with {HONEY} 2")
            world.call("select", HONEY)
            world.call("interact", 4, 97, -9, "up")
            counts = world.call("inventory")["counts"]
            require((counts.get(HONEY, 0), counts.get(BOTTLE, 0)), (2, 0), f"{label} direct pour rejected without loss")
            require(state(world), (20, HONEY, 1, 0.5, fluid, amount), f"{label} rejected pour retained cargo and fluid")
            tank(world)
            advance(world, 30)
            require(state(world), (0, BOTTLE, 1, 1.0, "create:honey", 250), f"{label} tank recovered after extraction")
        # A solid exit retains a whole solid stack. Replacing it with a drain
        # allows the original direct-belt handoff, without duplicating cargo.
        seed(world, IRON, 3)
        advance(world, 12)
        require(state(world)[1:4], (IRON, 3, 1.0), "Solid output blocked cargo")
        world.commands(("/setblock 5 97 -9 create:item_drain", "/setblock 6 97 -9 minecraft:smooth_stone"))
        advance(world, 12)
        require(state(world)[1:3], ("minecraft:air", 0), "Recovered handoff emptied source")
        require(state(world, "5 97 -9")[1:4], (IRON, 3, 1.0), "Recovered handoff retained complete cargo")
    print("Incompatible/full tanks rejected pours and stalled input, recovered after clearing; blocked output handed off once.")


def persistence(args):
    with fixture_world(args, "DrainReopen", pack=args.pack) as world:
        setup(world)
        world.command(f"/setblock {POS} {DRAIN}")
        tank(world, "create:honey", 250)
        before = state(world)
        world.restart()
        require(state(world), before, "Idle reopen preserved honey and empty cargo")
        seed(world, HONEY)
        tank(world, "create:honey", 250)
        advance(world, 9)
        before = state(world)
        if not (0 < before[0] < 20 and before[1:3] == (HONEY, 1)):
            raise RuntimeError(f"Active fixture did not reach partway processing: {before}")
        world.restart()
        # Opening can advance server ticks before freeze: accept progress or
        # completion, then assert the unique terminal item/fluid totals.
        after = state(world)
        if after[1:3] == (HONEY, 1):
            require(after[-2:], ("create:honey", 250), "Unfinished input retained initial honey")
        else:
            require(after[1:3], (BOTTLE, 1), "Reopened active cargo")
            require(after[-2:], ("create:honey", 500), "Reopened completed fluid")
        advance(world, 40)
        require(state(world), (0, BOTTLE, 1, 1.0, "create:honey", 500), "Active reopen completed once")
        world.restart()
        require(state(world), (0, BOTTLE, 1, 1.0, "create:honey", 500), "Completed reopen did not process output again")
    print("Idle, partway and completed reopen conserved cargo and fluid without duplicate processing.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--case", choices=("all", "acquisition", "collection", "boundaries", "persistence"), default="all")
    args = parser.parse_args()
    for name, action in (("acquisition", acquisition), ("collection", collection), ("boundaries", boundaries), ("persistence", persistence)):
        if args.case in ("all", name):
            action(args)


if __name__ == "__main__":
    main()
