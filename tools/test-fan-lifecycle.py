#!/usr/bin/env python3
"""Check Encased Fan survival placement, airflow, LAN collection, and save/reopen."""

import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
FAN = (5, 106, -7)
DEPOT = (7, 105, -7)
MOTOR = (4, 106, -7)
ITEM_SELECTOR = "@e[type=minecraft:item,limit=1]"


def advance(control, ticks):
    start = control.clock()
    for tick in range(1, ticks + 1):
        control.step_to(start + tick)


def setup(control):
    control.commands((
        "/fill 3 105 -9 9 105 -5 minecraft:smooth_stone",
        "/setblock 6 106 -7 minecraft:campfire[lit=true]",
        f"/setblock {' '.join(map(str, MOTOR))} create:creative_motor[facing=east]",
        f"/data merge block {' '.join(map(str, MOTOR))} {{ScrollValue:256}}",
        f"/setblock {' '.join(map(str, FAN))} create:encased_fan[facing=east]",
    ))


def input_depot(control):
    control.commands((
        f"/setblock {' '.join(map(str, DEPOT))} create:depot",
        "/setblock 6 105 -7 minecraft:stone",
        "/setblock 6 106 -8 minecraft:stone",
        "/setblock 6 106 -6 minecraft:stone",
    ))
    advance(control, 5)
    control.command(f"/item replace block {' '.join(map(str, DEPOT))} container.0 with minecraft:beef")


def run_survival(args):
    crafting = import_module("test-survival-crafting")
    fan = "create:encased_fan"
    ingredients = ("create:shaft", "create:andesite_casing", "create:propeller")
    with fixture_world(args, "FanSurvivalCraft", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 5 179 20 10 179 25 minecraft:smooth_stone",
            "/setblock 8 180 23 minecraft:crafting_table",
            "/setblock 8 180 24 minecraft:smooth_stone",
            "/tp @s 6.5 180 23.5",
            "/gamemode survival",
        ))
        control.commands(
            f"/item replace entity @s hotbar.{index} with {item}"
            for index, item in enumerate(ingredients)
        )
        control.call("wait", 3)
        control.call("interact", 8, 180, 23, "west")
        control.call("wait", 3)
        for index, slot in enumerate((101, 104, 107)):
            crafting.distribute(control, index, (slot,))
        crafting.craft(control, fan, 1)
        source = crafting.inventory_slot(control, fan)
        if source >= 9:
            control.call("click-slot", source)
            control.call("click-slot", 0)
        control.call("close")
        control.call("select", fan)
        control.call("look-at", 8, 181, 24.5)
        control.call("wait", 3)
        control.call("interact", 8, 180, 24, "west")
        actual = control.call("block", 7, 180, 24)["state"]
        counts = control.call("inventory")["counts"]
        if actual != f"{fan}[facing=west]" or any(counts.get(item, 0) for item in (*ingredients, fan)):
            raise RuntimeError(f"Survival craft and placement produced {actual} and left {counts}")

        for support, side, expected in (
            ("minecraft:smooth_stone", "create:shaft[axis=z]", "north"),
            ("create:smart_chute", "minecraft:air", "east"),
        ):
            control.commands((
                "/setblock 7 180 24 minecraft:air",
                f"/setblock 8 180 24 {support}",
                f"/setblock 7 180 25 {side}",
                f"/item replace entity @s hotbar.0 with {fan}",
            ))
            control.call("select", fan)
            control.call("wait", 3)
            control.call("interact", 8, 180, 24, "west")
            actual = control.call("block", 7, 180, 24)["state"]
            if actual != f"{fan}[facing={expected}]":
                raise RuntimeError(f"Expected facing={expected} with {support} and {side}, got {actual}")
    print("The Java recipe crafted one fan; survival placement aimed toward the player, away from a shaft, and toward a chute.")


