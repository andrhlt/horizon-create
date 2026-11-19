#!/usr/bin/env python3
"""Check original Create food spouting and survival consumption."""
import argparse
import re
from pathlib import Path
from fixture_world import fixture_world

CASES = (("sweet_roll", "bread", "minecraft:milk", 6, 9.6),
         ("chocolate_glazed_berries", "sweet_berries", "create:chocolate", 7, 11.2),
         ("honeyed_apple", "apple", "create:honey", 8, 12.8))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with fixture_world(args, "CreateFoods", pack=args.pack) as world:
        world.command("/gamemode survival")
        for i, (name, ingredient, fluid, _, _) in enumerate(CASES):
            x = 5 + i * 3
            world.commands((f"/setblock {x} 106 -11 create:spout", f"/setblock {x} 104 -11 create:depot",
                f'/data merge block {x} 106 -11 {{Tanks:[{{TankContent:{{Fluid:{{id:"{fluid}",amount:500}}}}}}]}}',
                f"/item replace block {x} 104 -11 container.0 with minecraft:{ingredient}"))
        start = world.clock()
        for tick in range(1, 50):
            world.step_to(start + tick)
        for i, (name, ingredient, fluid, _, _) in enumerate(CASES):
            x = 5 + i * 3
            depot = world.command(f"/data get block {x} 104 -11 Items")
            spout = world.command(f"/data get block {x} 106 -11")
            assert f'id: "create:{name}"' in depot, depot
            assert 'amount: 250' in spout, spout
        print("All three spout recipes produced their foods and used 250 mB.")
        def field(key):
            data = world.command(f"/data get entity @s {key}")
            return float(re.search(r": (-?[0-9.]+)", data)[1])
        for name, _, _, nutrition, saturation in CASES:
            world.command("/effect give @s minecraft:instant_health 1 5 true")
            world.command("/effect give @s minecraft:hunger 30 255 true")
            while field("foodLevel") > 9 or field("foodSaturationLevel") > 0:
                world.step_to(world.clock() + 1)
            world.command("/effect clear @s minecraft:hunger")
            before = field("foodLevel")
            world.command(f"/item replace entity @s hotbar.0 with create:{name}")
            world.call("select", 1)
            world.call("mouse", "right", "down")
            start = world.clock()
            for tick in range(1, 37):
                world.step_to(start + tick)
            world.call("mouse", "right", "up")
            level, actual = field("foodLevel"), field("foodSaturationLevel")
            assert level == min(20, before + nutrition), (name, before, level)
            assert abs(actual - min(level, saturation)) < .001, (name, actual, saturation)
            assert world.call("inventory")["counts"].get(f"create:{name}", 0) == 0
            print(f"{name}: survival use restored {nutrition} food and {actual} saturation.")
if __name__ == '__main__': main()
