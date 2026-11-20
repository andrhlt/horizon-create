#!/usr/bin/env python3
"""Replay Java wrench rotation and survival Controller Rail item exchanges."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

COORDINATE = re.compile(r"([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)d\b")


def rows(variant):
    with (ROOT / "fixtures" / f"controller-rail-{variant}-java.csv").open() as fixture:
        return list(csv.reader(fixture))[1:]


def sneak_click_at(control, position, aim):
    control.call("key", "shift", "down")
    control.call("wait", 4)
    try:
        control.call("look-at", *aim)
        control.call("wait", 1)
        looking = control.call("looking-at")
        hit = looking.get("block") or {}
        if looking.get("kind") != "block" or hit.get("pos") != list(position):
            raise RuntimeError(f"Controller Rail pickup aim missed {position}: {looking}")
        control.call("mouse", "right", "click")
        control.call("wait", 3)
    finally:
        control.call("key", "shift", "up")


def wrench(args):
    expected = rows("wrench")
    directions = {
        "west": (-1, 0), "east": (1, 0), "north": (0, -1), "south": (0, 1),
    }
    failures = []
    with fixture_world(args, "ControllerRailWrench", pack=args.pack) as control:
        control.call("tp", 20.5, 173, 28.5)
        control.call("wait", 4)
        control.commands((
            "/fill 5 170 22 35 170 32 minecraft:stone",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:wrench",
        ))
        control.call("wait", 3)
        control.call("select", "create:wrench")
        for index, (initial, supports, shape, backwards) in enumerate(expected):
            x, y, z = 7 + (index // 2) * 5, 171, 29 if supports == "true" else 24
            control.commands(
                f"/setblock {x+dx} {y} {z+dz} "
                + ("minecraft:stone" if supports == "true" or initial == f"ascending_{name}" else "minecraft:air")
                for name, (dx,dz) in directions.items()
            )
            state = f"create:controller_rail[shape={initial},backwards=true]"
            control.commands((f"/setblock {x} {y} {z} {state}", f"/setblock {x} {y} {z} {state}"))
            before = control.command(f"/execute if block {x} {y} {z} {state}")
            if "Test passed" not in before:
                actual = control.call("block", x, y, z)
                raise RuntimeError(f"Wrong pre-wrench state for row {index}: {actual}")
            control.call("tp", x + 0.5, y + 1.8, z + 1.5)
            control.call("look-at", x + 0.5, y + 0.1, z + 0.5)
            control.call("interact", x, y, z)
            wanted = f"create:controller_rail[shape={shape},backwards={backwards}]"
            after = control.command(f"/execute if block {x} {y} {z} {wanted}")
            if "Test passed" not in after:
                failures.append((initial, supports, wanted, control.call("block", x, y, z)))
    if failures:
        for failure in failures:
            print(failure)
        raise RuntimeError(f"{len(failures)} Controller Rail wrench cases differ from Java")
    print(f"All {len(expected)} Java Controller Rail wrench cases matched.")


def pickup(args):
    expected = rows("pickup")
    actual = []
    with fixture_world(args, "ControllerRailPickup", render=True, pack=args.pack) as control:
        control.call("tp", 17.5, 172, 26.5)
        control.call("wait", 5)
        control.commands((
            "/fill 12 170 22 24 170 29 minecraft:stone",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:wrench",
        ))
        control.call("wait", 3)
        control.call("select", "create:wrench")
        for index, (wet, _, _, _) in enumerate(expected):
            x, y, z = 15 + index * 5, 171, 25
            control.command("/clear @s create:controller_rail")
            control.command(f"/setblock {x} {y} {z} create:controller_rail[waterlogged={wet}]")
            control.call("tp", x + 0.5, y, z + 2.5)
            sneak_click_at(control, (x, y, z), (x + 0.5, y + 0.06, z + 0.5))
            block = control.call("block", x, y, z)
            source = "true" if block["state"] == "minecraft:water[level=0]" else "false"
            count = control.call("inventory")["counts"].get("create:controller_rail", 0)
            actual.append([wet, block["block"], source, str(count)])
    if expected != actual:
        raise RuntimeError(f"Controller Rail pickup differs: {expected}, {actual}")
    print(f"All {len(actual)} Java Controller Rail pickup cases matched, including retained source water.")


def reuse(args):
    expected = rows("reuse")
    names = {
        "place": "create:cart_assembler",
        "powered": "minecraft:powered_rail",
        "controller": "create:controller_rail",
    }
    failures = []
    with fixture_world(args, "ControllerRailCartReuse", pack=args.pack) as control:
        control.call("tp", 10.5, 173, 40.5)
        control.call("wait", 4)
        control.commands(("/fill 6 170 39 16 170 44 minecraft:stone", "/gamemode survival"))
        for rig, action, kind, backwards, shape, held, controller, powered in expected:
            x, y, z = 8 + int(rig) * 4, 171, 42
            if action == "place":
                rail = f"create:controller_rail[shape={shape},backwards={backwards}]"
                control.commands((
                    "/clear @s",
                    f"/setblock {x} {y} {z} {rail}",
                    f"/setblock {x} {y} {z} {rail}",
                    "/give @s create:cart_assembler 2",
                ))
                control.call("tp", x + 0.5, y + 1.6, z + 2.5)
                control.call("look-at", x + 0.5, y + 3.22, z + 4.5)
            elif action == "powered":
                control.command("/item replace entity @s hotbar.1 with minecraft:powered_rail")
            selected = names[action]
            control.call("wait", 3)
            control.call("select", selected)
            control.call("interact", x, y, z)
            after = f"create:cart_assembler[rail_type={kind},shape={shape},backwards={backwards},waterlogged=false]"
            observed, inventory = control.commands((
                f"/execute if block {x} {y} {z} {after}", "/data get entity @s Inventory",
            ))
            counts = {}
            for stack in re.findall(r"\{([^{}]*)\}", inventory):
                item = re.search(r'\bid: "([^"]+)"', stack)
                count = re.search(r"\bcount: (\d+)", stack)
                if item and count:
                    counts[item[1]] = counts.get(item[1], 0) + int(count[1])
            actual = (counts.get(selected, 0), counts.get(names["controller"], 0), counts.get(names["powered"], 0))
            if "Test passed" not in observed or actual != tuple(map(int, (held,controller,powered))):
                failures.append(((rig, action, kind, backwards, shape, held, controller, powered),
                                 control.call("block", x, y, z), actual))
    if failures:
        for failure in failures:
            print(failure)
        raise RuntimeError(f"{len(failures)} Controller Rail Cart Assembler reuse cases differ")
    print(f"All {len(expected)} Java Controller Rail reuse and item exchange actions matched.")


def departure(args):
    expected = rows("cart-direction")
    assert len(expected) == 18
    actual = []
    with fixture_world(args, "ControllerCartDirection", pack=args.pack) as control:
        control.call("tp", 16.5, 176, 26.5)
        control.call("wait", 5)
        control.command("/fill 7 173 22 21 173 32 minecraft:stone")
        for rig in range(2):
            z = 24 + rig * 5
            backwards = "true" if rig else "false"
            state = f"create:controller_rail[shape=east_west,backwards={backwards}]"
            control.commands((
                f"/fill 8 174 {z} 20 174 {z} minecraft:rail[shape=east_west]",
                f"/setblock 14 174 {z} {state}",
                f"/setblock 14 174 {z} {state}",
                "/item replace entity @s hotbar.0 with create:cart_assembler",
            ))
            control.call("tp", 16.5, 174, z+0.5)
            control.call("look-at", 14.5, 174.1, z+0.5)
            control.call("wait", 3)
            control.call("select", "create:cart_assembler")
            control.call("interact", 14, 174, z)
            control.commands((
                f"/setblock 14 175 {z} minecraft:polished_andesite",
                f"/setblock 14 174 {z-1} minecraft:redstone_block",
            ))
        control.call("tp", 16.5, 175, 26.5)
        for rig in range(2):
            control.command(f'/summon minecraft:minecart 14.5 174.0625 {24.5+rig*5} {{Tags:["direction_{rig}"]}}')
        baseline = control.clock()
        for tick in range(9):
            if tick:
                control.step_to(baseline + tick)
            for rig in range(2):
                selector = f"@e[type=minecraft:minecart,tag=direction_{rig},limit=1]"
                pos, motion = control.commands((f"/data get entity {selector} Pos", f"/data get entity {selector} Motion"))
                place = COORDINATE.findall(pos)
                velocity = COORDINATE.findall(motion)
                assert len(place) == len(velocity) == 3, (pos, motion)
                block = control.call("block", 14, 175, 24+rig*5)["block"]
                actual.append([str(tick),str(rig),float(place[0])-8,float(place[2])-24,float(velocity[0]),block])
    differences = []
    for want, got in zip(expected, actual, strict=True):
        if want[:2] != got[:2] or want[-1] != got[-1] or any(
                abs(float(a)-b) > 1e-6 for a,b in zip(want[2:5],got[2:5],strict=True)):
            differences.append((want,got))
    for difference in differences:
        print(difference)
    if differences:
        raise RuntimeError(f"{len(differences)} directed minecart samples differ")
    print(f"All {len(actual)} Java directed Cart Assembler rows matched tick for tick.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--assembler", action="store_true")
    args = parser.parse_args()
    if args.assembler:
        reuse(args)
        departure(args)
    else:
        wrench(args)
        pickup(args)
