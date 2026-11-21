#!/usr/bin/env python3
"""Craft, tune, and clear the original Factory Gauge item in survival."""

import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

crafting = import_module("test-survival-crafting")
machine = import_module("test-machine-crafting")
mp = import_module("test-multiplayer")
placement = import_module("test-clipboard-placement")
GAUGE = "create:factory_gauge"
FREQUENCY = "Freq: [I; 42, 123, -456, 789]"
SECOND_FREQUENCY = "Freq: [I; 43, 234, -567, 890]"


def aim_at_wall(world):
    world.command("/tp @s 14.5 170 22.5")
    mp.until("the actor to approach the gauge support", lambda:
             world.call("state")["player"]["position"] == [14.5, 170.0, 22.5])
    world.call("look-at", 14.25, 171.25, 24.0)
    mp.until("the ray to hit the north face of the gauge support", lambda:
             placement.ray_hit(world, (14, 171, 24), "north"))
    world.call("wait", 4)


def check_untuned_placement(world):
    world.command("/setblock 14 171 24 minecraft:stone")
    world.command("/setblock 14 171 23 minecraft:air")
    aim_at_wall(world)
    world.call("mouse", "right", "click")
    world.call("wait", 4)
    assert world.call("block", 14, 171, 23)["state"] == "minecraft:air"
    mp.until("the rejected Gauge to synchronize back to the inventory", lambda:
             mp.count(world, GAUGE) == 1)
    world.call("select", GAUGE)
    held = world.call("inventory")["held"] or {}
    assert held.get("item") == GAUGE and held.get("count") == 1, held
    server_inventory = world.command("/data get entity @s Inventory")
    assert GAUGE in server_inventory, server_inventory
    print("An untuned Factory Gauge could not be placed and was retained.")


