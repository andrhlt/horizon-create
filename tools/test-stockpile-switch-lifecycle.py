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
    match = re.search(rf"\b{name}: (-?\d+(?:\.\d+)?)[bfd]?\b", data)
    if not match:
        raise RuntimeError(f"Missing {name} in Stockpile Switch data: {data}")
    return int(float(match[1]))


def data(world, pos):
    return world.command(f"/data get block {xyz(pos)}")


def setup(world):
    world.commands((
        "/fill 7 100 -9 14 100 -6 minecraft:smooth_stone",
        f"/setblock {xyz(BARREL)} minecraft:barrel",
        f"/item replace block {xyz(BARREL)} container.0 with minecraft:stone 32",
        f"/item replace block {xyz(BARREL)} container.1 with minecraft:dirt 16",
        f"/setblock {xyz(ITEM_SWITCH)} create:stockpile_switch[target=wall,facing=south]",
        f"/setblock {xyz(TANK)} create:fluid_tank",
        f"/setblock {xyz(FLUID_SWITCH)} create:stockpile_switch[target=wall,facing=south]",
        f'/data merge block {xyz(ITEM_SWITCH)} {{Filter:{{id:"minecraft:stone",count:1}}}}',
        f'/data merge block {xyz(FLUID_SWITCH)} {{Filter:{{id:"minecraft:water_bucket",count:1}}}}',
        f"/data merge block {xyz(ITEM_SWITCH)} {{OffBelowAmount:16,OnAboveAmount:48,Inverted:0,InStacks:0}}",
        f"/data merge block {xyz(TANK)} {{TankContent:{{Fluid:{{id:\"minecraft:water\",amount:2000}}}}}}",
        f"/data merge block {xyz(FLUID_SWITCH)} {{OffBelowAmount:1000,OnAboveAmount:3000,Inverted:0,InStacks:0}}",
    ))


def assert_target(world, pos, target):
    result = world.command(
        f"/execute if block {xyz(pos)} create:stockpile_switch[target=wall,facing=south]"
    )
    if not result.startswith("Test passed"):
        raise RuntimeError(f"Stockpile Switch target {target} did not survive reopen: {result}")


def assert_contents(world, *, stone, dirt, water):
    barrel = data(world, BARREL)
    tank = data(world, TANK)
    stacks = {}
    for entry in re.findall(r"\{([^{}]+)\}", barrel):
        item = re.search(r'id: "([^"]+)"', entry)
        count = re.search(r"count: (\d+)", entry)
        if item and count:
            stacks[item[1]] = int(count[1])
    expected = {"minecraft:stone": stone, "minecraft:dirt": dirt}
    if stacks != expected:
        raise RuntimeError(f"Barrel contents changed: expected {expected}, got {stacks}; {barrel}")
    if "minecraft:water" not in tank or f"amount: {water}" not in tank:
        raise RuntimeError(f"Tank contents changed: expected water {water} mB, got {tank}")


def assert_switch(world, pos, *, lower, upper, amount, inverted, powered, output, filter_item):
    result = data(world, pos)
    got = tuple(field(result, key) for key in (
        "OffBelowAmount", "OnAboveAmount", "CurrentAmount", "Inverted", "Powered", "PoweredAfterDelay",
    ))
    expected = (lower, upper, amount, inverted, powered, output)
    if got != expected:
        raise RuntimeError(f"Stockpile Switch state mismatch at {xyz(pos)}: {got} != {expected}; {result}")
    sample = world.command(f"/data get block {xyz(pos)} Filter")
    if filter_item not in sample:
        raise RuntimeError(f"Stockpile Switch filter {filter_item} was not retained at {xyz(pos)}: {sample}")
    assert_target(world, pos, "barrel" if pos == ITEM_SWITCH else "fluid tank")


def assert_idle(world):
    assert_switch(world, ITEM_SWITCH, lower=16, upper=48, amount=32, inverted=0,
                  powered=0, output=0, filter_item="minecraft:stone")
    assert_switch(world, FLUID_SWITCH, lower=1000, upper=3000, amount=2000, inverted=0,
                  powered=0, output=0, filter_item="minecraft:water_bucket")
    assert_contents(world, stone=32, dirt=16, water=2000)


def advance(world, ticks):
    for _ in range(ticks):
        world.step_to(world.clock() + 1)


def assert_active(world):
    assert_switch(world, ITEM_SWITCH, lower=16, upper=48, amount=64, inverted=0,
                  powered=1, output=1, filter_item="minecraft:stone")
    assert_switch(world, FLUID_SWITCH, lower=1000, upper=3000, amount=4000, inverted=0,
                  powered=1, output=1, filter_item="minecraft:water_bucket")
    assert_contents(world, stone=64, dirt=16, water=4000)


def set_stocks(world, *, stone, dirt, water):
    world.commands((
        f"/item replace block {xyz(BARREL)} container.0 with minecraft:stone {stone}",
        f"/item replace block {xyz(BARREL)} container.1 with minecraft:dirt {dirt}",
        f'/data merge block {xyz(TANK)} {{TankContent:{{Fluid:{{id:"minecraft:water",amount:{water}}}}}}}',
    ))


def assert_mid_band(world):
    assert_switch(world, ITEM_SWITCH, lower=16, upper=48, amount=32, inverted=0,
                  powered=1, output=1, filter_item="minecraft:stone")
    assert_switch(world, FLUID_SWITCH, lower=1000, upper=3000, amount=2000, inverted=0,
                  powered=1, output=1, filter_item="minecraft:water_bucket")
    assert_contents(world, stone=32, dirt=48, water=2000)


def assert_below(world):
    assert_switch(world, ITEM_SWITCH, lower=16, upper=48, amount=16, inverted=0,
                  powered=0, output=0, filter_item="minecraft:stone")
    assert_switch(world, FLUID_SWITCH, lower=1000, upper=3000, amount=1000, inverted=0,
                  powered=0, output=0, filter_item="minecraft:water_bucket")
    assert_contents(world, stone=16, dirt=64, water=1000)


def assert_at_upper(world):
    assert_switch(world, ITEM_SWITCH, lower=16, upper=48, amount=48, inverted=0,
                  powered=1, output=1, filter_item="minecraft:stone")
    assert_switch(world, FLUID_SWITCH, lower=1000, upper=3000, amount=3000, inverted=0,
                  powered=1, output=1, filter_item="minecraft:water_bucket")
    assert_contents(world, stone=48, dirt=32, water=3000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with fixture_world(args, "StockpileSwitchLifecycle", pack=args.pack) as world:
        setup(world)
        advance(world, 14)
        assert_idle(world)
        world.command("/save-all flush")
        world.restart()
        assert_idle(world)

        set_stocks(world, stone=64, dirt=16, water=4000)
        advance(world, 14)
        assert_active(world)
        world.command("/save-all flush")
        world.restart()
        assert_active(world)

        set_stocks(world, stone=32, dirt=48, water=2000)
        advance(world, 14)
        assert_mid_band(world)
        world.command("/save-all flush")
        world.restart()
        assert_mid_band(world)
        set_stocks(world, stone=16, dirt=64, water=1000)
        advance(world, 14)
        assert_below(world)
        set_stocks(world, stone=48, dirt=32, water=3000)
        advance(world, 14)
        assert_at_upper(world)
        world.command("/save-all flush")
        world.restart()
        assert_at_upper(world)
    print("Stockpile Switch retained idle and active item/fluid settings, filters, target links and contents across reopen; both hysteresis boundaries passed.")


if __name__ == "__main__":
    main()
