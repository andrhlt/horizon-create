#!/usr/bin/env python3
"""Compare the original Water Wheel award and player ownership."""
import argparse
import csv
from importlib import import_module
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

adv = import_module("test-first-advancements")
multiplayer = adv.multiplayer
GUEST = "WheelOwner"
def wheel_fixture(large):
    size = "large" if large else "small"
    return size, Path(f"gametest/fluids/{size}_waterwheel.nbt")


def place_wheel(world, actor, target, x, y, large):
    name = "large_water_wheel" if large else "water_wheel"
    state = "axis=z,extension=false" if large else "facing=south,waterlogged=false"
    clear = (f"/fill {x-1} {y-1} -10 {x+1} {y+1} -9 minecraft:air"
             if large else f"/fill {x} {y} -10 {x} {y} -9 minecraft:air")
    world.commands((
        f"/gamemode survival {target}",
        f"/tp {target} {x+.5} {y} -7.0",
        clear,
        f"/give {target} create:{name}",
    ))
    item = f"create:{name}"
    multiplayer.until("the placer to hold a Water Wheel",
                      lambda: actor.call("inventory")["counts"].get(item) == 1)
    actor.call("select", item)
    # Aim at the south face; from floor height the ray passes above the
    # upstream stressometer mounted in front of the wheel fixture.
    actor.call("look-at", x + .5, y + .5, -10.999)
    actor.call("wait", 2)
    hit = actor.call("looking-at")
    block = hit.get("block") or {}
    if hit.get("kind") != "block" or block.get("pos") != [x, y, -11] or block.get("face") != "south":
        raise RuntimeError(f"Water Wheel placement ray missed {(x, y, -11)} south face: {hit}")
    player = actor.call("state")["player"]
    held = (actor.call("inventory").get("held") or {}).get("item")
    reach = math.dist(player["eye"], block["point"])
    if player["sneaking"] or held != item or reach > 4.5:
        raise RuntimeError(f"Invalid Water Wheel placement input: reach={reach:.2f}, held={held}, player={player}")
    print(f"Water Wheel placement input: target={(x, y, -11)} face=south reach={reach:.2f} "
          f"held={held} sneak={player['sneaking']} yaw={player['yaw']:.1f} pitch={player['pitch']:.1f}", flush=True)
    actor.call("mouse", "right", "click")
    actor.call("wait", 8)
    print(f"Water Wheel placement result: {world.call('block', x, y, -10)}; "
          f"inventory={actor.call('inventory')['counts']}", flush=True)
    multiplayer.until("the new Water Wheel to be placed on its original axis",
                      lambda: world.call("block", x, y, -10)["state"] == f"{item}[{state}]")
    multiplayer.until("the wheel item to be consumed",
                      lambda: not actor.call("inventory")["counts"].get(item))


def run_trip(world, actor, target, rows, structure, *, large=False, reopen=False, step_after_reopen=False):
    x, y = (7, 98) if large else (6, 97)
    open_lever, left_lever = ((6, 103, -11), (8, 102, -11)) if large else ((5, 101, -11), (7, 100, -11))
    wheel = f"{x} {y} -10"
    world.command(f"/place template create:{structure.with_suffix('')} 3 96 -12")
    place_wheel(world, actor, target, x, y, large)
    if reopen:
        before = world.command(f"/data get block {wheel} Owner").partition("block data: ")[2]
        world.restart()
        after = world.command(f"/data get block {wheel} Owner").partition("block data: ")[2]
        if not before or after != before:
            raise RuntimeError("The placed wheel lost its original owner while reopening.")
        if step_after_reopen:
            world.step_to(world.clock() + 1)
    level = 100 if large else 98
    world.commands((
        f"/fill {x-2} {level} -14 {x+2} {level} -14 minecraft:smooth_stone",
        f"/tp @s {x+.5} {level+1} -13.5",
    ))
    world.call("wait", 3)
    world.call("interact", *open_lever, "north")
    start = world.clock()
    errors = []
    for row in rows:
        tick = int(row["tick"])
        if tick:
            world.step_to(start + tick)
        block = world.command(f"/data get block {wheel} FlowScore")
        score = int(block.partition("block data: ")[2] or 0)
        owner = adv.progress(world, target, ("water_wheel",))[0]
        actual = (str(score), owner)
        expected = (row["flow"], row["owner"])
        if actual != expected:
            errors.append((tick, expected, actual))
        if target != "@s" and adv.progress(world, "@s", ("water_wheel",))[0] != row["bystander"]:
            raise RuntimeError(f"The wheel also awarded its bystander at tick {tick}.")
        if tick == (40 if large else 25):
            world.call("interact", *left_lever, "north")
    if errors:
        raise RuntimeError(f"{len(errors)} Java timing mismatches. First: {errors[:6]}")
    print(f"Water Wheel flow and ownership award matched all {len(rows)} Java ticks.")


