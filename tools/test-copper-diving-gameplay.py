#!/usr/bin/env python3
"""Check copper diving boot motion, backtank warnings, and save/reopen."""

import argparse
from contextlib import ExitStack
from importlib import import_module
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

mp = import_module("test-multiplayer")

POOL = ((8, 170, 21), (10, 175, 23))
TANK_POS = (9, 170, 24)
PLAYER_DRY = (9.5, 170.5, 25.5)
PLAYER_WATER = (9.5, 170.0, 22.5)
AIR = re.compile(r'"create:banktank_air":\s*(\d+)')


def set_up(world, *, boots=False):
    world.commands((
        "/gamemode survival",
        f"/tp @s {PLAYER_DRY[0]} {PLAYER_DRY[1]} {PLAYER_DRY[2]} 180 0",
    ))
    world.call("wait-ready")
    setup_chat = world.commands((
        "/fill 8 170 21 10 175 23 minecraft:air",
        "/fill 8 170 21 10 175 23 minecraft:water",
    ))
    world.step_to(world.clock() + 1)
    world.commands((
        "/setblock 9 169 22 minecraft:stone",
        "/setblock 9 169 25 minecraft:stone",
    ))
    world.step_to(world.clock() + 1)
    water = world.call("block", 9, 171, 22)
    if water.get("block") != "minecraft:water":
        raise RuntimeError(f"Fixture fills did not produce the water pool: {setup_chat}; {water}")
    if boots:
        world.command("/item replace entity @s armor.feet with create:copper_diving_boots")


def equip_tank(world, air, material="copper"):
    x, y, z = TANK_POS
    tank_item = f"create:{material}_backtank"
    world.command(f"/setblock {x} {y} {z} {tank_item}[facing=south,waterlogged=false]")
    world.command(f"/data merge block {x} {y} {z} {{Air:{air}}}")
    world.call("interact", x, y, z, "south")
    expected = f'"create:banktank_air": {air}'
    for _ in range(20):
        stack = world.command("/data get entity @s equipment.chest")
        if expected in stack:
            return
        world.step_to(world.clock() + 1)
    raise RuntimeError(f"The {air}-air Backtank did not equip: {stack}")


def tank_air(world):
    stack = world.command("/data get entity @s equipment.chest")
    match = AIR.search(stack)
    if not match:
        raise RuntimeError(f"The equipped tank has no air component: {stack}")
    return int(match[1])


