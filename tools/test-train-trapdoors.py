#!/usr/bin/env python3
"""Replay the original Train Trapdoor and Framed Glass Trapdoor through Horizon."""

import argparse
from collections import Counter
from contextlib import ExitStack
import csv
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world

craft = import_module("test-machine-crafting")
mp = import_module("test-multiplayer")
nozzle = import_module("test-nozzle")

PROPERTIES = ("facing", "half", "open", "powered", "waterlogged")


def reference(name):
    with (ROOT / "fixtures" / f"train-trapdoors-{name}-java.csv").open(newline="") as file:
        return list(csv.DictReader(file))


def state(row):
    return f'{row["id"]}[' + ",".join(f"{key}={row[key]}" for key in PROPERTIES) + "]"


def xyz(at):
    return nozzle.xyz(at)


def prepare_actor(host, actor, player, feet):
    floor = (int(feet[0]), int(feet[1]) - 1, int(feet[2]))
    host.commands((f"/setblock {xyz(floor)} minecraft:stone", f"/tp {player} {xyz(feet)}"))
    mp.until("the player to reach the trapdoor fixture", lambda:
             actor.call("state")["player"]["position"] == list(feet))


def wait_for_state(host, actor, where, row):
    expected = state(row)
    try:
        mp.until(f"both players to see {where} become {expected}", lambda:
                 nozzle.state(host, where) == nozzle.state(actor, where) == expected, seconds=5)
    except RuntimeError as error:
        raise AssertionError((row, nozzle.state(host, where), nozzle.state(actor, where))) from error


def defaults(host, pack):
    with ZipFile(pack) as archive:
        for index, row in enumerate(reference("defaults")):
            name = row["id"].removeprefix("create:")
            path = f"data/create/horizon/block/{name}.json"
            definition = json.loads(archive.read(path))
            assert definition["template"] == "minecraft:oak_trapdoor", (name, definition["template"])
            properties = definition["properties"]
            assert properties["hardness"] == float(row["hardness"]), row
            assert properties["explosion_resistance"] == float(row["resistance"]), row
            assert properties["map_color"] == int(row["map_color"]), row
            at = (7 + index * 4, 172, 22)
            host.command(f'/setblock {xyz(at)} {row["id"]}')
            mp.until(f"the default {name} block to load", lambda: nozzle.state(host, at) == state(row))
            assert "No items were found" in host.command(f'/clear @s {row["id"]} 0'), row
    for recipe in dict.fromkeys(row["recipe"] for row in reference("crafting")):
        reply = host.command(f"/recipe give @s {recipe}")
        assert "Unlocked" in reply or "No new recipes were learned" in reply, reply
    print("Both original trapdoor IDs, default states, block properties and recipe IDs matched.", flush=True)


