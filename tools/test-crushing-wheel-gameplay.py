#!/usr/bin/env python3
"""Check Crushing Wheel power boundaries, output recovery, and persistence."""

import argparse
from collections import Counter
import importlib
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

multiplayer = importlib.import_module("test-multiplayer")

WHEEL = "create:crushing_wheel"
CONTROLLER = "create:crushing_wheel_controller"
MOTOR_A = (-1, 100, 0)
MOTOR_B = (1, 102, 0)
WHEEL_A = (0, 100, 0)
WHEEL_B = (0, 102, 0)
CONTROL = (0, 101, 0)
DEPOT = (0, 100, 1)
GUEST = "CrusherGuest"


def coords(pos):
    return " ".join(map(str, pos))


def advance(world, ticks):
    for _ in range(ticks):
        world.step_to(world.clock() + 1)


def tags(world, pos=CONTROL):
    return world.command(f"/data get block {coords(pos)}")


def scalar(text, key, default=None):
    match = re.search(rf"\b{re.escape(key)}: (-?\d+(?:\.\d+)?)", text)
    if match:
        value = float(match[1])
        return int(value) if value.is_integer() else value
    if default is not None:
        return default
    raise RuntimeError(f"Missing {key} in {text}")


def inventory(text):
    stacks = Counter()
    for fragment in re.findall(r"\{[^{}]*\}", text):
        item = re.search(r'\bid: "([\w:]+)"', fragment)
        count = re.search(r"\b(?:count|Count): (\d+)", fragment)
        if item and count:
            stacks[item[1]] += int(count[1])
    return stacks


def setup(world, *, speed_b=128):
    world.commands((
        "/fill -5 99 -5 5 99 5 minecraft:smooth_stone",
        f"/setblock {coords(MOTOR_A)} create:creative_motor[facing=east]{{ScrollValue:128}}",
        f"/setblock {coords(MOTOR_B)} create:creative_motor[facing=west]{{ScrollValue:{speed_b}}}",
        f"/setblock {coords(WHEEL_A)} {WHEEL}[axis=x]",
        f"/setblock {coords(WHEEL_B)} {WHEEL}[axis=x]",
        f"/setblock {coords(DEPOT)} create:depot",
    ))
    advance(world, 4)
    state = world.call("block", *CONTROL)["state"]
    if not state.startswith(CONTROLLER):
        raise RuntimeError(f"Aligned wheels did not form their controller: {state}; "
                           f"wheel A={tags(world, WHEEL_A)}; wheel B={tags(world, WHEEL_B)}")
    return state


def rpm(world, pos=CONTROL):
    return scalar(tags(world, pos), "Speed", 0)


def wheel_rpms(world):
    return scalar(tags(world, WHEEL_A), "Speed", 0), scalar(tags(world, WHEEL_B), "Speed", 0)


def insert_gravel(world, count=64):
    world.command(f"/item replace block {coords(CONTROL)} container.0 with minecraft:gravel {count}")
    world.command(f"/data merge block {coords(CONTROL)} {{ProcessingTime:250.0f,AppliedRecipe:0b}}")


def wait_for(world, description, predicate, ticks=400):
    for _ in range(ticks):
        value = predicate()
        if value:
            return value
        advance(world, 1)
    raise RuntimeError(f"Timed out waiting for {description}: {tags(world)}")


