#!/usr/bin/env python3
"""Drive the isolated Packager through the pinned Java redstone schedule."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")

MACHINE = (8, 105, -12)
BARREL = (7, 105, -12)
COMPARATOR = (9, 105, -12)
WIRE = (10, 105, -12)
SIGN = (8, 105, -13)
POWER = (8, 105, -11)


def xyz(pos):
    return " ".join(map(str, pos))


def number(snbt, key):
    match = re.search(r"\b" + key + r":\s*(-?\d+)", snbt)
    return int(match[1]) if match else 0


def string(snbt, key):
    match = re.search(r"\b" + key + r":\s*(['\"])(.*?)\1", snbt)
    return match[2] if match else ""


def top_level_entries(list_snbt):
    depth = 0
    quote = None
    escaped = False
    for index, char in enumerate(list_snbt):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                yield list_snbt[start:index + 1]


def describe_slots(list_snbt, slot_key):
    slots = []
    for item in top_level_entries(list_snbt):
        stack_id = string(item, "id")
        if not stack_id:
            continue
        slot = number(item, slot_key)
        count = number(item, "(?:[cC]ount)") or 1
        name = "@Named" if "Named" in item else ""
        slots.append((slot, f"{stack_id}={count}{name}"))
    return "|".join(f"{slot}:{item}" for slot, item in sorted(slots))


def block_value(world, pos, path):
    return world.command(f"/data get block {xyz(pos)} {path}").partition("block data: ")[2]


def prepare(world):
    world.commands((
        "/fill 5 104 -15 13 104 -9 minecraft:smooth_stone",
        "/fill 5 105 -15 13 109 -9 minecraft:air",
        f"/setblock {xyz(BARREL)} minecraft:barrel",
        f"/setblock {xyz(COMPARATOR)} minecraft:comparator[facing=west]",
        f"/setblock {xyz(WIRE)} minecraft:redstone_wire",
        f"/setblock {xyz(SIGN)} minecraft:oak_sign",
        f'/data merge block {xyz(SIGN)} {{front_text:{{messages:[{{text:"Factory"}},{{text:"A"}},{{text:""}},{{text:""}}]}}}}',
        f"/item replace block {xyz(BARREL)} container.0 with minecraft:iron_ingot 5",
        f"/item replace block {xyz(BARREL)} container.3 with minecraft:iron_ingot 2",
        f"/item replace block {xyz(BARREL)} container.4 with minecraft:redstone 2",
        f'/item replace block {xyz(BARREL)} container.15 with minecraft:iron_ingot[minecraft:custom_name="Named"]',
        "/tp @s 10.5 105 -11.5",
        "/gamemode survival",
    ))


def block_data(world, pos):
    return world.command(f"/data get block {xyz(pos)}").partition("block data: ")[2]


def click(world, actor):
    actor.call("look-at", 8.98, 105.5, -11.5)
    pick = actor.call("looking-at")
    assert pick.get("kind") == "block" and pick["block"]["pos"] == list(MACHINE), pick
    tick = world.clock()
    reply = actor.call("mouse", "right", "click")
    actor.call("wait", 6)
    if os.environ.get("CREATE_PACKAGER_USE_TRACE"):
        print("Packager use", tick, pick, reply, actor.call("inventory")["held"], flush=True)
    assert world.clock() == tick


POSE_TICKS = {12, 16, 18, 21, 27, 36, 39, 42, 47, 54, 64}
POSE_MARKER = re.compile(r"CREATE_PACKAGER_POSE (\d+) (\d+) (true|false) (true|false) "
                        r"([0-9.]+) ([0-9.]+) (true|false) (true|false) (true|false)")


def verify_pose(peer, start, row, java):
    log = peer.socket.parent / "ctl.log"
    tick = int(row["tick"])
    game_time = start + tick
    def sample():
        matches = list(POSE_MARKER.finditer(log.read_text(errors="replace")))
        return next((
            match for match in reversed(matches)
            if int(match[1]) == game_time
            and (match[2], match[3], match[4], match[7], match[8], match[9]) == (
                row["animation"], row["inward"], java["open"], "true", "true", java["box"]
            )
        ), None)

    pose = mp.until(f"the actual Packager draw at game tick {game_time}", sample, seconds=5)
    assert (pose[3], pose[4], pose[7], pose[8], pose[9]) == (
        row["inward"], java["open"], "true", "true", java["box"]
    ), (tick, pose.groups(), java)
    assert int(pose[2]) == int(row["animation"]), (tick, pose.groups(), row)
    animation = int(row["animation"])
    fraction = float(pose[6])
    if fraction < 1e-5:
        reference = float(java["tray_zero"])
    elif abs(fraction - 0.5) < 1e-5:
        reference = float(java["tray_half"])
    elif abs(fraction - 1) < 1e-5:
        reference = float(java["tray_one"])
    else:
        cycle = animation - (0 if row["inward"] == "true" else 5) - fraction
        progress = max(-1, min(1, cycle / 15 * 2 - 1))
        reference = (1 - progress * progress) ** 2
    assert abs(float(pose[5]) - reference) < 2e-6, (tick, pose.groups(), reference)
    print("Verified rendered Packager", tick, pose.groups(), flush=True)


def run(world, actor, name, expected, poses):
    world.command(f"/setblock {xyz(MACHINE)} create:packager[facing=east]")
    # Java's first sample follows the first Packager block entity tick.
    world.step_to(world.clock() + 1)
    start = world.clock()
    clients = (world,) if actor is world else (world, actor)
    if poses:
        for peer in clients:
            peer.call("look-at", 8.98, 105.5, -11.5)
    differences = []
    for row in expected:
        tick = int(row["tick"])
        if tick:
            world.step_to(start + tick)
        if tick in (4, 55):
            world.command(f"/setblock {xyz(POWER)} minecraft:redstone_block")
        elif tick in (7, 59):
            world.command(f"/setblock {xyz(POWER)} minecraft:air")
        if tick in (9, 25, 31):
            if tick == 31:
                mp.until("the real pickup to reach the operator's inventory", lambda:
                         any("package" in (entry.get("item") or "")
                             for entry in actor.call("inventory")["hotbar"]))
                slot = next(entry["slot"] for entry in actor.call("inventory")["hotbar"]
                            if "package" in (entry.get("item") or ""))
                sent = world.command(f"/item replace entity {name} weapon.mainhand from entity {name} hotbar.{slot}")
                assert sent.startswith("Replaced "), sent
                mp.until("the picked-up Package in the actor's hand", lambda:
                         "package" in (actor.call("inventory")["held"] or {}).get("item", ""))
            else:
                world.command(f"/item replace entity {name} weapon.mainhand with minecraft:stick")
                mp.until("the Stick in the actor's hand", lambda:
                         (actor.call("inventory")["held"] or {}).get("item") == "minecraft:stick")
            click(world, actor)

        nbt = block_data(world, MACHINE)
        block = world.call("block", *MACHINE)["state"]
        wire = world.call("block", *WIRE)["state"]
        actual = {
            "powered": "powered=true" in block,
            "active": number(nbt, "Active") != 0,
            "cooldown": number(nbt, "ButtonCooldown"),
            "animation": number(nbt, "AnimationTicks"),
            "inward": number(nbt, "AnimationInward") != 0,
            "wire": wire.partition("power=")[2].split(",")[0].rstrip("]"),
            "held": "HeldBox:" in nbt,
            "inserted": "InsertedBox:" in nbt,
            "address": string(nbt, "SignAddress"),
            "hand_count": (actor.call("inventory")["held"] or {}).get("count", 0),
        }
        active_package = "HeldBox" if actual["held"] else "InsertedBox" if actual["inserted"] else None
        actual["payload"] = describe_slots(block_value(world, MACHINE, f'{active_package}.components."create:package_contents"'), "slot") if active_package else ""
        actual["barrel"] = describe_slots(block_value(world, BARREL, "Items"), "Slot")
        mismatch = {key: (row[key], str(value).lower() if isinstance(value, bool) else str(value))
                    for key, value in actual.items()
                    if row[key] != (str(value).lower() if isinstance(value, bool) else str(value))}
        if mismatch:
            differences.append((tick, mismatch, nbt))
        if poses and tick in POSE_TICKS:
            for peer in clients:
                verify_pose(peer, start, row, poses[tick])
        if tick in (0, 4, 9, 25, 31, 55):
            print(tick, nbt, block_data(world, BARREL), flush=True)
    if differences:
        raise AssertionError(differences[:8])
    print(f"Matched {len(expected)} Java Packager state and wire samples.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--visual", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/packager-redstone-java.csv").open() as ref:
        rows = list(csv.DictReader(ref))
    poses = {}
    if args.visual:
        os.environ["CREATE_PACKAGER_RENDER_TRACE"] = "1"
        with (ROOT / "fixtures/packager-poses-java.csv").open() as ref:
            poses = {int(row["tick"]): row for row in csv.DictReader(ref)}
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, "PackagerDraftGuest" if args.lan else "PackagerDraft", render=True, pack=args.pack))
        prepare(world)
        actor, name = world, "@s"
        if args.lan:
            name = "PackagerGuest"
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-packager-redstone-")))
            actor = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, render=True, scenario="packager-redstone", pack=args.pack,
            ))
            mp.until("the Packager guest to join", lambda: any(
                player["name"] == name and player["placed"]
                for player in world.call("lan", "status")["guests"]
            ))
            world.commands((
                "/tp @s 12.5 105 -13.5",
                f"/gamemode survival {name}",
                f"/tp {name} 10.5 105 -11.5",
            ))
            world.step_to(world.clock() + 1)
            mp.until("the guest to face the Packager", lambda:
                     actor.call("state")["player"]["position"] == [10.5, 105, -11.5])
        run(world, actor, name, rows, poses)


if __name__ == "__main__":
    main()
