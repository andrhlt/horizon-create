#!/usr/bin/env python3
"""Check Stockpile Switch contents, settings and threshold state across reopen."""
import argparse
from pathlib import Path
import re

from fixture_world import fixture_world

BARREL = (8, 101, -7)
ITEM_SWITCH = (8, 101, -8)
TANK = (13, 101, -7)
FLUID_SWITCH = (13, 101, -8)


def xyz(pos):
    return " ".join(map(str, pos))


def field(data, name):
    match = re.search(rf"\b{name}: (-?\d+)", data)
    if not match:
        raise RuntimeError(f"Missing {name} in Stockpile Switch data: {data}")
    return int(match[1])


def data(world, pos):
    return world.command(f"/data get block {xyz(pos)}")


def setup(world):
    world.commands((
        "/fill 7 100 -9 14 100 -6 minecraft:smooth_stone",
        f"/setblock {xyz(BARREL)} minecraft:barrel",
        f"/item replace block {xyz(BARREL)} container.0 with minecraft:stone 32",
        f"/setblock {xyz(ITEM_SWITCH)} create:stockpile_switch[target=wall,facing=south]",
        f"/setblock {xyz(TANK)} create:fluid_tank",
        f"/setblock {xyz(FLUID_SWITCH)} create:stockpile_switch[target=wall,facing=south]",
        f"/data merge block {xyz(ITEM_SWITCH)} {{OffBelowAmount:16,OnAboveAmount:48,Inverted:0,InStacks:0}}",
        f"/data merge block {xyz(TANK)} {{TankContent:{{Fluid:{{id:\"minecraft:water\",amount:4000}}}}}}",
        f"/data merge block {xyz(FLUID_SWITCH)} {{OffBelowAmount:1000,OnAboveAmount:3000,Inverted:1,InStacks:0}}",
    ))


def assert_retained(world, *, active):
    item = data(world, ITEM_SWITCH)
    fluid = data(world, FLUID_SWITCH)
    barrel = data(world, BARREL)
    tank = data(world, TANK)
    expected_item = (16, 48, 0, 0, 32, 0 if active else 0)
    got_item = (field(item, "OffBelowAmount"), field(item, "OnAboveAmount"),
                field(item, "Inverted"), field(item, "InStacks"),
                field(item, "CurrentAmount"), field(item, "PoweredAfterDelay"))
    expected_fluid = (1000, 3000, 1, 0, 4000, 0 if active else 1)
    got_fluid = (field(fluid, "OffBelowAmount"), field(fluid, "OnAboveAmount"),
                 field(fluid, "Inverted"), field(fluid, "InStacks"),
                 field(fluid, "CurrentAmount"), field(fluid, "PoweredAfterDelay"))
    if got_item != expected_item or got_fluid != expected_fluid:
        raise RuntimeError(f"Stockpile state changed across reopen: item={got_item} {item}; fluid={got_fluid} {fluid}")
    if "minecraft:stone" not in barrel or "count: 32" not in barrel:
        raise RuntimeError(f"Barrel contents were lost across reopen: {barrel}")
    if "minecraft:water" not in tank or "amount: 4000" not in tank:
        raise RuntimeError(f"Tank contents were lost across reopen: {tank}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with fixture_world(args, "StockpileSwitchLifecycle", pack=args.pack) as world:
        setup(world)
        world.step_to(world.clock() + 3)
        assert_retained(world, active=False)
        world.command("/save-all flush")
        world.restart()
        assert_retained(world, active=False)

        world.command(f"/item replace block {xyz(BARREL)} container.0 with minecraft:stone 64")
        world.step_to(world.clock() + 3)
        before = data(world, ITEM_SWITCH)
        if field(before, "PoweredAfterDelay") != 1:
            raise RuntimeError(f"Item threshold did not activate before active save: {before}")
        world.command("/save-all flush")
        world.restart()
        resumed = data(world, ITEM_SWITCH)
        if field(resumed, "PoweredAfterDelay") != 1 or field(resumed, "CurrentAmount") != 64:
            raise RuntimeError(f"Active item threshold did not survive reopen: {before} -> {resumed}")
    print("Stockpile Switch idle item/fluid settings and contents, plus active item threshold output, survived save/reopen.")


if __name__ == "__main__":
    main()
