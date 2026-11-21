#!/usr/bin/env python3
"""Exercise Mechanical Crafter survival actions, recovery and world reopen."""

import argparse
from collections import Counter
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

crafting = import_module("test-survival-crafting")
mechanical = import_module("test-mechanical-tools-crafting")
multiplayer = import_module("test-multiplayer")
CRAFTER = "create:mechanical_crafter"
COVER = "create:crafter_slot_cover"
CANNON = "create:potato_cannon"
WRENCH = "create:wrench"
STICK = "minecraft:stick"
GUEST = "CrafterGuest"

FRONT = (8, 105, -12)
ABOVE = (8, 106, -12)
TABLE = (11, 105, -12)
PLAYER = (10.5, 105, -11.5)
OUTLET = (5, 105, -9)
BARREL = (5, 104, -9)
MOTOR = (5, 106, -10)
INLET = (5, 106, -9)
LEAF = (9, 106, -9)
COVERED = (7, 105, -9)
PATTERN, ARROWS, INGREDIENTS = mechanical.RECIPES["potato_cannon"]
SLOTS = {
    (5 + col, mechanical.TOP - row, mechanical.Z): INGREDIENTS[key]
    for row, line in enumerate(PATTERN)
    for col, key in enumerate(line)
    if key != " "
}


def coords(pos):
    return " ".join(map(str, pos))


def state(world, pos):
    return world.call("block", *pos)["state"]


def assert_pose(world, pos, front, pointing):
    actual = state(world, pos)
    assert actual.startswith(CRAFTER) and f"facing={front}" in actual and f"pointing={pointing}" in actual, actual


def tags(world, pos, path=""):
    return world.command(f"/data get block {coords(pos)} {path}".rstrip())


def contents(world, pos, path="Items"):
    raw = tags(world, pos, path)
    stacks = Counter()
    for entry in re.findall(r"\{[^{}]*\}", raw):
        item = re.search(r'\bid: "([^"]+)"', entry)
        count = re.search(r"\bcount: (\d+)", entry)
        if item and count:
            stacks[item[1]] += int(count[1])
    return stacks


def phase(world, pos):
    raw = tags(world, pos, "Phase")
    match = re.search(r'"([A-Z]+)"', raw)
    assert match, raw
    return match[1]


def click(world, pos, face):
    world.call("interact", *pos, face)
    world.call("wait", 3)


def steps(world, amount):
    target = world.clock() + amount
    world.command(f"/tick step {amount}")
    multiplayer.until(f"world tick {target}", lambda: world.clock() >= target)
    assert world.clock() == target, (world.clock(), target)


def inventory(world, item):
    return world.call("inventory")["counts"].get(item, 0)


def build_platform(world):
    world.commands((
        "/fill 4 104 -15 13 104 -10 minecraft:smooth_stone",
        "/fill 4 105 -15 13 108 -10 minecraft:air",
        f"/tp @s {coords(PLAYER)}",
    ))


def survival(args):
    with fixture_world(args, "CrafterSurvival", render=True, pack=args.pack) as world:
        build_platform(world)
        world.commands((
            f"/setblock {coords(TABLE)} minecraft:crafting_table",
            "/setblock 7 105 -12 minecraft:smooth_stone",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:electron_tube",
            "/item replace entity @s hotbar.1 with create:brass_casing",
            "/item replace entity @s hotbar.2 with minecraft:crafting_table",
        ))
        click(world, TABLE, "west")
        for source, target in enumerate((100, 103, 106)):
            crafting.distribute(world, source, (target,))
        crafting.craft(world, CRAFTER, 3)
        slot = crafting.inventory_slot(world, CRAFTER)
        if slot >= 9:
            world.call("click-slot", slot)
            world.call("click-slot", 0)
        world.call("close")
        world.call("select", CRAFTER)
        world.command(f"/tp @s {coords(PLAYER)} 90 0")
        world.call("wait", 3)
        click(world, (7, 105, -12), "east")
        assert_pose(world, FRONT, "east", "up")
        world.command("/tp @s 8.5 105 -13.5 0 0")
        world.call("wait", 3)
        click(world, FRONT, "up")
        assert_pose(world, ABOVE, "east", "down")
        assert inventory(world, CRAFTER) == 1

        world.command(f"/tp @s {coords(PLAYER)}")
        world.command(f"/item replace entity @s hotbar.0 with {WRENCH}")
        world.call("select", WRENCH)
        click(world, FRONT, "east")
        assert_pose(world, FRONT, "east", "left")

        world.command(f"/item replace entity @s hotbar.0 with {STICK} 2")
        click(world, FRONT, "east")
        assert contents(world, FRONT) == {STICK: 1}, tags(world, FRONT)
        assert inventory(world, STICK) == 1
        world.command("/item replace entity @s hotbar.0 with minecraft:air")
        click(world, FRONT, "east")
        assert not contents(world, FRONT), tags(world, FRONT)
        assert inventory(world, STICK) == 1