def run_lan(args):
    world = "FanLifecycleLAN"
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, world, pack=args.pack))
        setup(host)
        input_depot(host)
        start = host.clock()
        advance(host, 160)
        end = host.clock()
        depot = host.command(f"/data get block {' '.join(map(str, DEPOT))} Items")
        if "minecraft:cooked_beef" not in depot:
            timer = host.command(f"/data get block {' '.join(map(str, DEPOT))} FanProcessingTime")
            fan = host.command(f"/data get block {' '.join(map(str, FAN))}")
            raise RuntimeError(f"Host did not see cooked fan output at {start}->{end}: {depot}; {timer}; {fan}")
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-fan-lan-")))
        guest_name = "FanGuest"
        guest = stack.enter_context(multiplayer.joined_client(
            args, scratch, f"127.0.0.1:{port}", guest_name,
            scenario="fan-lifecycle", pack=args.pack,
        ))
        multiplayer.until("the guest to see the fan Depot", lambda:
                          guest.call("block", *DEPOT)["block"] == "create:depot")
        multiplayer.until("the guest to join the LAN world", lambda: any(
            player["name"] == guest_name and player["placed"]
            for player in host.call("lan", "status")["guests"]
        ))
        host.command(f"/gamemode survival {guest_name}")
        host.command(f"/tp {guest_name} 7.5 106 -5.5")
        advance(host, 1)
        guest.call("interact", *DEPOT, "up")
        multiplayer.until("guest to collect cooked beef", lambda:
                          multiplayer.count(guest, "minecraft:cooked_beef") == 1)
        after = host.command(f"/data get block {' '.join(map(str, DEPOT))} Items")
        if after != "Found no elements matching Items" and not after.endswith("block data: []"):
            raise RuntimeError(f"Depot retained the output after guest collection: {after}")
    print("LAN fan processing produced one cooked beef; the guest collected it and the host Depot emptied.")


def item_position(control, selector=ITEM_SELECTOR, item_id="minecraft:beef"):
    item = control.command(f"/data get entity {selector}")
    position = re.search(r"Pos: \[(-?\d+(?:\.\d+)?)[dDfF]?, (-?\d+(?:\.\d+)?)[dDfF]?, (-?\d+(?:\.\d+)?)[dDfF]?\]", item)
    if position is None or item_id not in item:
        raise RuntimeError(f"Could not read the in-flight {item_id} item: {item}")
    return tuple(map(float, position.groups()))


def assert_item_count(control, expected_total):
    control.commands((
        "/scoreboard players set #fan_items fan_count 0",
        "/execute as @e[type=minecraft:item] run scoreboard players add #fan_items fan_count 1",
    ))
    count = control.command("/scoreboard players get #fan_items fan_count")
    total = re.search(r" has (\d+) \[", count)
    if total is None or total[1] != str(expected_total):
        raise RuntimeError(f"Expected {expected_total} dropped item(s), got {count}")


def run_airflow(args):
    with fixture_world(args, "FanAirflowBoundary", pack=args.pack) as control:
        control.command("/fill 3 105 -9 13 105 1 minecraft:smooth_stone")
        for z, speed in ((-7, 64), (-3, 64)):
            control.commands((
                f"/setblock 4 106 {z} create:creative_motor[facing=east]",
                f"/data merge block 4 106 {z} {{ScrollValue:{speed}}}",
                f"/setblock 5 106 {z} create:encased_fan[facing=east]",
            ))
        control.command("/setblock 7 106 -3 minecraft:stone")
        control.commands((
            "/setblock 6 106 -1 create:creative_motor[facing=west]",
            "/data merge block 6 106 -1 {ScrollValue:64}",
            "/setblock 5 106 -1 create:encased_fan[facing=west]",
        ))
        control.commands((
            "/setblock 4 106 -9 create:creative_motor[facing=east]",
            "/data merge block 4 106 -9 {ScrollValue:64}",
            "/setblock 5 106 -9 create:encased_fan[facing=east]",
            "/setblock 6 106 -9 minecraft:campfire[lit=true]",
        ))
        control.commands((
            "/setblock 3 106 1 create:creative_motor[facing=east]",
            "/data merge block 3 106 1 {ScrollValue:-64}",
            "/setblock 4 106 1 create:shaft[axis=x]",
            "/setblock 5 106 1 create:encased_fan[facing=east]",
        ))
        control.command("/scoreboard objectives add fan_count dummy")
        advance(control, 5)
        control.command('/summon minecraft:item 8.5 106.5 -6.5 '
                        '{Item:{id:"minecraft:stone",count:1},Motion:[0.0d,0.0d,0.0d],PickupDelay:32767s,Tags:["FanOpen"]}')
        control.command('/summon minecraft:item 8.5 106.5 -2.5 '
                        '{Item:{id:"minecraft:stone",count:1},Motion:[0.0d,0.0d,0.0d],PickupDelay:32767s,Tags:["FanBlocked"]}')
        control.command('/summon minecraft:item 3.5 106.5 -0.5 '
                        '{Item:{id:"minecraft:stone",count:1},Motion:[0.0d,0.0d,0.0d],PickupDelay:32767s,Tags:["FanReversed"]}')
        control.command('/summon minecraft:item 8.5 106.5 -8.5 '
                        '{Item:{id:"minecraft:stone",count:1},Motion:[0.0d,0.0d,0.0d],PickupDelay:32767s,Tags:["FanRejected"]}')
        control.command('/summon minecraft:item 6.5 106.5 1.5 '
                        '{Item:{id:"minecraft:stone",count:1},Motion:[0.0d,0.0d,0.0d],PickupDelay:32767s,Tags:["FanReverseRPM"]}')
        advance(control, 20)
        assert_item_count(control, 5)
        open_item = item_position(control, "@e[type=minecraft:item,tag=FanOpen,limit=1]", "minecraft:stone")
        blocked_item = item_position(control, "@e[type=minecraft:item,tag=FanBlocked,limit=1]", "minecraft:stone")
        reversed_item = item_position(control, "@e[type=minecraft:item,tag=FanReversed,limit=1]", "minecraft:stone")
        item_position(control, "@e[type=minecraft:item,tag=FanRejected,limit=1]", "minecraft:stone")
        if open_item[0] <= 8.6:
            raise RuntimeError(f"Unobstructed eastward airflow did not move the item: {open_item}")
        if blocked_item[0] > 8.55:
            raise RuntimeError(f"Airflow passed through the solid obstruction: {blocked_item}")
        if reversed_item[0] >= 3.4:
            raise RuntimeError(f"West-facing fan airflow did not reverse direction: {reversed_item}")
        reverse_rpm = control.command("/data get entity @e[type=minecraft:item,tag=FanReverseRPM,limit=1]")
        motion = re.search(r"Motion: \[(-?\d+(?:\.\d+)?)[dDfF]?,", reverse_rpm)
        if motion is None or float(motion[1]) >= 0:
            raise RuntimeError(f"Negative fan RPM did not pull the item toward the fan: {reverse_rpm}")
    print("Fan airflow moved east and west, reversed with negative RPM, stopped at a solid obstruction, and left unsupported stone unchanged in a smoking lane.")