def placement(host, actor, player):
    for index, row in enumerate(reference("placement")):
        name = row["placement"]
        block = row["id"]
        x, y, z = 7 + (index % 6) * 6, 172, 31 + (index // 6) * 8
        support = (x, y, z)
        if name.startswith("side_"):
            face = "east"
            feet = (x + 3.5, y - 1, z + .5)
            aim = (x + 1, y + (.25 if name == "side_low" else .75), z + .5)
        elif name == "ceiling":
            face = "down"
            feet = (x + .5, y - 2, z + 2.5)
            aim = (x + .5, y, z + .5)
        else:
            face = "up"
            feet = (x + .5, y + (3 if name == "powered_floor" else 1), z + 2.5)
            aim = (x + .5, y + 1, z + (.125 if name == "powered_floor" else .5))
        at = nozzle.add(support, nozzle.OFFSETS[face])
        host.commands((
            f"/setblock {xyz(support)} minecraft:stone",
            f"/setblock {xyz(at)} {'minecraft:water' if name == 'wet_floor' else 'minecraft:air'}",
            f"/clear {player}",
            f"/item replace entity {player} hotbar.0 with {block}",
        ))
        signal = nozzle.add(at, (0, 0, 1))
        if name == "powered_floor":
            host.command(f"/setblock {xyz(signal)} minecraft:redstone_block")
        prepare_actor(host, actor, player, feet)
        mp.until(f"the player to receive the {block}", lambda: mp.count(actor, block) == 1)
        actor.call("select", block)
        hit = nozzle.aim(actor, aim, support, face)
        assert all(abs(a - b) < .004 for a, b in zip(hit["point"], aim, strict=True)), (row, hit, aim)
        actor.call("wait", 2)
        actor.call("mouse", "right", "click")
        wait_for_state(host, actor, at, row)
        mp.until(f"the {name} trapdoor to be used from the hotbar", lambda:
                 mp.count(actor, block) == int(row["item_count"]))
        if name == "floor":
            host.command(f"/setblock {xyz(support)} minecraft:air")
            host.step_to(host.clock() + 1)
            expected = state(row)
            assert nozzle.state(host, at) == expected and nozzle.state(actor, at) == expected, (
                "Java TrainTrapdoorBlock inherits TrapDoorBlock.updateShape, which does not require support",
                block, nozzle.state(host, at), nozzle.state(actor, at),
            )
            print(f"{block}: removing the placement block left the trapdoor in place.", flush=True)
        start = host.clock()
        assert host.clock() == start, (row, start, host.clock())
        print(f"{block} {name}: placement state and item use matched Java.", flush=True)


def heard_trapdoors(control):
    return Counter({identifier: count for identifier, count in control.call("status")["heard"].items()
                    if "trapdoor" in identifier})

def transition(host, actor, player, sound):
    rows = reference("transition")
    audio = {(row["id"], row["step"]): row for row in reference("sounds")} if sound else {}
    for index, block in enumerate(dict.fromkeys(row["id"] for row in rows)):
        rig = [row for row in rows if row["id"] == block]
        at = (7 + index * 7, 172, 21)
        x, y, z = at
        signal = nozzle.add(at, (0, 0, 1))
        host.commands((f"/clear {player}", f"/setblock {xyz(nozzle.add(at, (0, -1, 0)))} minecraft:stone"))
        prepare_actor(host, actor, player, (x + .5, y, z - 2.5))
        mp.until("the trapdoor player’s hand to empty", lambda: not actor.call("inventory")["held"])
        start = host.clock()
        previous = rig[0]
        heard = heard_trapdoors(actor) if sound else Counter()
        for row in rig:
            action = row["action"]
            if action == "default":
                host.command(f"/setblock {xyz(at)} {block}")
            elif action == "power_on":
                host.command(f"/setblock {xyz(signal)} minecraft:redstone_block")
            elif action == "power_off":
                host.command(f"/setblock {xyz(signal)} minecraft:air")
            elif action == "waterlog":
                # Java's fixture only sets this state. Placement exercises acquiring water from a source.
                host.command(f"/setblock {xyz(at)} {state(row)}")
            else:
                top = .6 if previous["open"] == "true" else .09
                target = (x + .5, y + top, z + .9)
                nozzle.aim(actor, target, at)
                actor.call("wait", 2)
                actor.call("mouse", "right", "click")
            wait_for_state(host, actor, at, row)
            if (block, row["tick"]) in audio:
                audio_row = audio[block, row["tick"]]
                assert audio_row["action"] == action
                event = audio_row["sound"]
                expected = Counter() if event == "-" else Counter(event.split("|"))
                if expected:
                    mp.until(f"{block} playback at step {row['tick']}", lambda:
                             (heard_trapdoors(actor) - heard).total() >= expected.total())
                actor.call("wait", 3)
                sounds = heard_trapdoors(actor)
                assert sounds - heard == expected, (audio_row, sounds - heard)
                heard = sounds
            assert host.clock() == start, (row, start, host.clock())
            previous = row
        print(f"{block}: default and nine ordered Java open, powered and waterlogged snapshots matched.", flush=True)
        if sound:
            print(f"{block}: matched the seven original iron trapdoor sound events and two silent steps.", flush=True)


def crafting(args, env):
    with fixture_world(args, "TrainTrapdoorCraft", render=True, pack=args.pack, env=env) as host:
        host.commands(("/fill 8 169 22 16 169 28 minecraft:stone",
                       "/setblock 12 170 24 minecraft:crafting_table", "/tp @s 12.5 170 26.5",
                       "/gamemode survival"))
        for order in (False, True):
            for row in reference("crafting"):
                inputs = row["inputs"].split("|")
                if order:
                    inputs.reverse()
                craft.replay(host, {**row, "slots": ",".join(inputs), "remainder": ""})
    print("Both original shapeless recipes matched in both slot orders with all 11 original wood types.")


def run(args):
    env = {"HORIZON_NO_AUDIO": "1"}
    if not args.crafting_only:
        with ExitStack() as stack:
            mode = "LAN" if args.lan else "Solo"
            host = stack.enter_context(fixture_world(args, f"TrainTrapdoors{mode}", render=not args.lan,
                                                     pack=args.pack, env=env))
            actor, player = host, "@s"
            if args.lan:
                port = host.call("lan", "open", "0", "commands", "force")["port"]
                player = "TrapdoorGuest"
                scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-trapdoors-guest-")))
                actor = stack.enter_context(mp.joined_client(args, scratch, f"127.0.0.1:{port}", player,
                                                             scenario="train-trapdoors", pack=args.pack,
                                                             render=True, env=env))
                mp.until("the trapdoor guest to join", lambda: any(guest["name"] == player and guest["placed"]
                         for guest in host.call("lan", "status")["guests"]))
            host.command(f"/gamemode survival {player}")
            defaults(host, args.pack)
            if not args.transitions_only:
                placement(host, actor, player)
            if not args.placement_only:
                transition(host, actor, player, args.sound)
    if not any((args.lan, args.placement_only, args.transitions_only)):
        crafting(args, env)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--sound", action="store_true", help="compare muted toggle playback to the Java event trace")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--placement-only", action="store_true")
    mode.add_argument("--transitions-only", action="store_true")
    mode.add_argument("--crafting-only", action="store_true")
    run(parser.parse_args())
