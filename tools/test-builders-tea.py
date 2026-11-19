#!/usr/bin/env python3
"""Check Builder's Tea brewing, bottling and survival use."""
import argparse
import re
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

multiplayer = import_module("test-multiplayer")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with fixture_world(args, "BuildersTea", pack=args.pack) as world:
        world.commands((
            "/gamemode survival",
            "/setblock 4 105 -11 create:creative_motor[facing=up]",
            "/data merge block 4 105 -11 {ScrollValue:256}",
            "/setblock 4 106 -11 create:cogwheel[axis=y]",
            "/setblock 5 106 -11 create:mechanical_mixer",
            "/setblock 5 104 -11 create:basin",
            "/setblock 5 103 -11 create:blaze_burner[blaze=kindled]",
            "/data merge block 5 103 -11 {fuelLevel:1,burnTimeRemaining:1600}",
            '/data merge block 5 104 -11 {InputTanks:[{TankContent:{Fluid:{id:"minecraft:water",amount:250}}},'
            '{TankContent:{Fluid:{id:"minecraft:milk",amount:250}}}]}',
            "/item replace block 5 104 -11 container.0 with minecraft:oak_leaves",
        ))
        start = world.clock()
        for tick in range(1, 90):
            world.step_to(start + tick)
        basin = world.command("/data get block 5 104 -11")
        assert 'amount: 500, id: "create:tea"' in basin, basin
        world.commands((
            "/setblock 8 106 -11 create:spout",
            "/setblock 8 104 -11 create:depot",
            '/data merge block 8 106 -11 {Tanks:[{TankContent:{Fluid:{id:"create:tea",amount:500}}}]}',
            "/item replace block 8 104 -11 container.0 with minecraft:glass_bottle",
        ))
        start = world.clock()
        for tick in range(1, 45):
            world.step_to(start + tick)
        depot = world.command("/data get block 8 104 -11 Items")
        spout = world.command("/data get block 8 106 -11")
        assert 'id: "create:builders_tea"' in depot and "amount: 250" in spout, (depot, spout)
        world.command("/item replace entity @s hotbar.0 with create:builders_tea 1")
        world.call("select", 1)
        world.call("mouse", "right", "down")
        try:
            multiplayer.until("the tea to return a glass bottle", lambda:
                              world.call("inventory")["counts"].get("minecraft:glass_bottle") == 1)
        finally:
            world.call("mouse", "right", "up")
        inventory = world.call("inventory")["counts"]
        assert inventory.get("minecraft:glass_bottle") == 1 and not inventory.get("create:builders_tea"), inventory
        player = world.command("/data get entity @s")
        assert ('id: "minecraft:haste"' in player and "show_icon: 0b" in player
                and "show_particles: 0b" in player), player
        duration = int(re.search(r"active_effects: \[\{duration: (\d+)", player)[1])
        assert 3500 <= duration <= 3600, duration
        saturation = float(re.search(r"foodSaturationLevel: ([\d.]+)", player)[1])
        assert abs(saturation - 6.2) < .001, saturation
        print("Brewed 500 mB tea, bottled 250 mB, drank at full hunger, and returned a bottle. "
              "Haste was hidden and saturation increased by 1.2.")


if __name__ == "__main__":
    main()