def lan(args):
    with TemporaryDirectory(prefix="hc-crafter-lan-") as scratch:
        with fixture_world(args, "CrafterLAN", pack=args.pack) as host:
            build_platform(host)
            host.command(f"/setblock {coords(FRONT)} {CRAFTER}[facing=east,pointing=up]")
            host.command("/tp @s 12.5 105 -13.5")
            steps(host, 1)
            network = host.call("lan", "open", "0", "commands", "force")
            address = f"127.0.0.1:{network['port']}"
            with multiplayer.joined_client(
                args, Path(scratch), address, GUEST, render=True, scenario="crafter-lan", pack=args.pack,
            ) as guest:
                multiplayer.until("guest placement", lambda: any(
                    player["name"] == GUEST and player["placed"]
                    for player in host.call("lan", "status")["guests"]
                ))
                host.commands((
                    f"/gamemode survival {GUEST}",
                    f"/tp {GUEST} {coords(PLAYER)}",
                    f"/item replace entity {GUEST} hotbar.0 with {WRENCH}",
                ))
                multiplayer.until("guest sees crafter and wrench", lambda: (
                    state(guest, FRONT).startswith(CRAFTER) and inventory(guest, WRENCH) == 1
                    and guest.call("state")["player"]["position"] == list(PLAYER)
                ))
                guest.call("select", WRENCH)
                guest.call("wait", 3)
                click(guest, FRONT, "east")
                multiplayer.until("guest arrow change on host", lambda: "pointing=left" in state(host, FRONT))
                multiplayer.until("guest receives arrow change", lambda: "pointing=left" in state(guest, FRONT))

                host.command(f"/item replace entity {GUEST} hotbar.0 with {STICK} 2")
                multiplayer.until("guest receives ingredients", lambda: inventory(guest, STICK) == 2)
                guest.call("select", STICK)
                guest.call("wait", 3)
                click(guest, FRONT, "east")
                multiplayer.until("host receives exactly one ingredient", lambda: contents(host, FRONT) == {STICK: 1})
                multiplayer.until("guest inventory converges", lambda: inventory(guest, STICK) == 1)


def setup_process(world, wrong=False):
    commands = [
        "/fill 4 103 -11 10 103 -5 minecraft:smooth_stone",
        "/fill 4 104 -11 10 108 -5 minecraft:air",
        "/tp @s 5.5 104 -6.5",
        f"/setblock {coords(BARREL)} minecraft:barrel",
        f"/setblock {coords(MOTOR)} create:creative_motor[facing=south]{{ScrollValue:128}}",
    ]
    for pos, item in SLOTS.items():
        row, col = mechanical.TOP - pos[1], pos[0] - 5
        pointing = mechanical.POINTING[ARROWS[row][col]]
        commands.append(f"/setblock {coords(pos)} {CRAFTER}[facing=south,pointing={pointing}]")
        if pos != INLET:
            commands.append(f"/item replace block {coords(pos)} container.0 with {item}")
    commands.extend((
        f"/setblock {coords(COVERED)} {CRAFTER}[facing=south,pointing=left]",
        "/gamemode survival",
        f"/item replace entity @s hotbar.0 with {STICK if wrong else SLOTS[INLET]}",
        f"/item replace entity @s hotbar.1 with {COVER}",
    ))
    world.commands(commands)
    steps(world, 25)
    assert phase(world, INLET) == "IDLE" and not contents(world, BARREL)


