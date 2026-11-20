#!/usr/bin/env python3
"""Replay the pinned Java Nozzle's placement, support drop, recipe and item airflow."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world

craft = import_module("test-machine-crafting")
mp = import_module("test-multiplayer")

NOZZLE = "create:nozzle"
FAN = "create:encased_fan"
OFFSETS = {
    "down": (0, -1, 0), "up": (0, 1, 0), "north": (0, 0, -1),
    "south": (0, 0, 1), "west": (-1, 0, 0), "east": (1, 0, 0),
}
ITEM = '@e[type=minecraft:item,tag=NozzleProbe,limit=1]'
MOB = '@e[type=minecraft:zombie,tag=NozzleMobProbe,limit=1]'


def reference(name):
    with (ROOT / "fixtures" / f"nozzle-{name}-java.csv").open(newline="") as file:
        return list(csv.DictReader(file))


def xyz(values):
    return " ".join(map(str, values))


def add(values, delta):
    return tuple(a + b for a, b in zip(values, delta, strict=True))


def near(a, b):
    return abs(a - b) < 1e-7


def state(control, at):
    return control.call("block", *at)["state"]


def aim(control, point, pos, face=None):
    control.call("look-at", *point)

    def looking():
        hit = control.call("looking-at").get("block") or {}
        return hit if hit.get("pos") == list(pos) and (face is None or hit.get("face") == face) else None

    return mp.until(f"the player to look at {pos} from {face}", looking)


def outline_hit(eye, center, target, boxes):
    direction = tuple(b - a for a, b in zip(eye, center, strict=True))
    first = 1.0
    for box in boxes:
        start, end = 0., 1.
        for axis, step in enumerate(direction):
            start_plane = target[axis] + box[axis] - eye[axis]
            end_plane = target[axis] + box[axis + 3] - eye[axis]
            if step == 0:
                if not start_plane <= 0 <= end_plane:
                    break
                continue
            low, high = sorted((start_plane / step, end_plane / step))
            start, end = max(start, low), min(end, high)
        else:
            if start <= end:
                first = min(first, start)
    assert first < 1.0, (eye, center, target, boxes)
    return add(eye, tuple(first * step for step in direction))


def drop_count(control, at):
    items = control.call("entities", 12, "minecraft:item")["entities"]
    return sum(item["item"]["count"] for item in items
               if item["item"]["item"] == NOZZLE
               and all(abs(value - cell - .5) <= 1.5
                       for value, cell in zip(item["pos"], at, strict=True)))


def verify_shapes(pack):
    with ZipFile(pack) as archive:
        shapes = json.loads(archive.read("data/create/horizon/block/nozzle.json"))
    for row in reference("placement"):
        if row["result"] != "CONSUME":
            continue
        facing = row["facing"]
        outlines = [[int(coord) / 16 for coord in box.split(":")]
                    for box in row["outline_sixteenths"].split("+")]
        for key in ("shapes", "collision_shapes"):
            assert shapes[key]["values"][facing] == outlines, (key, facing)


def placement(host, actor, player, pack):
    verify_shapes(pack)
    drop = {row["facing"]: int(row["dropped_count"]) for row in reference("support-drop")}
    if actor is not host:
        host.commands(("/setblock 4 167 24 minecraft:stone", "/tp @s 4.5 168 24.5"))
    start = host.clock()
    for index, row in enumerate(reference("placement")):
        name = row["clicked_face"]
        face = name if name in OFFSETS else "east"
        offset = OFFSETS[face]
        support = (4 + index * 4, 172, 20)
        target = add(support, offset)
        feet = add(support, (2.5, 2 if face == "up" else -4, .5)) if offset[1] else (
            add(support, (.5 + 3 * offset[0], -1, .5 + 3 * offset[2]))
        )
        floor = (int(feet[0]), int(feet[1]) - 1, int(feet[2]))
        source = "minecraft:stone" if name == "stone" else f"{FAN}[facing={face if name != 'fan_back' else 'west'}]"
        host.commands((
            f"/clear {player}",
            f"/setblock {xyz(support)} {source}",
            f"/setblock {xyz(floor)} minecraft:stone",
            f"/tp {player} {xyz(feet)}",
            f"/item replace entity {player} hotbar.0 with {NOZZLE}",
            f"/item replace entity {player} hotbar.1 with create:wrench",
        ))
        mp.until(f"the {name} placement setup to reach the player", lambda: (
            actor.call("state")["player"]["position"] == list(feet)
            and mp.count(actor, NOZZLE) == 1 and mp.count(actor, "create:wrench") == 1
        ))
        actor.call("select", NOZZLE)
        aim(actor, add(support, (.5, .5, .5)), support, face)
        actor.call("wait", 2)
        actor.call("mouse", "right", "click")
        remaining = int(row["remaining_items"])
        expected = f'{NOZZLE}[facing={row["facing"]}]' if row["result"] == "CONSUME" else "minecraft:air"
        if expected == "minecraft:air":
            actor.call("wait", 6)
        mp.until(f"{name} placement to match Java", lambda: (
            state(host, target) == state(actor, target) == expected
            and mp.count(actor, NOZZLE) == remaining
        ))
        assert host.clock() == start, (name, start, host.clock())
        if row["wrench_result"] == "FAIL":
            center = add(target, (.5, .5, .5))
            hit = aim(actor, center, target)
            eye = actor.call("state")["player"]["eye"]
            shapes = [[int(coord) / 16 for coord in box.split(":")]
                      for box in row["outline_sixteenths"].split("+")]
            expected_point = outline_hit(eye, center, target, shapes)
            axis = next(i for i, step in enumerate(OFFSETS[hit["face"]]) if step)
            assert near(hit["point"][axis], expected_point[axis]), (hit, expected_point)
            # The camera ray uses the game's quantized trigonometry.
            assert all(abs(a - b) < .002 for a, b in zip(hit["point"], expected_point, strict=True)), (hit, expected_point)
            actor.call("select", "create:wrench")
            actor.call("wait", 3)
            actor.call("mouse", "right", "click")
            actor.call("wait", 6)
            assert state(host, target) == expected, (name, state(host, target))
        if face in drop:
            host.command(f"/setblock {xyz(support)} minecraft:air")
            mp.until(f"the detached {face} Nozzle and drop to match Java", lambda: (
                state(host, target) == state(actor, target) == "minecraft:air"
                and drop_count(host, target) == drop[face]
            ))
            assert host.clock() == start, (face, start, host.clock())
        print(f"{name}: Java facing, placement outcome, item use and applicable outline or wrench matched.", flush=True)

    # A Nozzle has no active operation to resume, so persistence is its placed
    # state and support relationship. Exercise that static before/after state
    # across a real world close and reopen.
    if actor is host:
        support = (4, 172, 20)
        target = add(support, OFFSETS["east"])
        host.commands((f"/setblock {xyz(support)} {FAN}[facing=east]",
                       f"/setblock {xyz(target)} {NOZZLE}[facing=east]"))
        expected = f"{NOZZLE}[facing=east]"
        mp.until("the persistence Nozzle to be placed", lambda: state(host, target) == expected)
        host.command("/save-all")
        host.restart()
        mp.until("the placed Nozzle to remain after world reopen", lambda: state(host, target) == expected)
        assert state(host, support) == f"{FAN}[facing=east]"
        print("Placed Nozzle and aligned Fan support survived save/reopen.", flush=True)


def motion(host):
    reply = host.command(f"/data get entity {ITEM} Motion")
    match = re.search(r"\[([^\[\]]+)\]\s*$", reply)
    assert match, reply
    return tuple(float(value.strip().rstrip("dDfF")) for value in match[1].split(","))


def entity_motion(host, selector):
    reply = host.command(f"/data get entity {selector} Motion")
    match = re.search(r"\[([^\[\]]+)\]\s*$", reply)
    assert match, reply
    return tuple(float(value.strip().rstrip("dDfF")) for value in match[1].split(","))


def speed(host, pos):
    reply = host.command(f"/data get block {xyz(pos)} Speed")
    match = re.search(r"(-?[\deE+.]+)f\s*$", reply)
    assert match, reply
    return float(match[1])


def airflow(host, actor, player):
    fan = (11, 172, 20)
    motor = add(fan, (-1, 0, 0))
    nozzle = add(fan, (1, 0, 0))
    wall = add(nozzle, (0, 0, 1))
    center = add(nozzle, (.5, .5, .5))
    host.commands(("/fill 7 172 16 9 172 16 minecraft:stone", "/tp @s 7.5 173 16.5"))
    if actor is not host:
        host.command(f"/tp {player} 9.5 173 16.5")
        mp.until("the guest to reach the airflow fixture", lambda:
                 actor.call("state")["player"]["position"] == [9.5, 173, 16.5])
    for row in reference("airflow"):
        name, rpm, distance = row["scenario"], int(row["rpm"]), float(row["distance"])
        host.commands((
            f"/setblock {xyz(nozzle)} minecraft:air",
            f"/setblock {xyz(fan)} minecraft:air",
            f"/setblock {xyz(motor)} minecraft:air",
            f"/setblock {xyz(motor)} create:creative_motor[facing=east]{{ScrollValue:{rpm}}}",
            f"/setblock {xyz(fan)} {FAN}[facing=east]",
            f"/setblock {xyz(wall)} {'minecraft:stone' if name == 'occluded' else 'minecraft:air'}",
        ))
        start = host.clock()
        for tick in range(1, 4):
            host.step_to(start + tick)
        if rpm:
            assert speed(host, fan) == rpm, (name, speed(host, fan), rpm)
        check_player = name in ("push", "pull")
        if check_player:
            mob_x = center[0] + distance
            host.commands(("/fill 13 171 19 16 171 21 minecraft:stone",
                           f"/tp {player} 7.5 173 16.5"))
            mp.until("the player to reach the Nozzle airflow sample", lambda: (
                (state := actor.call("state")["player"])
                and abs(state["position"][0] - 7.5) < .01
                and abs(state["position"][2] - 16.5) < .01
            ))
        host.command(f"/setblock {xyz(nozzle)} {NOZZLE}[facing=east]")
        start = host.clock()
        host.step_to(start + 1)
        # A ray perpendicular to the Fan's axis isolates Nozzle motion. Its radial
        # acceleration maps the Java X sample to Horizon's Z axis.
        sample = add(center, (0, 0, distance))
        host.command(f'/summon minecraft:item {xyz(sample)} {{NoGravity:1b,PickupDelay:32767s,'
                     'Item:{id:"minecraft:paper",count:1},Motion:[0d,0d,0d],Tags:["NozzleProbe"]}')
        assert motion(host) == (0, 0, 0), name
        mob_sample = add(center, (distance, 0, 0))
        check_mob = name in ("push", "pull")
        if check_mob:
            host.command(f'/summon minecraft:zombie {xyz(mob_sample)} {{NoAI:1b,NoGravity:1b,'
                         'PersistenceRequired:1b,Motion:[0d,0d,0d],Tags:["NozzleMobProbe"]}')
            assert entity_motion(host, MOB) == (0, 0, 0), name
        if actor is not host:
            def guest_paper():
                return next((entry["pos"] for entry in actor.call("entities", 12, "minecraft:item")["entities"]
                             if entry["item"]["item"] == "minecraft:paper"), None)

            mp.until(f"the guest to see the {name} probe at rest", lambda: (
                (at := guest_paper()) is not None and all(abs(a - b) < .01 for a, b in zip(at, sample, strict=True))
            ))
        for tick in range(2, 7):
            host.step_to(start + tick)
            expected = ((float(row["delta_z"]), float(row["delta_y"]), float(row["delta_x"]))
                        if tick == 6 else (0, 0, 0))
            actual = motion(host)
            assert all(near(a, b) for a, b in zip(actual, expected, strict=True)), (name, tick, actual, expected)
            if check_mob:
                mob_expected = ((float(row["delta_x"]) * 4.0, 0.0, 0.0)
                                if tick == 6 else (0.0, 0.0, 0.0))
                mob_actual = entity_motion(host, MOB)
                assert all(near(a, b) for a, b in zip(mob_actual, mob_expected, strict=True)), (
                    name, tick, mob_actual, mob_expected)
        impulse = float(row["delta_x"])
        if actor is not host and impulse:
            mp.until(f"the guest to receive the {name} impulse probe", lambda: guest_paper() is not None)
        if check_player:
            teleport_start = host.clock()
            host.command(f"/tp {player} {mob_x} 172 {center[2]}")
            host.step_to(teleport_start + 1)
            player_before = actor.call("state")["player"]
            for _ in range(12):
                host.step_to(host.clock() + 1)
            player_after = actor.call("state")["player"]
            position = player_after["position"]
            diff = tuple(value - origin for value, origin in zip(position, center, strict=True))
            player_distance = sum(value * value for value in diff) ** .5
            pushing = rpm > 0
            sign = 1.0 if pushing else -1.0
            expected_x = sign * (float(row["range"]) - player_distance) * diff[0] / player_distance / 32.0
            delta_x = player_after["position"][0] - player_before["position"][0]
            assert delta_x * expected_x > 0 and abs(delta_x) >= abs(expected_x) * .25, (
                name, player_before, player_after, expected_x)
            stop_before = player_after
            host.command(f"/setblock {xyz(fan)} minecraft:air")
            previous_velocity = stop_before["velocity"][0]
            for _ in range(6):
                host.step_to(host.clock() + 1)
                stopped = actor.call("state")["player"]
                velocity_delta = stopped["velocity"][0] - previous_velocity
                assert velocity_delta * expected_x < abs(expected_x) * .25, (
                    name, stop_before, stopped, expected_x)
                previous_velocity = stopped["velocity"][0]
            print(f"{name}: player airflow stopped without a new impulse after Fan removal.", flush=True)
        host.command(f"/kill {ITEM}")
        if check_mob:
            host.command(f"/kill {MOB}")
        if check_player:
            host.command(f"/tp {player} 7.5 173 16.5")
        if actor is not host:
            mp.until(f"the guest to receive the {name} probe's removal", lambda: guest_paper() is None)
        coverage = "item impulse"
        if check_mob:
            coverage += ", mob impulse"
        if check_player:
            coverage += ", local player impulse"
        print(f"{name}: Horizon matched the Java {coverage} on the sixth Nozzle tick.", flush=True)


def run(args):
    mode = "LAN" if args.lan else "Solo"
    env = {"HORIZON_NO_AUDIO": "1"}
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, f"Nozzle{mode}", pack=args.pack, render=not args.lan, env=env))
        actor, player = host, "@s"
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            player = "NozzleGuest"
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-nozzle-guest-")))
            actor = stack.enter_context(mp.joined_client(args, scratch, f"127.0.0.1:{port}", player,
                                                         scenario="nozzle", pack=args.pack, render=True, env=env))
            mp.until("the guest to join", lambda: any(guest["name"] == player and guest["placed"]
                                                      for guest in host.call("lan", "status")["guests"]))
        if not args.airflow_only:
            host.command(f"/gamemode survival {player}")
            placement(host, actor, player, args.pack)
        if not args.placement_only:
            airflow(host, actor, player)
    if not args.airflow_only and not args.placement_only and not args.lan:
        with fixture_world(args, "NozzleCrafting", pack=args.pack, render=True, env=env) as host:
            host.commands(("/fill 8 169 22 16 169 28 minecraft:stone",
                           "/setblock 12 170 24 minecraft:crafting_table", "/tp @s 12.5 170 26.5",
                           "/gamemode survival"))
            for row in reference("crafting"):
                craft.replay(host, row)
        print("The original Nozzle recipe was crafted in survival.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    section = parser.add_mutually_exclusive_group()
    section.add_argument("--placement-only", action="store_true")
    section.add_argument("--airflow-only", action="store_true")
    run(parser.parse_args())