def run_reopen(args):
    with fixture_world(args, "FanItemReopen", pack=args.pack) as control:
        setup(control)
        control.command("/setblock 9 106 -7 minecraft:stone")
        control.command(f"/data merge block {' '.join(map(str, MOTOR))} {{ScrollValue:0}}")
        control.command("/scoreboard objectives add fan_count dummy")
        control.command('/summon minecraft:item 6.5 106.5 -6.5 '
                        '{Item:{id:"minecraft:beef",count:1},Motion:[0.0d,0.0d,0.0d],PickupDelay:32767s}')
        advance(control, 1)
        assert_item_count(control, 1)
        before = item_position(control)
        fan = control.call("block", *FAN)["state"]
        if "facing=east" not in fan:
            raise RuntimeError(f"Fan facing was not saved before restart: {fan}")
        control.restart()
        assert_item_count(control, 1)
        after_load = item_position(control)
        loaded_fan = control.call("block", *FAN)["state"]
        if "facing=east" not in loaded_fan or after_load[::2] != before[::2] or abs(after_load[1] - before[1]) > 1:
            raise RuntimeError(f"Idle fan/item state changed across save and reopen: {loaded_fan}, {before} -> {after_load}")
        control.command(f"/data merge block {' '.join(map(str, MOTOR))} {{ScrollValue:64}}")
        advance(control, 1)
        assert_item_count(control, 1)
        active_before = item_position(control)
        control.restart()
        assert_item_count(control, 1)
        active_after_load = item_position(control)
        fan_data = control.command(f"/data get block {' '.join(map(str, FAN))}")
        motor_data = control.command(f"/data get block {' '.join(map(str, MOTOR))}")
        loaded_fan = control.call("block", *FAN)["state"]
        if "facing=east" not in loaded_fan:
            raise RuntimeError(f"Active fan facing changed across save and reopen: {loaded_fan}")
        # The restarted client can run game ticks before the harness freezes it.
        # The wall bounds valid travel during that interval.
        if not active_before[0] <= active_after_load[0] < 9 or active_after_load[2] != active_before[2]:
            raise RuntimeError(f"Active in-flight item changed across save and reopen: {active_before} -> {active_after_load}; fan={fan_data}; motor={motor_data}")
        advance(control, 10)
        assert_item_count(control, 1)
        after_ticks = item_position(control)
        if after_ticks[0] <= active_before[0] or "Speed: 64.0f" not in fan_data:
            raise RuntimeError(f"Powered airflow did not resume after active reopen: {active_before} -> {active_after_load} -> {after_ticks}; fan={fan_data}; motor={motor_data}")
    print("Idle and active save/reopen retained the fan facing and one in-flight beef item; powered airflow resumed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--survival", dest="run", action="store_const", const=run_survival)
    mode.add_argument("--lan", dest="run", action="store_const", const=run_lan)
    mode.add_argument("--reopen", dest="run", action="store_const", const=run_reopen)
    mode.add_argument("--airflow", dest="run", action="store_const", const=run_airflow)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