def movement(args, boots_item="create:copper_diving_boots"):
    def scenario(label, boots, *, forward=False):
        with fixture_world(args, f"CopperBootMovement{label}{'Forward' if forward else ''}",
                           render=False, pack=args.pack, terrain_seed=2081) as world:
            set_up(world)
            world.command(f"/tp @s {PLAYER_WATER[0]} {PLAYER_WATER[1]} {PLAYER_WATER[2]} 0 0")
            # Capture the same unbooted state before adding the treatment item.
            # The pre-physics injection then applies on the next local player tick.
            water = world.call("block", 9, 173, 22)
            if water.get("block") != "minecraft:water":
                raise RuntimeError(f"{label} start was not inside the prepared water volume: {water}")
            start = world.call("state")["player"]
            for _ in range(12):
                if start["on_ground"]:
                    break
                world.step_to(world.clock() + 1)
                start = world.call("state")["player"]
            if start["pose"] != "STANDING":
                raise RuntimeError(f"{label} did not start in the Java standing pose: {start}")
            if not start["on_ground"] or abs(start["position"][1] - 170.0) > 1e-4:
                raise RuntimeError(f"{label} did not settle on the submerged stone floor: {start}")
            if forward:
                world.call("key", "w", "down")
            if not forward:
                world.command("/setblock 9 169 22 minecraft:air")
            if boots:
                world.command(f"/item replace entity @s armor.feet with {boots_item}")
                feet = world.command("/data get entity @s equipment.feet")
                if f'id: "{boots_item}"' not in feet:
                    raise RuntimeError(f"The {boots_item} were not equipped before the movement tick: {feet}")
            tick = world.clock()
            sample_count = 3 if forward else 8
            for sample_tick in range(tick + 1, tick + sample_count + 1):
                world.step_to(sample_tick)
            after = world.call("state")["player"]
            if forward:
                world.call("key", "w", "up")
            return start, after

    bare, bare_after = scenario("Control", False)
    equipped, equipped_after = scenario("Equipped", True)
    start_position_delta = abs(bare["position"][1] - equipped["position"][1])
    start_velocity_delta = abs(bare["velocity"][1] - equipped["velocity"][1])
    if start_position_delta > 0.001 or start_velocity_delta > 0.001 or bare["pose"] != equipped["pose"] or bare["on_ground"] != equipped["on_ground"]:
        raise RuntimeError(f"The live player-tick snapshots were not equivalent enough to compare: bare={bare}, boots={equipped}")
    bare_dy = bare_after["velocity"][1] - bare["velocity"][1]
    boots_dy = equipped_after["velocity"][1] - equipped["velocity"][1]
    if boots_dy > bare_dy - 0.04:
        raise RuntimeError(f"{boots_item} missed Java's -0.05/tick downward impulse: bare Δvy={bare_dy:.6f}, boots Δvy={boots_dy:.6f}; start={equipped}; end={equipped_after}")
    if equipped_after["position"][1] > bare_after["position"][1] - 0.2:
        raise RuntimeError(f"{boots_item} did not cause consequentially faster sinking over eight submerged ticks: bare={bare_after}, boots={equipped_after}")

    moving_bare, moving_bare_after = scenario("Control", False, forward=True)
    moving_boots, moving_boots_after = scenario("Equipped", True, forward=True)
    moving_position_delta = abs(moving_bare["position"][1] - moving_boots["position"][1])
    moving_velocity_delta = abs(moving_bare["velocity"][1] - moving_boots["velocity"][1])
    if moving_position_delta > 0.001 or moving_velocity_delta > 0.001 or moving_bare["pose"] != moving_boots["pose"] or moving_bare["on_ground"] != moving_boots["on_ground"]:
        raise RuntimeError(f"The live input-state snapshots were not equivalent enough to compare: bare={moving_bare}, boots={moving_boots}")
    bare_speed = (moving_bare_after["velocity"][0] ** 2 + moving_bare_after["velocity"][2] ** 2) ** 0.5
    boots_speed = (moving_boots_after["velocity"][0] ** 2 + moving_boots_after["velocity"][2] ** 2) ** 0.5
    if bare_speed <= 0 or boots_speed < bare_speed * 1.25:
        raise RuntimeError(f"{boots_item} did not apply Java's 1.3 underwater movement multiplier: bare={moving_bare_after}, boots={moving_boots_after}")
    print(f"{boots_item}: matched submerged start; Δvy equipped={boots_dy:.6f}, bare={bare_dy:.6f}; forward speed bare={bare_speed:.6f}, equipped={boots_speed:.6f}.")


def lan_movement(args, boots_item="create:copper_diving_boots"):
    with TemporaryDirectory(prefix="hc-copper-boots-lan-", dir="/private/tmp") as temp:
        with ExitStack() as sessions:
            host = sessions.enter_context(fixture_world(args, "CopperBootMovementLan", render=False,
                                                         pack=args.pack, terrain_seed=2081))
            host.command("/gamemode survival")
            host.command("/tp @s 9.5 170 22.5 0 0")
            host.call("wait-ready")
            host.commands((
                "/fill 8 170 21 14 175 23 minecraft:water",
                "/fill 8 169 21 14 169 23 minecraft:stone",
            ))
            host.step_to(host.clock() + 1)
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            guest_name = "CopperBootGuest"
            guest = sessions.enter_context(mp.joined_client(
                args, Path(temp), f"127.0.0.1:{port}", guest_name, render=False,
                scenario="copper-diving-movement", pack=args.pack))
            mp.until("copper boots guest joins", lambda: any(
                item["name"] == guest_name and item["placed"] for item in host.call("lan", "status")["guests"]))
            host.commands((
                f"/tp @s 9.5 170 22.5 0 0",
                f"/tp {guest_name} 13.5 170 22.5 0 0",
            ))
            mp.until("guest to reach its submerged start", lambda:
                     abs(guest.call("state")["player"]["position"][0] - 13.5) < 0.1 and
                     guest.call("state")["player"]["on_ground"])
            starts = (host.call("state")["player"], guest.call("state")["player"])
            for label, state in zip(("host", "guest"), starts):
                if state["pose"] != "STANDING" or not state["on_ground"] or abs(state["position"][1] - 170) > 1e-3:
                    raise RuntimeError(f"LAN {label} did not start standing on the submerged floor: {state}")
            host.commands((
                f"/item replace entity @s armor.feet with {boots_item}",
                f"/item replace entity {guest_name} armor.feet with {boots_item}",
            ))
            host.commands(("/setblock 9 169 22 minecraft:air", "/setblock 13 169 22 minecraft:air"))
            tick = host.clock()
            for sample_tick in range(tick + 1, tick + 5):
                host.step_to(sample_tick)
            ends = (host.call("state")["player"], guest.call("state")["player"])
            for label, start, end in zip(("host", "guest"), starts, ends):
                drop = start["position"][1] - end["position"][1]
                if drop < 0.25 or end["velocity"][1] > -0.15:
                    raise RuntimeError(f"LAN {label} did not receive the {boots_item} sinking effect: start={start}, end={end}")
            print(f"{boots_item} sinking ran for both the LAN host player and joined guest.")