def rotation(world, speed_b=128):
    state = setup(world, speed_b=-128)
    same_sign = wheel_rpms(world)
    if "valid=false" not in state:
        raise RuntimeError(f"Equal-sign wheel pair should be invalid, got {state}; "
                           f"wheel A={tags(world, WHEEL_A)}; wheel B={tags(world, WHEEL_B)}; "
                           f"motor A={tags(world, MOTOR_A)}; motor B={tags(world, MOTOR_B)}")
    if same_sign[0] == 0 or same_sign[1] == 0 or same_sign[0] * same_sign[1] <= 0:
        raise RuntimeError(f"Invalid same-sign case did not have equal nonzero wheel speeds: {same_sign}")
    if rpm(world) != 0:
        raise RuntimeError(f"Equal-sign wheel pair generated controller speed {rpm(world)}")

    world.command(f"/data merge block {coords(MOTOR_B)} {{ScrollValue:-128}}")
    advance(world, 3)
    invalid = world.call("block", *CONTROL)["state"]
    if "valid=false" not in invalid or rpm(world) != 0:
        raise RuntimeError(f"Same-sign wheel pair became valid: {invalid}, speed={rpm(world)}")

    world.command(f"/data merge block {coords(MOTOR_B)} {{ScrollValue:128}}")
    advance(world, 3)
    active = world.call("block", *CONTROL)["state"]
    opposing = wheel_rpms(world)
    if "valid=true" not in active or "facing=south" not in active or rpm(world) != 2.56:
        raise RuntimeError(f"Opposing wheel pair did not run south at 2.56 speed: {active}, {rpm(world)}")
    if opposing[0] * opposing[1] >= 0:
        raise RuntimeError(f"South-facing active case did not have opposite wheel speeds: {opposing}")

    world.command(f"/data merge block {coords(MOTOR_A)} {{ScrollValue:-128}}")
    world.command(f"/data merge block {coords(MOTOR_B)} {{ScrollValue:-128}}")
    advance(world, 3)
    reverse = world.call("block", *CONTROL)["state"]
    reversed_rpms = wheel_rpms(world)
    if "valid=true" not in reverse or "facing=north" not in reverse or rpm(world) != 2.56:
        raise RuntimeError(f"Reversed opposing pair did not reverse controller direction: {reverse}, {rpm(world)}")
    if reversed_rpms[0] * reversed_rpms[1] >= 0:
        raise RuntimeError(f"Reversed active case did not retain opposite wheel speeds: {reversed_rpms}")
    world.command(f"/data merge block {coords(MOTOR_A)} {{ScrollValue:128}}")
    world.command(f"/data merge block {coords(MOTOR_B)} {{ScrollValue:128}}")
    advance(world, 3)
    active = world.call("block", *CONTROL)["state"]
    if "valid=true" not in active or "facing=south" not in active or rpm(world) != 2.56:
        raise RuntimeError(f"Opposing wheel pair did not run south at 2.56 speed: {active}, {rpm(world)}")
    insert_gravel(world)
    wait_for(world, "gravel admission", lambda: "minecraft:gravel" in inventory(tags(world)))
    before = tags(world)

    world.command(f"/data merge block {coords(MOTOR_A)} {{ScrollValue:0}}")
    advance(world, 3)
    stopped_state = world.call("block", *CONTROL)["state"]
    stopped = tags(world)
    if "valid=false" not in stopped_state or inventory(stopped) != inventory(before):
        raise RuntimeError(f"Stopping a loaded pair changed its buffered input: {before} -> {stopped}")
    stopped_time = scalar(stopped, "ProcessingTime")
    advance(world, 5)
    if scalar(tags(world), "ProcessingTime") != stopped_time:
        raise RuntimeError("Crushing progress continued while the wheel pair was stopped")

    world.command(f"/data merge block {coords(MOTOR_A)} {{ScrollValue:128}}")
    advance(world, 3)
    restarted_state = world.call("block", *CONTROL)["state"]
    if "valid=true" not in restarted_state:
        raise RuntimeError(f"Opposing pair did not restart after power returned: {restarted_state}")
    wait_for(world, "processing to resume", lambda: scalar(tags(world), "ProcessingTime") < stopped_time)
    print(f"Crusher measured wheel speeds: same-sign invalid={same_sign}, opposing active={opposing}; "
          f"reverse-facing={reverse} at {reversed_rpms}; stopped input and progress were retained and resumed.", flush=True)


def blocked_output(world):
    setup(world, speed_b=128)
    world.command(f"/item replace block {coords(DEPOT)} container.0 with minecraft:iron_sword")
    insert_gravel(world)
    wait_for(world, "the Crusher to apply the gravel recipe", lambda: scalar(tags(world), "AppliedRecipe", 0) == 1)
    # Gravel has a guaranteed sand output plus independent flint and clay-ball chances.
    buffered = inventory(tags(world))
    if buffered.get("minecraft:sand", 0) != 64 or buffered.get("minecraft:gravel", 0):
        raise RuntimeError(f"Blocked output should retain 64 sand and consume gravel: {buffered}, {tags(world)}")
    before = buffered.copy()
    advance(world, 5)
    if inventory(tags(world)) != before:
        raise RuntimeError("A full Depot consumed or duplicated buffered Crusher output")

    world.command(f"/item replace block {coords(DEPOT)} container.0 with minecraft:air")
    wait_for(world, "Crusher output to reach the Depot", lambda: inventory(tags(world, DEPOT)).get("minecraft:sand", 0) == 64)
    recovered = inventory(tags(world, DEPOT))
    remaining = inventory(tags(world))
    if recovered.get("minecraft:sand", 0) + remaining.get("minecraft:sand", 0) != 64:
        raise RuntimeError(f"Sand was lost or duplicated during blocked-output recovery: depot={recovered}, controller={remaining}")
    for optional in ("minecraft:flint", "minecraft:clay_ball"):
        if recovered.get(optional, 0) + remaining.get(optional, 0) != before.get(optional, 0):
            raise RuntimeError(f"{optional} was lost or duplicated: before={before}, depot={recovered}, controller={remaining}")


