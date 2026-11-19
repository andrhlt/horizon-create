#!/usr/bin/env python3
"""Replay Java Controller Rail placement, power, recipe, and actual minecart motion."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

POWER = re.compile(r"\bpower=(\d+)\b")
LEVEL = re.compile(r"(?:data|signal): (\d+)\b")
NUMBER = re.compile(r"([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)d\b")
RAIL_Y = 174
POWER_LEVELS = (15, 7, 0, 15)


def reference(name):
    with (ROOT / "fixtures" / f"controller-rail-{name}-java.csv").open() as source:
        return list(csv.reader(source))[1:]


def placement_power(args):
    placement = reference("placement")
    signal = reference("power")
    with fixture_world(args, "ControllerRailPlacement", pack=args.pack) as control:
        control.commands((
            "/tp @s 32 172 28",
            "/fill 34 169 22 47 169 32 minecraft:stone",
            "/gamemode survival",
        ))
        control.call("wait", 5)
        failures = []
        for row in placement:
            yaw, scenario, shape, backwards, wet, power, count = row
            yaw_value = int(yaw)
            x, y, z = 35 + yaw_value // 30, 170, 24 + int(scenario) * 3
            if scenario == "1":
                control.command(f"/setblock {x} {y} {z} minecraft:water[level=0]")
            elif scenario == "2":
                control.commands((
                    f"/setblock {x+1} {y} {z} minecraft:stone",
                    f"/setblock {x+1} {y+1} {z} create:controller_rail[shape=east_west]",
                ))
            control.commands(("/clear @s create:controller_rail", "/give @s create:controller_rail 2"))
            px, pz = x + 0.5, z + 2.5
            control.call("tp", px, y + 1, pz)
            dx, dz = [(0, 1), (-1, 0), (0, -1), (1, 0)][yaw_value // 90]
            control.call("look-at", px + dx * 2, y + 2.62, pz + dz * 2)
            control.call("select", "create:controller_rail")
            control.call("interact", x, y-1, z, "up")
            state = f"create:controller_rail[shape={shape},backwards={backwards},waterlogged={wet},power={power}]"
            block, held = control.commands((
                f"/execute if block {x} {y} {z} {state}", "/data get entity @s SelectedItem",
            ))
            actual_count = re.search(r"\bcount: (\d+)", held)
            if "Test passed" not in block or not actual_count or actual_count[1] != count:
                failures.append((row, control.call("block", x, y, z), held))
        for failure in failures:
            print("Placement", failure)
    with fixture_world(args, "ControllerRailPower", pack=args.pack) as control:
        control.commands((
            "/tp @s 14 173 35",
            "/fill 7 169 36 21 169 39 minecraft:stone",
            "/fill 8 170 38 20 170 38 create:controller_rail[shape=east_west]",
        ))
        control.call("wait", 5)
        actual = []
        start = control.clock()
        for index in range(len(signal)):
            if index:
                control.step_to(start + index)
            blocks = control.call("script", script="".join(f"block {x} 170 38\n" for x in range(8, 21)))
            states = [re.search(r"\bpower=(\d+)", state["state"]) for state in blocks]
            actual.append([str(index), *[power[1] if power else "absent" for power in states]])
            if index == 0:
                control.command("/setblock 8 170 37 minecraft:redstone_block")
            elif index == 4:
                control.command("/setblock 20 170 37 minecraft:redstone_block")
            elif index == 8:
                control.command("/setblock 8 170 37 minecraft:air")
            elif index == 12:
                control.command("/setblock 20 170 37 minecraft:air")
    power_failures = [(want, got) for want, got in zip(signal, actual, strict=True) if want != got]
    for failure in power_failures:
        print("Signal", failure)
    assert not failures and not power_failures, (len(failures), len(power_failures))
    print(f"All {len(placement)} placement and {len(signal) * 13} signal samples matched Java.")


def gradient(args):
    expected = reference("gradient")
    assert len(expected) == 35
    actual = []
    with fixture_world(args, "ControllerRailGradient", pack=args.pack) as control:
        control.call("tp", 20.5, 172, 36.5)
        control.call("wait", 4)
        control.commands((
            "/fill 7 169 35 24 169 42 minecraft:stone",
            "/setblock 20 170 37 create:analog_lever[face=floor,facing=north]",
            "/fill 8 170 38 20 170 38 create:controller_rail[shape=east_west]",
            "/setblock 14 170 39 minecraft:comparator[facing=north]",
        ))
        baseline = control.clock()
        script = "".join(f"block {x} 170 38\n" for x in range(8, 21))
        script += 'command "/data get block 14 170 39 OutputSignal"'
        for tick in range(35):
            if tick:
                control.step_to(baseline + tick)
            *blocks, data = control.call("script", script=script)
            observations = [POWER.search(block["state"]) for block in blocks]
            match = LEVEL.search(data["chat"][-1])
            row = [
                str(tick),
                *[hit[1] if hit else "absent" for hit in observations],
                match[1] if match else data["chat"][-1],
            ]
            actual.append(row)
            if tick == 0:
                control.command("/setblock 8 170 37 minecraft:redstone_block")
            elif tick == 4:
                control.call("tp", 20.5, 170, 39.5)
                control.call("look-at", 20.5, 170.1, 37.5)
                control.call("wait", 3)
                for _ in range(7):
                    control.call("interact", 20, 170, 37)
                if control.clock() != baseline + tick:
                    raise RuntimeError("Analog Lever interaction advanced the frozen tick")
            elif tick == 24:
                control.command("/setblock 8 170 37 minecraft:air")
            elif tick == 28:
                control.command("/setblock 20 170 37 minecraft:air")
    failures = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
    if failures:
        for pair in failures[:25]:
            print(pair)
        raise RuntimeError(f"{len(failures)} Controller Rail gradient ticks differ from Java")
    print(f"All {len(actual) * 14} Java rail power and comparator samples matched tick for tick.")


def motion(args):
    expected = reference("motion")
    assert len(expected) == 52
    actual = []
    with fixture_world(args, "ControllerRailMotion", pack=args.pack) as control:
        control.commands((
            "/tp @s 15.5 176 34.5",
            "/fill 7 173 22 21 173 44 minecraft:stone",
        ))
        control.call("wait", 5)
        for rig, power in enumerate(POWER_LEVELS):
            z = 24 + rig * 3
            for x in (8, 20):
                if power == 15:
                    control.command(f"/setblock {x} {RAIL_Y} {z-1} minecraft:redstone_block")
                elif power == 7:
                    control.commands((
                        f"/setblock {x} {RAIL_Y} {z-1} create:analog_lever[face=floor,facing=north]",
                        f"/data merge block {x} {RAIL_Y} {z-1} {{State:7,ChangeTimer:0}}",
                    ))
            control.command(f"/fill 8 {RAIL_Y} {z} 20 {RAIL_Y} {z} create:controller_rail[shape=east_west,backwards=true]")
            result = control.command(f"/execute if block 12 {RAIL_Y} {z} create:controller_rail[power={power}]")
            if "Test passed" not in result:
                raise RuntimeError(f"Expected original signal power {power} for cart {rig}: {result}")
        for rig, _ in enumerate(POWER_LEVELS):
            x, z = 12.15 if rig == 2 else 12.5, 24.5 + rig * 3
            speed = -0.18 if rig == 3 else 0.0
            control.command(
                f'/summon minecraft:minecart {x} 174.0625 {z} {{Motion:[{speed}d,0.0d,0.0d],Tags:["controller_{rig}"]}}'
            )
        baseline = control.clock()
        for tick in range(13):
            if tick:
                control.step_to(baseline + tick)
            for rig in range(4):
                selector = f"@e[type=minecraft:minecart,tag=controller_{rig},limit=1]"
                pos, motion = control.commands((
                    f"/data get entity {selector} Pos", f"/data get entity {selector} Motion",
                ))
                position = NUMBER.findall(pos)
                velocity = NUMBER.findall(motion)
                assert len(position) == len(velocity) == 3, (pos, motion)
                x, y, z = (int(float(coordinate)) for coordinate in position)
                power = POWER.search(control.call("block", x, y, z)["state"])
                actual.append([str(tick), str(rig), *position, velocity[0], power[1] if power else "absent"])
    diffs = []
    for want, got in zip(expected, actual, strict=True):
        if want[:2] != got[:2] or want[-1] != got[-1] or any(
                abs(float(a) - float(b)) > 1e-6 for a, b in zip(want[2:6], got[2:6], strict=True)):
            diffs.append((want, got))
    if diffs:
        for difference in diffs[:25]:
            print(difference)
        raise RuntimeError(f"{len(diffs)} minecart rows differ from Java")
    print(f"All {len(actual)} Java Controller Rail minecart rows matched tick for tick.")


def craft(args):
    crafting = import_module("test-survival-crafting")
    with fixture_world(args, "ControllerRailRecipe", render=True, pack=args.pack) as control:
        control.commands((
            "/tp @s 11.5 170 26.5",
            "/fill 8 169 22 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with minecraft:gold_ingot 6",
            "/item replace entity @s hotbar.1 with minecraft:stick",
            "/item replace entity @s hotbar.2 with create:electron_tube",
        ))
        control.call("wait", 5)
        control.call("tp", 12.5, 170, 26.5)
        control.call("interact", 12, 170, 24, "up")
        for item, slots in (
            ("minecraft:gold_ingot", (100, 102, 103, 105, 106, 108)),
            ("minecraft:stick", (104,)),
            ("create:electron_tube", (107,)),
        ):
            crafting.distribute(control, crafting.inventory_slot(control, item), slots)
        crafting.craft(control, "create:controller_rail", 6)
        counts = control.call("inventory")["counts"]
        assert not any(counts.get(item, 0) for item in
                       ("minecraft:gold_ingot", "minecraft:stick", "create:electron_tube")), counts
    print("The original survival recipe crafted six Controller Rails and consumed all eight inputs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--gradient", dest="test", action="store_const", const=gradient)
    group.add_argument("--motion", dest="test", action="store_const", const=motion)
    group.add_argument("--craft", dest="test", action="store_const", const=craft)
    parser.set_defaults(test=placement_power)
    args = parser.parse_args()
    args.test(args)
