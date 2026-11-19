#!/usr/bin/env python3
"""Check Honey and Chocolate buckets through a spout and an item drain."""
import argparse
from pathlib import Path
from fixture_world import fixture_world


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with fixture_world(args, "FluidBucketMachines", pack=args.pack) as world:
        for z, fluid in ((-11, "honey"), (-8, "chocolate")):
            world.commands((
                f"/setblock 8 106 {z} create:spout",
                f"/setblock 8 104 {z} create:depot",
                f'/data merge block 8 106 {z} {{Tanks:[{{TankContent:{{Fluid:{{id:"create:{fluid}",amount:1000}}}}}}]}}',
                f"/item replace block 8 104 {z} container.0 with minecraft:bucket",
                f"/setblock 12 104 {z} create:item_drain",
                f"/setblock 13 104 {z} minecraft:smooth_stone",
                f"/item replace block 12 104 {z} container.0 with create:{fluid}_bucket",
                f"/data merge block 12 104 {z} {{HeldItem:{{Pos:0.0f,InDirection:5}}}}",
            ))
        start = world.clock()
        for tick in range(1, 45):
            world.step_to(start + tick)
        for z, fluid in ((-11, "honey"), (-8, "chocolate")):
            depot, spout, drain = world.commands((
                f"/data get block 8 104 {z}", f"/data get block 8 106 {z}",
                f"/data get block 12 104 {z}",
            ))
            assert f'id: "create:{fluid}"' in drain and "amount: 1000" in drain, drain
            assert 'id: "minecraft:bucket"' in drain, drain
            assert f'id: "create:{fluid}_bucket"' in depot, depot
            assert f'id: "create:{fluid}"' not in spout, spout
    print("Honey and Chocolate buckets fill and drain 1000 mB each.")


if __name__ == "__main__":
    main()
