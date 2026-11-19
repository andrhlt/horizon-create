#!/usr/bin/env python3
"""Verify the original lava, honey bottle, and campfire bread recipe behaviors."""
import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")


def lava_and_honey(world):
    sources = ("cobblestone", "mossy_cobblestone", "infested_cobblestone", "cobbled_deepslate", "cobblestone")
    positions = [4 + 3 * index for index in range(len(sources))]
    for index, (x, source) in enumerate(zip(positions, sources, strict=True)):
        heat, fuel = ("kindled", 1) if index == len(sources) - 1 else ("seething", 2)
        replies = world.commands((
            f"/setblock {x - 1} 105 -11 create:creative_motor[facing=up]{{ScrollValue:256}}",
            f"/setblock {x - 1} 106 -11 create:cogwheel[axis=y]",
            f"/setblock {x} 106 -11 create:mechanical_mixer",
            f"/setblock {x} 104 -11 create:basin",
            f"/setblock {x} 103 -11 create:blaze_burner[blaze={heat}]{{fuelLevel:{fuel},burnTimeRemaining:1600}}",
            f"/item replace block {x} 104 -11 container.0 with minecraft:{source}",
        ))
        assert "Replaced" in replies[-1], replies
    world.commands((
        "/setblock 19 106 -11 create:spout",
        "/setblock 19 104 -11 create:depot",
        '/data merge block 19 106 -11 {Tanks:[{TankContent:{Fluid:{id:"create:honey",amount:500}}}]}',
        "/item replace block 19 104 -11 container.0 with minecraft:glass_bottle",
    ))
    tick = world.clock()
    for offset in range(1, 65):
        world.step_to(tick + offset)
    for index, x in enumerate(positions):
        basin = world.command(f"/data get block {x} 104 -11")
        if index < len(positions) - 1:
            assert 'amount: 50, id: "minecraft:lava"' in basin, basin
        else:
            assert 'id: "minecraft:cobblestone"' in basin and 'minecraft:lava' not in basin, basin
    depot = world.command("/data get block 19 104 -11 Items")
    spout = world.command("/data get block 19 106 -11")
    assert 'id: "minecraft:honey_bottle"' in depot and "amount: 250" in spout, (depot, spout)
    print("Four superheated cobblestone variants yielded 50 mB lava each; ordinary heat did not. Bottling used 250 mB honey.", flush=True)


def campfire(world):
    world.commands((
        "/fill 6 114 -14 14 114 -7 minecraft:stone",
        "/setblock 9 115 -11 minecraft:campfire[lit=true]",
        "/tp @s 9.5 115 -8.5 180 25",
        "/gamemode survival",
        "/item replace entity @s hotbar.0 with create:dough",
    ))
    world.call("wait", 4)
    world.call("interact", 9, 115, -11, "up")
    raw = world.command("/data get block 9 115 -11")
    assert 'id: "create:dough"' in raw and "600" in raw, raw
    tick = world.clock()
    assert "Stepping" in world.command("/tick step 599")
    mp.until("the cook to reach tick 599", lambda: world.clock() == tick + 599, seconds=45)
    raw = world.command("/data get block 9 115 -11")
    assert 'id: "create:dough"' in raw and "599" in raw, raw
    world.step_to(tick + 600)
    raw = world.command("/data get block 9 115 -11")
    assert 'id: "create:dough"' not in raw, raw
    nearby = world.call("entities")["entities"]
    assert any("minecraft:bread" in str(entity) for entity in nearby), nearby
    print("Survival Campfire Bread stayed raw through tick 599 and dropped at tick 600.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()
    with fixture_world(args, "ExtraMaterialRecipes", pack=args.pack, env={"HORIZON_NO_AUDIO": "1"}) as world:
        lava_and_honey(world)
        campfire(world)