def check_tuned_placement(world, screenshot):
    aim_at_wall(world)
    world.call("mouse", "right", "click")
    target = (14, 171, 23)
    try:
        mp.until("the tuned Factory Gauge to be placed on the north wall", lambda:
                 world.call("block", *target)["state"] ==
                 "create:factory_gauge[face=wall,facing=north,powered=false,waterlogged=false]")
    except RuntimeError as error:
        raise AssertionError((world.call("block", *target), world.call("looking-at"),
                              world.call("inventory"), world.command("/data get entity @s Inventory"))) from error
    mp.until("the placed Factory Gauge to consume its item", lambda:
             mp.count(world, GAUGE) == 0)
    data = world.command("/data get block 14 171 23")
    assert "bottom_right" in data and FREQUENCY in data, data
    if screenshot:
        world.call("look-at", 14.25, 171.25, 23.875)
        world.call("wait", 4)
        world.call("screenshot", screenshot)
    print("A tuned Factory Gauge retained its Stock Link frequency in the selected wall slot and was consumed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--recipes-only", action="store_true")
    parser.add_argument("--placement", action="store_true")
    parser.add_argument("--panels", action="store_true", help="also place and retry an additional panel")
    parser.add_argument("--filter", action="store_true", help="set a panel filter with a held item")
    parser.add_argument("--connection", action="store_true", help="connect the configured panel to a Display Link")
    parser.add_argument("--stock-display", action="store_true", help="display real linked network stock")
    parser.add_argument("--reopen", action="store_true", help="verify configured panel and stock display after an idle save/reopen")
    parser.add_argument("--support-removal", action="store_true", help="check multi-panel support loss and drops")
    parser.add_argument("--panel-break", action="store_true", help="check survival removal of one panel")
    parser.add_argument("--placement-screenshot", type=Path)
    args = parser.parse_args()
    if args.reopen:
        args.stock_display = True
    if args.stock_display:
        args.connection = True
    if args.connection:
        args.filter = True
    if args.support_removal or args.panel_break:
        args.panels = True
    if args.panels or args.filter:
        args.placement = True

    with fixture_world(args, "FactoryGaugeItem", render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        world.commands((
            "/fill 8 169 22 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
            "/gamemode survival",
        ))
        machine.replay(world, {
            "recipe": "crafting/logistics/factory_gauge", "width": "2",
            "slots": "create:stock_link,create:precision_mechanism",
            "output": GAUGE, "count": "2", "remainder": "",
        })
        if args.recipes_only:
            machine.replay(world, {
                "recipe": "crafting/logistics/factory_gauge_clear", "width": "1",
                "slots": GAUGE, "output": GAUGE, "count": "1", "remainder": "",
            })
            print("Both original Factory Gauge recipes passed in the survival crafting grid.")
            return
        world.commands((
            "/clear @s",
            "/setblock 10 170 24 create:stock_link[face=floor]",
            f"/data merge block 10 170 24 {{{FREQUENCY}}}",
            f"/item replace entity @s hotbar.0 with {GAUGE}",
        ))
        mp.until("the actor to hold the Factory Gauge", lambda:
                 (world.call("inventory")["held"] or {}).get("item") == GAUGE)
        if args.placement:
            check_untuned_placement(world)
        world.command("/tp @s 10.5 170 22.5")
        mp.until("the actor to stand near the Stock Link", lambda:
                 world.call("state")["player"]["position"] == [10.5, 170.0, 22.5])
        world.call("look-at", 10.5, 170.18, 24.5)
        mp.until("the ray to hit the Stock Link", lambda:
                 (world.call("looking-at").get("block") or {}).get("pos") == [10, 170, 24])
        world.call("wait", 4)
        world.call("mouse", "right", "click")
        world.call("wait", 4)
        tuned = world.command("/data get entity @s SelectedItem")
        assert "create:factory_panel" in tuned and FREQUENCY in tuned, (
            tuned, world.call("inventory")["held"], world.call("looking-at"),
            world.command("/data get block 10 170 24"),
        )

        if args.placement:
            check_tuned_placement(world, args.placement_screenshot)
            if args.filter:
                world.command("/item replace entity @s hotbar.0 with minecraft:iron_ingot 5")
                world.call("select", "minecraft:iron_ingot")
                world.call("look-at", 14.25, 171.25, 23.875)
                mp.until("the actor to target the lower panel", lambda:
                         placement.ray_hit(world, (14, 171, 23), "north"))
                world.call("wait", 4)
                world.call("mouse", "right", "click")
                world.call("wait", 4)
                data = world.command("/data get block 14 171 23 bottom_right")
                assert "Filter" in data and "minecraft:iron_ingot" in data, data
                assert mp.count(world, "minecraft:iron_ingot") == 5
                print("The lower panel copied the held iron filter without consuming it.")
                if args.connection:
                    world.commands(("/setblock 13 171 24 minecraft:stone",
                                    "/setblock 13 171 23 create:display_link[facing=north]",
                                    "/item replace entity @s hotbar.1 with minecraft:air"))
                    world.call("key", "2", "tap")
                    world.call("look-at", 14.25, 171.25, 23.875)
                    world.call("wait", 4)
                    world.call("mouse", "right", "click")
                    mp.until("the configured Factory Panel screen", lambda:
                             any(button.get("label") == "Add new connection"
                                 for button in world.call("screen").get("buttons", [])))
                    world.call("click-button", "Add new connection")
                    mp.until("the panel screen to close for connection selection", lambda:
                             world.call("state")["screen"] == "playing")
                    world.call("look-at", 13.5, 171.5, 23.875)
                    mp.until("the Display Link to be targeted", lambda:
                             (world.call("looking-at").get("block") or {}).get("pos") == [13, 171, 23])
                    world.call("mouse", "right", "click")
                    def linked_gauge():
                        data = world.command("/data get block 13 171 23 LinkedGauges")
                        return data if "bottom_right" in data and "14, 171, 23" in data else None
                    linked = mp.until("the panel connection to synchronize", linked_gauge)
                    assert "bottom_right" in linked and "14, 171, 23" in linked, (
                        linked, world.call("state"), world.call("looking-at"),
                        world.command("/data get block 13 171 23"),
                        world.command("/data get block 14 171 23"))
                    print("The configured panel connected to the Display Link.")
                    if args.stock_display:
                        world.commands(("/setblock 17 170 24 minecraft:barrel",
                                        "/setblock 18 170 24 create:packager[facing=east]",
                                        "/setblock 18 171 24 create:stock_link[face=floor]",
                                        f"/data merge block 18 171 24 {{{FREQUENCY}}}",
                                        "/item replace block 17 170 24 container.0 with minecraft:iron_ingot 12",
                                        "/setblock 13 172 23 create:nixie_tube",
                                        "/data merge block 13 171 23 {TargetOffset:[I;0,1,0],TargetLine:0}"))
                        world.step_to(world.clock() + 1)
                        world.call("look-at", 13.5, 171.5, 23.875)
                        world.call("wait", 4)
                        world.call("mouse", "right", "click")
                        mp.until("the linked Gauge source option", lambda:
                                 any(b.get("label") == "Factory gauge status" for b in world.call("screen").get("buttons", [])))
                        world.call("click-button", "Factory gauge status")
                        def displayed():
                            text = world.command("/data get block 13 172 23 CustomText")
                            return text if "12" in text and "Iron Ingot" in text else None
                        text = mp.until("the Display Link to publish the network's twelve iron ingots", displayed)
                        print(f"Linked Gauge published stock to the Nixie: {text}")
                        world.call("close")
                    if args.reopen:
                        world.call("save")
                        world.restart()
                        panel = world.command("/data get block 14 171 23 bottom_right")
                        assert all(value in panel for value in ("minecraft:iron_ingot", FREQUENCY)), panel
                        linked = world.command("/data get block 13 171 23 LinkedGauges")
                        assert "bottom_right" in linked and "14, 171, 23" in linked, linked
                        world.step_to(world.clock() + 1)
                        output = world.command("/data get block 13 172 23 CustomText")
                        assert "12" in output and "Iron Ingot" in output, output
                        print("Idle save/reopen retained the filtered panel and Display Link connection, and republished twelve stocked ingots.")
                    world.call("key", "1", "tap")
            next_frequency = SECOND_FREQUENCY if args.panels else FREQUENCY
            world.command(f"/data merge block 10 170 24 {{{next_frequency}}}")
            world.command(f"/item replace entity @s hotbar.0 with {GAUGE} {2 if args.panels else 1}")
            world.command("/tp @s 10.5 170 22.5")
            mp.until("the actor to return to the Stock Link", lambda:
                     world.call("state")["player"]["position"] == [10.5, 170.0, 22.5])
            world.call("look-at", 10.5, 170.18, 24.5)
            mp.until("the ray to find the Stock Link again", lambda:
                     (world.call("looking-at").get("block") or {}).get("pos") == [10, 170, 24])
            world.call("wait", 4)
            world.call("mouse", "right", "click")
            world.call("wait", 4)
            assert next_frequency in world.command("/data get entity @s SelectedItem")
            if args.panels:
                world.command("/tp @s 14.5 170 22.5")
                mp.until("the actor to return to the panel", lambda:
                         world.call("state")["player"]["position"] == [14.5, 170.0, 22.5])
                world.call("look-at", 14.25, 171.75, 23.875)
                mp.until("the ray to hit the upper quadrant of the gauge", lambda:
                         placement.ray_hit(world, (14, 171, 23), "north"))
                world.call("wait", 4)
                world.call("mouse", "right", "click")
                mp.until("the new panel to consume one gauge", lambda: mp.count(world, GAUGE) == 1)
                data = world.command("/data get block 14 171 23")
                assert all(value in data for value in ("bottom_right", "top_right", FREQUENCY, SECOND_FREQUENCY)), data
                world.call("wait", 4)
                world.call("mouse", "right", "click")
                world.call("wait", 4)
                mp.until("the gauge rejected from the occupied slot to remain in inventory", lambda:
                         mp.count(world, GAUGE) == 1)
                again = world.command("/data get block 14 171 23")
                assert again == data, (data, again)
                retained = world.command("/data get entity @s SelectedItem")
                assert GAUGE in retained and SECOND_FREQUENCY in retained, retained
                if args.placement_screenshot:
                    world.call("screenshot", args.placement_screenshot)
                print("A second tuned panel occupied another quadrant; retrying it retained the item.")

        world.command("/tp @s 12.5 170 26.5")
        world.call("wait", 3)
        world.call("interact", 12, 170, 24, "up")
        crafting.distribute(world, crafting.inventory_slot(world, GAUGE), (100,))
        crafting.craft(world, GAUGE, 1)
        world.call("close")
        world.call("wait", 3)
        cleared = world.command("/data get entity @s Inventory")
        assert GAUGE in cleared and "block_entity_data" not in cleared, cleared
        if args.panel_break:
            world.command("/item replace entity @s hotbar.1 with minecraft:netherite_pickaxe")
            world.call("select", "minecraft:netherite_pickaxe")
            world.command("/tp @s 14.5 170 22.5")
            world.call("look-at", 14.25, 171.75, 23.875)
            mp.until("the actor to aim at the upper panel", lambda:
                     placement.ray_hit(world, (14, 171, 23), "north"))
            world.call("mouse", "left", "down")
            try:
                for _ in range(100):
                    world.step_to(world.clock() + 1)
                    if world.call("block", 14, 171, 23)["state"] == "minecraft:air":
                        raise AssertionError("Mining one panel destroyed the entire multi-panel gauge")
                    data = world.command("/data get block 14 171 23")
                    if "top_right" not in data:
                        break
                else:
                    raise AssertionError("Mining did not remove the selected panel")
            finally:
                world.call("mouse", "left", "up")
            assert "bottom_right" in data and FREQUENCY in data and SECOND_FREQUENCY not in data, data
            def available_gauges():
                dropped = sum(e["item"]["count"] for e in world.call("entities", 12, "minecraft:item")["entities"]
                              if e.get("item", {}).get("item") == GAUGE)
                return dropped + mp.count(world, GAUGE)
            mp.until("the mined panel to drop one Gauge", lambda: available_gauges() == 2)
            print("Mining the upper panel dropped one Gauge and preserved the lower panel.")
        if args.support_removal:
            world.command("/tp @s 10.5 170 26.5")
            world.command("/setblock 14 171 24 minecraft:air")
            world.call("wait", 4)
            mp.until("the unsupported gauge to disappear", lambda:
                     world.call("block", 14, 171, 23)["state"] == "minecraft:air")
            def gauge_drops():
                return sum(e["item"]["count"] for e in world.call("entities", 12, "minecraft:item")["entities"]
                           if e.get("item", {}).get("item") == GAUGE)
            mp.until("both unsupported panels to drop", lambda: gauge_drops() == 2)
            print("Removing the support dropped both occupied panels.")

    print("Crafted two Factory Gauges, tuned one to the Stock Link, and cleared it with the original recipe.")


if __name__ == "__main__":
    main()