def run_lava_trip(world, actor, target, rows, *, large):
    item = "create:large_water_wheel" if large else "create:water_wheel"
    state = "axis=z,extension=false" if large else "facing=south,waterlogged=false"
    lava_x = 8 if large else 7
    wall_x = lava_x + 1
    world.commands((
        "/setblock 6 103 -7 minecraft:stone",
        "/setblock 6 104 -11 minecraft:stone",
        f"/setblock {wall_x} 104 -10 minecraft:stone",
        f"/setblock {wall_x} 105 -10 minecraft:stone",
        "/setblock 6 104 -9 minecraft:stone",
        f"/gamemode survival {target}",
        f"/tp {target} 6.5 104 -7.0",
        f"/give {target} {item}",
    ))
    multiplayer.until("the lava wheel placer to hold the wheel",
                      lambda: actor.call("inventory")["counts"].get(item) == 1)
    actor.call("select", item)
    actor.call("look-at", 6.5, 104.5, -10.999)
    actor.call("wait", 2)
    hit = actor.call("looking-at")
    block = hit.get("block") or {}
    if hit.get("kind") != "block" or block.get("pos") != [6, 104, -11] or block.get("face") != "south":
        raise RuntimeError(f"Magma Wheel placement ray missed {(6, 104, -11)} south face: {hit}")
    player = actor.call("state")["player"]
    held = (actor.call("inventory").get("held") or {}).get("item")
    reach = math.dist(player["eye"], block["point"])
    if player["sneaking"] or held != item or reach > 4.5:
        raise RuntimeError(f"Invalid Magma Wheel placement input: reach={reach:.2f}, held={held}, player={player}")
    print(f"Magma Wheel placement input: target={(6, 104, -11)} face=south reach={reach:.2f} "
          f"held={held} sneak={player['sneaking']}", flush=True)
    actor.call("mouse", "right", "click")
    actor.call("wait", 8)
    multiplayer.until("the lava-test wheel to be placed on its original axis",
                      lambda: world.call("block", 6, 104, -10)["state"] == f"{item}[{state}]")
    world.command("/setblock 6 104 -11 minecraft:air")
    start = world.clock()
    differences = []
    awards = ("water_wheel", "lava_wheel_00000")
    for row in rows:
        tick = int(row["tick"])
        world.step_to(start + tick)
        block = world.command("/data get block 6 104 -10 FlowScore")
        score = int(block.partition("block data: ")[2] or 0)
        actual = (str(score), *adv.progress(world, target, awards))
        expected = (row["flow"], *(row[name] for name in awards))
        if actual != expected:
            differences.append((tick, expected, actual))
        if target != "@s" and adv.progress(world, "@s", (awards[-1],))[0] != row["bystander"]:
            raise RuntimeError(f"The lava wheel also awarded its bystander at tick {tick}.")
        if tick == 4:
            world.command(f"/setblock {lava_x} 104 -10 minecraft:lava[level=8]")
    if differences:
        raise RuntimeError(f"{len(differences)} Java lava-wheel mismatches. First: {differences[:6]}")
    print(f"Magma Wheel flow and exclusive ownership award matched all {len(rows)} Java ticks.")


def run(args):
    size, structure = wheel_fixture(args.large)
    if args.lava:
        size, structure = ("large-lava" if args.large else "lava"), None
    with (ROOT / f"fixtures/{size}-waterwheel-advancement-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    if args.large and args.reopen:
        phase = "-six-ticks" if args.step_after_reopen else ""
        with (ROOT / f"fixtures/large-waterwheel-server-restart{phase}-java.csv").open() as source:
            restarted = list(csv.DictReader(source))
        for award, motion in zip(rows, restarted, strict=True):
            if award["tick"] != motion["tick"]:
                raise RuntimeError("The Java restart and ownership references use different ticks.")
            award["flow"] = motion["flow"]
    scenario = "WheelAwardReopen" if args.reopen else "WheelAwardLAN" if args.multiplayer else "WheelAward"
    with fixture_world(args, f"{scenario}{size}", structure, render=True, pack=args.pack) as world:
        def exercise(actor, target):
            if args.lava:
                run_lava_trip(world, actor, target, rows, large=args.large)
            else:
                run_trip(world, actor, target, rows, structure, large=args.large, reopen=args.reopen,
                         step_after_reopen=args.step_after_reopen)

        if not args.multiplayer:
            exercise(world, "@s")
            return
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-wheel-award-") as folder, multiplayer.joined_client(
            args, Path(folder), f"127.0.0.1:{port}", GUEST, render=True, scenario="wheel",
            pack=args.pack,
        ) as guest:
            multiplayer.until("the wheel placer to join", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in world.call("lan", "status")["guests"]
            ))
            exercise(guest, GUEST)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--large", action="store_true")
    parser.add_argument("--lava", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--multiplayer", action="store_true")
    mode.add_argument("--reopen", action="store_true")
    parser.add_argument("--step-after-reopen", action="store_true")
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    if args.lava and args.reopen:
        parser.error("--reopen requires a water fixture")
    if args.step_after_reopen and not (args.large and args.reopen):
        parser.error("--step-after-reopen requires --large and --reopen")
    run(args)
