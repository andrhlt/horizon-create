#!/usr/bin/env python3
"""Replay Java Stock Link placement, redstone and support removal in Horizon."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import json

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
placement = import_module("test-clipboard-placement")
packager = import_module("test-packager-redstone")

LINK = "create:stock_link"


def offset(position, direction):
    return tuple(cell + step for cell, step in zip(position, direction, strict=True))


def place(host, actor, player, support, direction, side, row):
    feet = (support[0] + .5 + 2 * direction[0], 171, support[2] + .5 + 2 * direction[2])
    if side in ("down", "up"):
        feet = (feet[0], feet[1], feet[2] - 2)
    host.commands((
        f"/item replace entity {player} hotbar.0 with {LINK}",
        f"/tp {player} {placement.coords(feet)}",
    ))
    multiplayer.until(f"the player to approach the {side} face with a Stock Link", lambda: (
        actor.call("state")["player"]["position"] == list(feet)
        and multiplayer.count(actor, LINK) == 1
    ))
    actor.call("select", LINK)
    aim = tuple(cell + .5 + step * .5 for cell, step in zip(support, direction, strict=True))
    actor.call("look-at", *aim)
    multiplayer.until(f"the player to aim at the {side} face", lambda:
                      placement.ray_hit(actor, support, side))
    actor.call("wait", 3)
    actor.call("mouse", "right", "click")
    target = offset(support, direction)
    try:
        multiplayer.until(f"the {side} Stock Link placement", lambda:
                          host.call("block", *target)["state"] == row["state"], seconds=6)
    except RuntimeError as error:
        raise AssertionError((row["state"], host.call("block", *target),
                              actor.call("looking-at"), actor.call("inventory"))) from error
    multiplayer.until("the placed Stock Link and consumed item to synchronize", lambda: (
        actor.call("block", *target)["state"] == row["state"]
        and multiplayer.count(actor, LINK) == 0
    ))

    bounds = [float(row[f"{edge}_{axis}"]) for edge in ("min", "max") for axis in "xyz"]
    hit_point = tuple(cell + (bounds[i] + bounds[i + 3]) / 2 for i, cell in enumerate(target))
    actor.call("look-at", *hit_point)
    axis = next(i for i, step in enumerate(direction) if step)
    plane = target[axis] + bounds[axis + 3 * int(direction[axis] > 0)]

    def hits_outline():
        hit = placement.ray_hit(actor, target, side)
        return hit and abs(hit["point"][axis] - plane) < 1e-5

    multiplayer.until(f"the {side} hit to match the Java outline", hits_outline)


def replay(host, actor, player, rows, block_definition):
    sides = tuple(row["side"] for row in rows if row["phase"] == "placed")
    supports = {side: (7 + 5 * i, {"down": 175, "up": 170}.get(side, 172), 20)
                for i, side in enumerate(sides)}
    host.command("/fill 3 170 15 38 170 25 minecraft:stone")
    for side, support in supports.items():
        host.command(f"/setblock {placement.coords(support)} minecraft:redstone_block")
    for row in rows:
        if row["phase"] == "placed" and "waterlogged=true" in row["state"]:
            target = offset(supports[row["side"]], placement.FACE_OFFSETS[row["side"]])
            host.command(f"/setblock {placement.coords(target)} minecraft:water")

    origin = host.clock() - 1
    for row in rows:
        expected_tick = origin + int(row["tick"])
        if host.clock() != expected_tick:
            host.step_to(expected_tick)
        side, phase = row["side"], row["phase"]
        support = supports[side]
        direction = placement.FACE_OFFSETS[side]
        target = offset(support, direction)
        if phase == "placed":
            place(host, actor, player, support, direction, side, row)
        elif phase == "unsupported":
            host.command(f"/setblock {placement.coords(support)} minecraft:air")
        else:
            signal = offset(target, direction)
            block = "minecraft:redstone_block" if phase == "powered" else "minecraft:air"
            host.command(f"/setblock {placement.coords(signal)} {block}")

        assert host.clock() == expected_tick
        actual = host.call("block", *target)["state"]
        assert actual == row["state"], (row["tick"], side, phase, actual, row["state"])
        properties = dict(field.split("=") for field in actual.split("[")[1][:-1].split(","))
        key = f'{properties["face"]},{properties["facing"]}'
        bounds = [float(row[f"{edge}_{axis}"]) for edge in ("min", "max") for axis in "xyz"]
        assert block_definition["collision_shapes"]["values"][key] == [bounds]
        multiplayer.until(f"the {side} Stock Link to synchronize after {phase}", lambda:
                          actor.call("block", *target)["state"] == row["state"])
        print(f'{row["tick"]} {side} {phase}: {actual}')


def replay_packager(host, actor, rows):
    machine = (8, 105, -12)
    storage = offset(machine, (-1, 0, 0))
    link = offset(machine, (0, 1, 0))
    link_signal = offset(link, (0, 1, 0))
    machine_signal = offset(machine, (1, 0, 0))
    fmt = placement.coords
    schedule = {
        2: (f"/setblock {fmt(storage)} minecraft:barrel",
            f"/item replace block {fmt(storage)} container.0 with minecraft:iron_ingot 12",
            f"/setblock {fmt(machine)} create:packager[facing=east]"),
        3: (f"/setblock {fmt(link)} {LINK}",),
        5: (f"/setblock {fmt(machine_signal)} minecraft:redstone_block",),
        6: (f"/setblock {fmt(machine_signal)} minecraft:air",
            f"/setblock {fmt(link_signal)} minecraft:target",
            f"/setblock {fmt(link_signal)} minecraft:target[power=7]"),
        8: (f"/setblock {fmt(link_signal)} minecraft:redstone_block",),
        10: (f"/setblock {fmt(link_signal)} minecraft:air",),
        12: (f"/setblock {fmt(link)} minecraft:air",),
        14: (f"/setblock {fmt(machine_signal)} minecraft:redstone_block",),
        15: (f"/setblock {fmt(machine_signal)} minecraft:air",),
    }
    host.command("/tp @s 10.5 105 -10.5")
    origin = host.clock() - 2
    fields = ("linked", "link_present", "link_powered", "link_strength", "packager_powered",
              "stored_ingots", "held_package")
    failures = []
    for row in rows:
        tick = int(row["tick"])
        expected_tick = origin + tick
        if host.clock() != expected_tick:
            host.step_to(expected_tick)
        for command in schedule.get(tick, ()):
            host.command(command)
        expected_machine = (f'create:packager[facing=east,linked={row["linked"]},'
                            f'powered={row["packager_powered"]}]')
        expected_link = (f'{LINK}[face=floor,facing=north,powered={row["link_powered"]},waterlogged=false]'
                         if row["link_present"] == "true" else "minecraft:air")
        try:
            multiplayer.until(f"the Java block states to reach the host at tick {tick}", lambda: (
                host.call("block", *machine)["state"] == expected_machine
                and host.call("block", *link)["state"] == expected_link
            ), seconds=1.5)
        except RuntimeError:
            pass
        machine_state = host.call("block", *machine)["state"]
        link_state = host.call("block", *link)["state"]
        link_present = link_state.startswith(LINK)
        machine_data = packager.block_data(host, machine)
        stock = packager.block_value(host, storage, "Items")
        actual = (
            str("linked=true" in machine_state).lower(),
            str(link_present).lower(),
            str("powered=true" in link_state).lower(),
            packager.block_value(host, link, "Power") if link_present else "-1",
            str("powered=true" in machine_state).lower(),
            str(packager.number(stock, "(?:[cC]ount)")),
            str("HeldBox:" in machine_data).lower(),
        )
        wanted = tuple(row[field] for field in fields)
        if actual != wanted:
            failures.append((tick, dict(zip(fields, actual, strict=True)), dict(zip(fields, wanted, strict=True))))
        assert host.clock() == expected_tick
        print(tick, ",".join(actual), flush=True)
        if actor is not host and actual == wanted:
            multiplayer.until(f"the Stock Link and Packager to synchronize at Java tick {tick}", lambda: (
                actor.call("block", *machine)["state"] == machine_state
                and actor.call("block", *link)["state"] == link_state
            ))
    assert not failures, failures


def uuid_array(data):
    match = re.search(r"\[I;\s*((?:-?\d+\s*,\s*){3}-?\d+)\s*\]", data)
    return tuple(map(int, match[1].split(","))) if match else None


def replay_tuning(host, actor, player, rows, screenshots):
    first, second = (10, 171, 20), (13, 171, 20)
    fmt = placement.coords
    host.command("/fill 7 170 16 16 170 23 minecraft:smooth_stone")
    owner = uuid_array(host.command(f"/data get entity {player} UUID"))
    assert owner is not None

    def held():
        return actor.call("inventory")["held"] or {}

    def give_link():
        host.command(f"/item replace entity {player} hotbar.0 with {LINK}")
        multiplayer.until("an untuned Stock Link in hand", lambda: (
            held().get("item") == LINK and not held().get("components")
        ))
        actor.call("select", LINK)

    def click(target, *, block_under=False):
        x, y, z = target
        feet = (x + .5, y, z - 1.5)
        host.command(f"/tp {player} {fmt(feet)}")
        multiplayer.until("the player to reach the Stock Link", lambda:
                          actor.call("state")["player"]["position"] == list(feet))
        support = offset(target, (0, -1, 0))
        if block_under:
            actor.call("look-at", x + .5, y, z + .5)
            hit = lambda: placement.ray_hit(actor, support, "up")
        else:
            actor.call("look-at", x + .5, y + .18, z + .5)
            hit = lambda: (actor.call("looking-at").get("block") or {}).get("pos") == list(target)
        multiplayer.until("the aim to reach the intended block", hit)
        actor.call("wait", 4)
        actor.call("mouse", "right", "click")

    def section(at, field):
        return uuid_array(packager.block_value(host, at, field))

    def look_to_sky():
        x, y, z = first
        actor.call("look-at", x + .5, y + 15, z - 1.5)
        multiplayer.until("the player to look into open air", lambda:
                          not actor.call("looking-at").get("block"))

    def save_image(name):
        if screenshots:
            look_to_sky()
            actor.call("wait", 5)
            actor.call("screenshot", screenshots / f"{name}.png")

    origin = host.clock() - 2
    original_freq = None
    messages = {
        "new": "New link network started",
        "tune": "Tuned to this network",
        "place": "Connected to existing network successfully",
        "clear": "Cleared connection to network",
    }
    for row in rows:
        tick, action = row["tick"], row["action"]
        now = origin + tick
        if host.clock() != now:
            host.step_to(now)
        if action == "new":
            give_link()
            click(first, block_under=True)
            multiplayer.until("the original Stock Link to be placed and spent", lambda: (
                actor.call("block", *first)["state"].startswith(LINK) and not held()
            ))
            original_freq = section(first, "Freq")
            assert original_freq is not None
            assert (section(first, "PlacedBy") == owner) == row["player_recorded"]
        elif action == "tune":
            give_link()
            click(first)
            try:
                multiplayer.until("the held Stock Link to receive the block frequency", lambda:
                                  uuid_array(held().get("components") or "") == original_freq, seconds=5)
            except RuntimeError as error:
                raise AssertionError((original_freq, held(), actor.call("looking-at"),
                                      host.command(f"/data get entity {player} SelectedItem"),
                                      host.command(f"/data get block {fmt(first)}"))) from error
            item = held()
            assert item["count"] == row["held_count"]
            assert re.search(r'id"?:\s*"create:packager_link"', item["components"]), item["components"]
            assert "minecraft:enchantment_glint_override" not in item["components"]
            assert uuid_array(host.command(f"/data get entity {player} SelectedItem")) == original_freq
            save_image("tuned")
        elif action == "place":
            click(second, block_under=True)
            multiplayer.until("the tuned Stock Link to be placed and spent", lambda: (
                actor.call("block", *second)["state"].startswith(LINK) and not held()
            ))
            assert (section(second, "Freq") == original_freq) == row["matches_original_frequency"]
            assert (section(second, "PlacedBy") == owner) == row["player_recorded"]
        elif action == "clear":
            give_link()
            click(first)
            multiplayer.until("the held Stock Link to tune before clearing", lambda:
                              uuid_array(held().get("components") or "") == original_freq)
            look_to_sky()
            actor.call("wait", 4)
            actor.call("mouse", "right", "click")
            multiplayer.until("the held Stock Link to clear its frequency", lambda: (
                held().get("item") == LINK and not held().get("components")
            ))
            assert held()["count"] == row["held_count"]
            assert uuid_array(host.command(f"/data get entity {player} SelectedItem")) is None
            save_image("cleared")
        multiplayer.until(f"the {action} action bar message", lambda:
                          actor.call("messages").get("actionbar") == messages[action])
        assert host.clock() == now
        print(f"{tick} {action}: Java Stock Link item and block frequency state matched.")
    click(first)
    multiplayer.until("the held Stock Link to tune before crafting", lambda:
                      uuid_array(held().get("components") or "") == original_freq)
    crafting = import_module("test-survival-crafting")
    actor.call("key", "e", "tap")
    multiplayer.until("the survival inventory crafting grid", lambda:
                      actor.call("state")["screen"] == "inventory")
    crafting.distribute(actor, 0, [100])
    crafting.output(actor, LINK, 1)
    actor.call("click-slot", 200, "shift")
    multiplayer.until("the crafted Stock Link to reach the inventory", lambda:
                      multiplayer.count(actor, LINK) == 1)
    actor.call("close")
    actor.call("select", LINK)
    multiplayer.until("the crafting grid to return an untuned Stock Link", lambda: (
        held().get("item") == LINK and not held().get("components")
    ))
    assert multiplayer.count(actor, LINK) == 1
    assert host.clock() == now
    print("The original one-item recipe cleared the tuned Stock Link.")


def run(args):
    if args.tuning:
        rows = json.loads((ROOT / "fixtures/stock-link-tuning-java.json").read_text())
    else:
        fixture = "stock-link-packager-java.csv" if args.packager else "stock-link-java.csv"
        with (ROOT / "fixtures" / fixture).open() as file:
            rows = list(csv.DictReader(file))
    with ZipFile(args.pack) as pack:
        block_definition = json.loads(pack.read("data/create/horizon/block/stock_link.json"))
    mode = "Lan" if args.lan else "Solo"
    env = {"HORIZON_NO_AUDIO": "1"}
    with ExitStack() as resources:
        host = resources.enter_context(fixture_world(
            args, "StockLink" + ("Packager" if args.packager else "Tuning" if args.tuning else "") + mode,
            pack=args.pack, render=not args.lan and not args.packager, env=env,
        ))
        actor, player = host, "@s"
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            player = "StockLinkGuest"
            scratch = Path(resources.enter_context(TemporaryDirectory(prefix="hc-stock-link-")))
            actor = resources.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, scenario="stock-link-packager" if args.packager else "stock-link-tuning" if args.tuning else "stock-link",
                pack=args.pack, render=not args.packager, env=env,
            ))
            multiplayer.until("the Stock Link guest to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]
            ))
            host.command("/tp @s 4.5 171 18.5")
            if args.packager:
                host.command(f"/tp {player} 10.5 105 -10.5")
        if args.packager:
            replay_packager(host, actor, rows)
        else:
            host.command(f"/gamemode survival {player}")
            if args.tuning:
                if args.screenshots:
                    args.screenshots.mkdir(parents=True, exist_ok=True)
                replay_tuning(host, actor, player, rows, args.screenshots)
            else:
                replay(host, actor, player, rows, block_definition)
    print(f"{mode} matched {len(rows)} Java Stock Link snapshots.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--packager", action="store_true")
    scope.add_argument("--tuning", action="store_true")
    parser.add_argument("--screenshots", type=Path)
    run(parser.parse_args())