def warning(args, starting_air):
    scenario = f"CopperTankWarning{starting_air}"
    with fixture_world(args, scenario, render=False, pack=args.pack) as world:
        set_up(world, boots=True)
        world.command("/item replace entity @s armor.head with create:copper_diving_helmet")
        world.command(f"/tp @s {PLAYER_DRY[0]} {PLAYER_DRY[1]} {PLAYER_DRY[2]} 180 0")
        equip_tank(world, starting_air)
        world.command(f"/tp @s {PLAYER_WATER[0]} {PLAYER_WATER[1]} {PLAYER_WATER[2]} 180 0")
        for _ in range(40):
            world.step_to(world.clock() + 1)
            if tank_air(world) == starting_air - 1:
                break
        else:
            raise RuntimeError(f"Backtank air did not decrease from {starting_air}")

        messages = world.call("messages")
        subtitle = messages.get("subtitle") or ""
        if "⚠" not in subtitle:
            raise RuntimeError(f"No visible low/depleted warning at {starting_air - 1} air: {messages}")
        print(f"Backtank warning appeared at {starting_air}→{starting_air - 1} air: {subtitle}")


def reopen(args, material="copper"):
    helmet_item = f"create:{material}_diving_helmet"
    with fixture_world(args, f"{material.title()}DivingReopen", render=False, pack=args.pack) as world:
        set_up(world, boots=True)
        world.command(f"/tp @s {PLAYER_DRY[0]} {PLAYER_DRY[1]} {PLAYER_DRY[2]} 180 0")
        equip_tank(world, 900, material)
        world.restart()
        if tank_air(world) != 900:
            raise RuntimeError("A charged Backtank did not retain 900 air on reopen.")

        world.command(f"/item replace entity @s armor.head with {helmet_item}")
        world.command(f"/tp @s {PLAYER_WATER[0]} {PLAYER_WATER[1]} {PLAYER_WATER[2]} 180 0")
        for _ in range(40):
            world.step_to(world.clock() + 1)
            if tank_air(world) == 899:
                break
        else:
            raise RuntimeError("The reopened diving suit did not consume one air unit underwater.")

        world.restart()
        if tank_air(world) != 899:
            raise RuntimeError("A partially depleted Backtank did not retain 899 air on reopen.")
        for _ in range(25):
            world.step_to(world.clock() + 1)
            if tank_air(world) == 898:
                break
        else:
            raise RuntimeError("Underwater air consumption did not resume after reopening.")
    print(f"Charged and partially depleted {material.title()} Backtanks survived reopen; breathing resumed after reload.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--movement", action="store_true")
    parser.add_argument("--lan-movement", action="store_true")
    parser.add_argument("--netherite-movement", action="store_true")
    parser.add_argument("--netherite-lan-movement", action="store_true")
    parser.add_argument("--warnings", action="store_true")
    parser.add_argument("--reopen", action="store_true")
    parser.add_argument("--netherite-reopen", action="store_true")
    args = parser.parse_args()
    selected = args.movement or args.lan_movement or args.netherite_movement or args.netherite_lan_movement or args.warnings or args.reopen or args.netherite_reopen
    if not selected or args.movement:
        movement(args)
    if not selected or args.lan_movement:
        lan_movement(args)
    if args.netherite_movement:
        movement(args, "create:netherite_diving_boots")
    if args.netherite_lan_movement:
        lan_movement(args, "create:netherite_diving_boots")
    if not selected or args.warnings:
        warning(args, 91)
        warning(args, 2)
    if not selected or args.reopen:
        reopen(args)
    if args.netherite_reopen:
        reopen(args, "netherite")


if __name__ == "__main__":
    main()
