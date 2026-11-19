#!/usr/bin/env python3
"""Check Factory Gauge discovery as a Display Link source."""
import argparse
from importlib import import_module
from pathlib import Path
from fixture_world import fixture_world

mp = import_module("test-multiplayer")
GAUGE_SOURCE = "Factory gauge status"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with fixture_world(args, "FactoryGaugeDisplay", render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        world.commands(("/fill 8 169 20 16 169 27 minecraft:stone",
                        "/setblock 14 171 24 minecraft:stone",
                        "/setblock 14 171 23 create:factory_gauge[face=wall,facing=north]",
                        "/setblock 14 171 22 create:display_link[facing=north]",
                        "/setblock 13 171 22 create:nixie_tube",
                        "/data merge block 13 171 22 {CustomText:'{\"text\":\"old\"}'}",
                        "/data merge block 14 171 22 {TargetOffset:[I;-1,0,0],TargetLine:0}",
                        "/tp @s 14.5 170 20.5", "/clear @s"))
        before = world.command("/data get block 13 171 22 CustomText")
        assert "old" in before, before
        world.step_to(world.clock() + 1)
        world.call("look-at", 14.5, 171.5, 22.1)
        mp.until("the Display Link to be targeted", lambda:
                 (world.call("looking-at").get("block") or {}).get("pos") == [14, 171, 22])
        world.call("wait", 4)
        world.call("mouse", "right", "click")
        mp.until("the Display Link menu to open", lambda:
                 world.call("state").get("screen") == "container")
        world.call("wait", 3)
        screen = world.call("screen")
        assert any(button.get("label") == GAUGE_SOURCE for button in screen["buttons"]), screen
        world.call("click-button", GAUGE_SOURCE)
        world.call("wait", 3)
        data = world.command("/data get block 14 171 22")
        assert 'Id: "create:gauge_status"' in data, data
        target = world.command("/data get block 13 171 22 CustomText")
        assert "old" not in target and "text" in target, target
        print("Display Link selected Factory gauge status and cleared the target for its empty panel list.")


if __name__ == "__main__":
    main()