def reopen(world):
    state = setup(world, speed_b=128)
    if "valid=true" not in state:
        raise RuntimeError(f"Idle crusher pair is not active before save: {state}")
    idle_before = (state, rpm(world), inventory(tags(world)))
    world.command("/save-all")
    world.restart()
    advance(world, 3)
    idle_after = (world.call("block", *CONTROL)["state"], rpm(world), inventory(tags(world)))
    if idle_after != idle_before:
        raise RuntimeError(f"Idle Crusher state changed on reopen: {idle_before} -> {idle_after}")

    insert_gravel(world)
    wait_for(world, "active processing progress", lambda: (
        scalar(tags(world), "AppliedRecipe", 0) == 0
        and 0 < scalar(tags(world), "ProcessingTime", 0) < 250
    ))
    active_before = tags(world)
    input_before = inventory(active_before)
    time_before = scalar(active_before, "ProcessingTime")
    world.command("/save-all")
    world.restart()
    active_after = tags(world)
    reopened_time = scalar(active_after, "ProcessingTime")
    if inventory(active_after) != input_before or reopened_time > time_before:
        raise RuntimeError(f"Active Crusher input/progress was lost or reset on reopen: {active_before} -> {active_after}")
    wait_for(world, "active Crusher work to resume", lambda: scalar(tags(world), "ProcessingTime", 0) < reopened_time)


def lan(args):
    with TemporaryDirectory(prefix="hc-crushing-lan-") as scratch:
        with fixture_world(args, "CrushingWheelLAN", pack=args.pack) as host:
            setup(host, speed_b=128)
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            with multiplayer.joined_client(args, Path(scratch), f"127.0.0.1:{port}", GUEST,
                                           scenario="crushing-wheel-lan", pack=args.pack) as guest:
                multiplayer.until("guest to join", lambda: any(
                    p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]
                ))
                multiplayer.until("guest to see the formed controller", lambda:
                                  guest.call("block", *CONTROL)["state"] == host.call("block", *CONTROL)["state"])
                guest_state = guest.call("block", *CONTROL)["state"]
                if "valid=true" not in guest_state:
                    raise RuntimeError(f"Guest did not observe the active Crusher: {guest_state}")
                insert_gravel(host, 16)
                wait_for(host, "host Crusher to finish its gravel batch", lambda:
                         scalar(tags(host), "AppliedRecipe", 0) == 1, ticks=250)
                host_inventory = inventory(tags(host))
                if host_inventory.get("minecraft:sand", 0) != 16:
                    raise RuntimeError(f"Host Crusher did not produce sixteen sand: {host_inventory}")
                # The host collects the guaranteed output from the Depot; the guest sees the
                # same server inventory and can collect it from the shared block.
                host.command(f"/item replace block {coords(DEPOT)} container.0 with minecraft:air")
                wait_for(host, "host Depot collection", lambda:
                         inventory(tags(host, DEPOT)).get("minecraft:sand", 0) == 16)
                guest_inventory_before = guest.call("inventory")["counts"].get("minecraft:sand", 0)
                host.command(f"/tp {GUEST} 0.5 101 1.5")
                multiplayer.until("guest to reach the output Depot", lambda: (
                    (position := guest.call("state")["player"]["position"])
                    and abs(position[0] - 0.5) < 0.3
                    and abs(position[1] - 101.0) < 0.5
                    and abs(position[2] - 1.5) < 0.3
                ))
                guest.call("look-at", 0.5, 100.5, 1.5)
                guest.call("interact", *DEPOT, "up")
                multiplayer.until("guest to collect the Crusher output", lambda:
                                  guest.call("inventory")["counts"].get("minecraft:sand", 0) == guest_inventory_before + 16)


CASES = {"rotation": rotation, "blocked": blocked_output, "reopen": reopen}


def run(args):
    if args.case == "lan":
        lan(args)
        return
    with fixture_world(args, f"CrushingWheel-{args.case}", pack=args.pack) as world:
        if args.case == "rotation":
            rotation(world, speed_b=128)
        else:
            CASES[args.case](world)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--case", choices=("rotation", "blocked", "reopen", "lan"), required=True)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    run(args)
    print(f"Crushing Wheel {args.case} case passed.", flush=True)