def install_cover(world):
    world.call("select", COVER)
    click(world, COVERED, "south")
    assert "Cover: 1b" in tags(world, COVERED), tags(world, COVERED)
    assert inventory(world, COVER) == 0


def processing(args):
    with fixture_world(args, "CrafterRecoveryReopen", render=True, pack=args.pack) as world:
        setup_process(world)
        world.call("select", SLOTS[INLET])
        click(world, INLET, "south")
        steps(world, 25)
        assert phase(world, INLET) == "IDLE" and contents(world, INLET) == {SLOTS[INLET]: 1}
        assert not contents(world, BARREL)

        world.command("/save-all")
        world.restart()
        assert_pose(world, COVERED, "south", "left")
        assert phase(world, INLET) == "IDLE"
        assert {pos: contents(world, pos) for pos in SLOTS} == {
            pos: {item: 1} for pos, item in SLOTS.items()
        }

        full = ",".join(f'{{Slot:{slot}b,id:"minecraft:cobblestone",count:64}}' for slot in range(27))
        world.command(f"/data merge block {coords(BARREL)} {{Items:[{full}]}}")
        assert contents(world, BARREL) == {"minecraft:cobblestone": 27 * 64}
        install_cover(world)
        for _ in range(25):
            if phase(world, LEAF) == "EXPORTING":
                break
            steps(world, 1)
        else:
            raise AssertionError(f"Expected active grid after covering blank slot: {tags(world, LEAF)}")
        assert contents(world, LEAF, "GroupedItems.Grid") == {SLOTS[LEAF]: 1}
        assert phase(world, INLET) == "ACCEPTING"
        assert contents(world, INLET, "GroupedItems.Grid") == {SLOTS[INLET]: 1}
        world.command("/save-all")
        world.restart()
        steps(world, 150)
        assert phase(world, OUTLET) == "INSERTING", tags(world, OUTLET)
        assert contents(world, OUTLET, "GroupedItems.Grid") == {CANNON: 1}
        assert contents(world, BARREL) == {"minecraft:cobblestone": 27 * 64}
        assert "Cover: 1b" in tags(world, COVERED)

        world.command(f"/item replace block {coords(BARREL)} container.0 with minecraft:air")
        steps(world, 65)
        assert contents(world, BARREL) == {"minecraft:cobblestone": 26 * 64, CANNON: 1}
        for pos in (*SLOTS, COVERED):
            assert phase(world, pos) == "IDLE" and not contents(world, pos), tags(world, pos)


def wrong_ingredients(args):
    with fixture_world(args, "CrafterWrongIngredients", render=True, pack=args.pack) as world:
        setup_process(world, wrong=True)
        install_cover(world)
        world.call("select", STICK)
        click(world, INLET, "south")
        assert inventory(world, STICK) == 0, tags(world, INLET)
        assert phase(world, INLET) == "ACCEPTING", tags(world, INLET)
        world.command("/tp @s 5.5 104 -4.5")
        steps(world, 75)
        assert phase(world, OUTLET) == "IDLE" and not contents(world, BARREL), tags(world, OUTLET)
        expected = Counter(SLOTS.values())
        del expected[SLOTS[INLET]]
        expected[STICK] = 1
        drops = Counter()
        for entity in world.call("entities", 12, "minecraft:item")["entities"]:
            drops[entity["item"]["item"]] += entity["item"]["count"]
        assert drops == expected, (drops, expected)


CASES = {
    "survival": survival,
    "lan": lan,
    "process": processing,
    "wrong": wrong_ingredients,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--case", choices=CASES)
    args = parser.parse_args()
    for case in (args.case,) if args.case else CASES:
        CASES[case](args)
        print(f"Mechanical Crafter {case} case passed.", flush=True)


if __name__ == "__main__":
    main()
