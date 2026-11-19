#!/usr/bin/env python3
"""Exercise Factory Gauge floor and ceiling placement in a survival world."""
import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

mp = import_module("test-multiplayer")
placement = import_module("test-clipboard-placement")
GAUGE = "create:factory_gauge"
FREQ = "Freq: [I; 42, 123, -456, 789]"


def tune(world):
    world.commands(("/clear @s", f"/item replace entity @s hotbar.0 with {GAUGE}",
                    "/tp @s 10.5 170 22.5"))
    mp.until("the actor to hold an untuned gauge by the Stock Link", lambda:
             (world.call("inventory")["held"] or {}).get("item") == GAUGE and
             world.call("state")["player"]["position"] == [10.5, 170.0, 22.5])
    world.call("look-at", 10.5, 170.18, 24.5)
    mp.until("the Stock Link to be targeted", lambda:
             (world.call("looking-at").get("block") or {}).get("pos") == [10, 170, 24])
    world.call("wait", 4)
    world.call("mouse", "right", "click")
    world.call("wait", 4)
    selected = world.command("/data get entity @s SelectedItem")
    assert "create:factory_panel" in selected and FREQ in selected, selected


def run_case(world, name, support, face, point, target, facing, slot):
    tune(world)
    world.command("/tp @s 14.5 170 22.5")
    mp.until(f"the actor to approach the {name} support", lambda:
             world.call("state")["player"]["position"] == [14.5, 170.0, 22.5])
    world.call("look-at", *point)
    mp.until(f"the {name} support face to be targeted", lambda:
             placement.ray_hit(world, support, face))
    world.call("wait", 4)
    world.call("mouse", "right", "click")
    expected = f"{GAUGE}[face={name},facing={facing},powered=false,waterlogged=false]"
    try:
        mp.until(f"the {name} gauge state", lambda: world.call("block", *target)["state"] == expected)
    except RuntimeError as error:
        raise AssertionError((name, expected, world.call("block", *target),
                              world.command("/data get entity @s SelectedItem"),
                              world.call("looking-at"))) from error
    mp.until(f"the {name} gauge item to be consumed", lambda: mp.count(world, GAUGE) == 0)
    data = world.command("/data get block " + " ".join(map(str, target)))
    assert slot in data and FREQ in data, (name, slot, data)
    print(f"{name}: {expected}, {slot}, matching frequency, consumed item.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with fixture_world(args, "FactoryGaugeOrientation", render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        world.commands(("/fill 8 169 22 16 169 28 minecraft:stone",
                        "/setblock 10 170 24 create:stock_link[face=floor]",
                        f"/data merge block 10 170 24 {{{FREQ}}}",
                        "/setblock 14 173 24 minecraft:stone",
                        "/gamemode survival"))
        run_case(world, "floor", (14, 169, 24), "up", (14.25, 170.0, 24.25),
                 (14, 170, 24), "south", "top_left")
        run_case(world, "ceiling", (14, 173, 24), "down", (14.25, 173.0, 24.25),
                 (14, 172, 24), "north", "bottom_left")


if __name__ == "__main__":
    main()
