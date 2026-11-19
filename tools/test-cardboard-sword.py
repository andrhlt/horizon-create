#!/usr/bin/env python3
"""Compare real Horizon Cardboard Sword clicks with pinned Java melee."""
import argparse
from collections import defaultdict
import csv
from importlib import import_module
import math
import os
import re
from pathlib import Path
import time
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

placement = import_module("test-package-placement")
package = placement.package
crafting = import_module("test-survival-crafting")
multiplayer = import_module("test-multiplayer")
TARGET = "@e[tag=sword_target,limit=1]"
SWORD = "create:cardboard_sword"
ORIGIN = (8.5, 101.0, 3.5)
CASES = ("pig", "zombie", "enchant", "spider", "spider_wood", "sprint", "sprint_uncharged", "enchant_sprint")
FIELDS = ("health", "x", "y", "z", "vx", "vy", "vz")


def entity_data(host, selector, field):
    reply = host.command(f"/data get entity {selector} {field}".rstrip())
    return reply.split("entity data: ", 1)[1] if "entity data: " in reply else None


def vector(value):
    return tuple(float(entry.strip().removesuffix("d")) for entry in value.strip("[]").split(","))


def sample(host):
    state = entity_data(host, TARGET, "")
    hp = float(re.search(r'\bHealth:\s*([.0-9]+)f', state)[1])
    coordinates = vector(re.search(r'\bPos:\s*(\[[^\]]*\])', state)[1])
    pos = tuple(value - origin for value, origin in zip(coordinates, ORIGIN, strict=True))
    vel = vector(re.search(r'\bMotion:\s*(\[[^\]]*\])', state)[1])
    raw_effects = re.search(r'\bactive_effects:\s*(\[[^\]]*\])', state)
    raw_effects = raw_effects[1] if raw_effects else "[]"
    effects = package.parse(re.sub(r'([,{])\s*([A-Za-z][A-Za-z0-9_]*):', r'\1"\2":', raw_effects))
    slow = next((effect for effect in effects if effect["id"] == "minecraft:slowness"), {})
    return (hp, *pos, *vel, slow.get("duration", 0), slow.get("amplifier", -1))


def playback_trace(peer):
    prefix = "CREATE_ELEVATOR_PLAYBACK create:cardboard_bonk,"
    log = peer.socket.parent / "ctl.log"
    return [line.split(prefix, 1)[1].split(",")
            for line in log.read_text().splitlines() if prefix in line]


def check_bonk_playback(peer, offset, volume, pitch, role):
    def matches():
        records = playback_trace(peer)[offset:]
        return (len(records) == 1 and records[0][0] == "7"
                and list(map(float, records[0][-2:])) == [volume, pitch])
    placement.editor.wait_for(peer, "the original bonk playback parameters", matches)
    record = playback_trace(peer)[offset]
    print(f"{role} heard create:cardboard_bonk, category {record[0]}, volume {record[-2]}, pitch {record[-1]}.", flush=True)


def bonks_heard(peer):
    return peer.call("status")["heard"].get("create:cardboard_bonk", 0)


def aim(actor, kind, yaw):
    x, y, z = ORIGIN
    actor.call("look-at", x, y + (0.8 if kind == "zombie" else 0.42), z)
    def targeted():
        aimed = actor.call("looking-at")
        return aimed["kind"] == "entity" and aimed["entity"]["type"] == f"minecraft:{kind}"
    placement.editor.wait_for(actor, f"the {kind} under the crosshair", targeted)
    rotation = actor.call("state")["player"]
    assert math.isclose(rotation["yaw"] % 360, yaw, abs_tol=0.01), rotation


def attack(actor, host, name, scenario, kind, yaw, row):
    sprint = "sprint" in scenario
    if sprint:
        # Match the original charged threshold using actual client input.
        actor.call("key", "ctrl", "down")
        actor.call("key", "w", "down")
    try:
        if sprint:
            placement.editor.wait_for(actor, "the attacker to sprint", lambda:
                                     actor.call("state")["player"]["sprinting"])
            actor.call("key", "ctrl", "up")
        if scenario == "sprint_uncharged":
            # A slow base stat provides a wide immediate window after a real
            # sword equip. The resulting charge still falls below Java's 0.9.
            host.command(f"/attribute {name} minecraft:attack_speed base set 0.1")
            host.command(f"/item replace entity {name} weapon.mainhand with minecraft:air")
            placement.editor.wait_for(actor, "the hand to become empty", lambda:
                                     not actor.call("inventory")["held"])
            host.command(f"/item replace entity {name} weapon.mainhand with {SWORD}")
            placement.editor.wait_for(actor, "the fresh sword to arrive", lambda:
                                     (actor.call("inventory")["held"] or {}).get("item") == SWORD)
        aim(actor, kind, yaw)
        actor.call("mouse", "left", "click")
        if sprint and row["sounds"]:
            placement.editor.wait_for(actor, "the cardboard swing to stop sprinting", lambda:
                                     not actor.call("state")["player"]["sprinting"])
    finally:
        if sprint:
            actor.call("key", "w", "up")
            actor.call("key", "ctrl", "up")
        if scenario == "sprint_uncharged":
            host.command(f"/attribute {name} minecraft:attack_speed base set 4")


def run_case(host, actor, name, scenario, swing, rows, probe, sound_parameters):
    host.call("command", f"/tp {TARGET} 50 105 50")
    host.call("command", f"/kill {TARGET}")
    host.command("/time set midnight")
    kind = "zombie" if scenario == "zombie" else "spider" if scenario.startswith("spider") else "pig"
    yaw = 90 if kind == "zombie" else 0
    x, y, z = ORIGIN
    reach = 1.7 if kind == "spider" else 2.9 if "sprint" in scenario else 2.0
    attacker = (x + reach, y, z) if yaw else (x, y, z - reach)
    placement.teleport(host, actor, name, attacker)
    item = "minecraft:wooden_sword" if scenario == "spider_wood" else SWORD
    enchanted = scenario.startswith("enchant")
    components = '[minecraft:enchantments={"minecraft:knockback":2}]' if enchanted else ""
    reply = host.command(f"/item replace entity {name} weapon.mainhand with {item}{components}")
    assert "Replaced" in reply, reply
    placement.editor.wait_for(actor, "the melee weapon in the hand", lambda:
                             (actor.call("inventory")["held"] or {}).get("item") == item)
    if enchanted:
        held = entity_data(host, name, "SelectedItem") or entity_data(host, name, "equipment.mainhand")
        assert "minecraft:knockback" in held, held
    hp = float(swing["initial_health"])
    if scenario != "sprint_uncharged":
        for stat in ("attack_damage", "attack_speed"):
            actual = float(host.command(f"/attribute {name} minecraft:{stat} get").split()[-1])
            assert math.isclose(actual, float(swing[stat]), abs_tol=1e-6), (stat, actual, swing)
    host.command(f"/summon minecraft:{kind} {placement.editor.xyz(ORIGIN)} {{PersistenceRequired:1b,Tags:[sword_target]}}")
    host.command(f"/attribute {TARGET} minecraft:movement_speed base set 0")
    host.command(f"/attribute {TARGET} minecraft:follow_range base set 0")
    # Let living entities establish support on the floor before receiving an impulse.
    host.step_to(host.clock() + 1)
    host.step_to(host.clock() + 1)
    assert entity_data(host, TARGET, "OnGround") == "1b", entity_data(host, TARGET, "OnGround")
    assert sample(host)[0] == hp
    aim(actor, kind, yaw)
    actor.call("wait", 14)
    offsets = {peer: (bonks_heard(peer), len(playback_trace(peer))) for peer in dict.fromkeys((host, actor))}
    start = host.clock()
    attack(actor, host, name, scenario, kind, yaw, swing)
    placement.editor.wait_for(host, "the authority to accept the actual mouse attack", lambda:
                             sample(host)[0] != hp or any(sample(host)[i] for i in (4, 6)))
    assert host.clock() == start
    for row in rows:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        actual = sample(host)
        expected = (*(float(row[field]) for field in FIELDS),
                    int(row["slowness"]), int(row["slowness_amplifier"]))
        if probe:
            print(f"{scenario} tick {tick}: Horizon {actual} Java {expected}", flush=True)
            break
        assert all(math.isclose(got, want, abs_tol=8e-6) for got, want in
                   zip(actual, expected, strict=True)), (scenario, tick, expected, actual)
        if tick == 0 and kind == "spider":
            # Isolate normal sword damage from the spider's random retaliation
            # leap after the real hit. The strike and sound have already landed.
            placement.teleport(host, actor, name, (x, y, z - 6))

    if probe:
        return
    held = entity_data(host, name, "equipment.mainhand")
    if held is None:
        held = entity_data(host, name, "SelectedItem")
    assert held is not None, scenario
    damage = package.parse(held).get("components", {}).get("minecraft:damage", 0)
    assert damage == int(swing["damage"]), (scenario, held)
    expected_count = int(bool(swing["sounds"]))
    for peer, (heard, log_offset) in offsets.items():
        if expected_count:
            placement.editor.wait_for(peer, "the original bonk to play", lambda:
                                      bonks_heard(peer) - heard == expected_count)
        else:
            assert bonks_heard(peer) == heard
        if sound_parameters and expected_count:
            _, _, volume, pitch = swing["sounds"].split("|")
            role = "Host" if peer is host else "Guest"
            check_bonk_playback(peer, log_offset, float(volume), float(pitch), role)
    print(f"{scenario}: {len(rows)} Java motion, damage and slowness rows", flush=True)


def craft(host, actor, name):
    table = (7, 101, 2)
    host.commands((
        f"/clear {name}",
        "/setblock 7 101 2 minecraft:crafting_table",
        f"/item replace entity {name} hotbar.0 with create:cardboard 2",
        f"/item replace entity {name} hotbar.1 with minecraft:stick",
    ))
    placement.teleport(host, actor, name, (7.5, 101.0, 4.5))
    multiplayer.until("the original two Cardboard ingredients", lambda:
                     multiplayer.count(actor, "create:cardboard") == 2)
    actor.call("interact", *table, "up")
    crafting.distribute(actor, 0, (101, 104))
    crafting.distribute(actor, 1, (107,))
    crafting.output(actor, SWORD, 1)
    actor.call("click-slot", 200, "shift")
    multiplayer.until("the survival-crafted Cardboard Sword", lambda: multiplayer.count(actor, SWORD) == 1)
    assert multiplayer.count(actor, "create:cardboard") == 0
    assert multiplayer.count(actor, "minecraft:stick") == 0
    actor.call("close")
    host.command("/setblock 7 101 2 minecraft:air")
    print("The original survival recipe consumed two Cardboard and one wooden rod.", flush=True)


def anvil(host, actor, name):
    at = (7, 101, 2)
    host.commands((
        "/setblock 7 101 2 minecraft:anvil",
        f"/experience set {name} 30 levels",
    ))
    placement.teleport(host, actor, name, (7.5, 101.0, 4.5))
    cases = {
        "knockback": ('{"minecraft:knockback":2}', True),
        "sharpness": ('{"minecraft:sharpness":1}', False),
        "mixed": ('{"minecraft:knockback":2,"minecraft:sharpness":1}', False),
    }
    def current_slots():
        return {entry["slot"]: entry["stack"] for entry in actor.call("menu")["slots"]}
    for scenario, (enchantments, produces_sword) in cases.items():
        host.commands((
            f"/clear {name}",
            f"/item replace entity {name} hotbar.0 with {SWORD}",
            f"/item replace entity {name} hotbar.1 with minecraft:enchanted_book"
            f"[minecraft:stored_enchantments={enchantments}]",
        ))
        placement.editor.wait_for(actor, "the sword and book in inventory", lambda:
                                  multiplayer.count(actor, SWORD) == 1
                                  and multiplayer.count(actor, "minecraft:enchanted_book") == 1)
        actor.call("interact", *at, "up")
        actor.call("click-slot", 0)
        actor.call("click-slot", 600)
        actor.call("click-slot", 1)
        actor.call("click-slot", 601)
        placement.editor.wait_for(actor, "both original anvil inputs", lambda:
                                  600 in current_slots() and 601 in current_slots())
        if produces_sword:
            placement.editor.wait_for(actor, "the Knockback II anvil result", lambda:
                current_slots().get(650, {}).get("enchantments") == [["minecraft:knockback", 2]])
            assert current_slots()[650]["item"] == SWORD
        else:
            actor.call("wait", 8)
            assert 650 not in current_slots(), (scenario, current_slots())
        actor.call("close")
        print(f"{scenario}: original enchantment-book acceptance matched.", flush=True)


def block(host, actor, name, sound_parameters):
    pos = (8, 101, 3)
    placement.teleport(host, actor, name, (8.5, 101, 1.5))
    host.commands((
        f"/setblock {placement.editor.xyz(pos)} minecraft:stone",
        f"/item replace entity {name} weapon.mainhand with {SWORD}",
    ))
    placement.editor.wait_for(actor, "the sword in the hand", lambda:
                             (actor.call("inventory")["held"] or {}).get("item") == SWORD)
    actor.call("look-at", 8.5, 101.5, 3.5)
    placement.editor.wait_for(actor, "the stone under the crosshair", lambda:
                             actor.call("looking-at")["kind"] == "block")
    offsets = {peer: (bonks_heard(peer), len(playback_trace(peer))) for peer in dict.fromkeys((host, actor))}
    actor.call("mouse", "left", "down")
    try:
        actor.call("wait", 6)
    finally:
        actor.call("mouse", "left", "up")
    for peer, (heard, log_offset) in offsets.items():
        placement.editor.wait_for(peer, "the block-start bonk", lambda: bonks_heard(peer) == heard + 1)
        if sound_parameters:
            role = "Host" if peer is host else "Guest"
            check_bonk_playback(peer, log_offset, 0.5, 1.85, role)
    print("Exactly one bonk on the original left-click-block start.", flush=True)


def fuel(host, actor, name):
    recycle = import_module("test-window-recycling")
    at = (8, 101, 3)
    coordinates = placement.editor.xyz(at)
    placement.teleport(host, actor, name, (8.5, 101.0, 1.5))
    host.commands((
        f"/setblock {coordinates} minecraft:furnace",
        f"/item replace block {coordinates} container.0 with minecraft:raw_iron",
        f"/item replace entity {name} hotbar.0 with {SWORD}",
    ))
    placement.editor.wait_for(actor, "the sword in the inventory", lambda:
                             (actor.call("inventory")["held"] or {}).get("item") == SWORD)
    actor.call("interact", *at, "north")
    actor.call("click-slot", 0)
    actor.call("click-slot", 301)
    placement.editor.wait_for(actor, "the sword in the furnace's fuel slot", lambda:
        any(slot["slot"] == 301 and (slot["stack"] or {}).get("item") == SWORD
            for slot in actor.call("menu")["slots"]))
    start = host.clock()
    for tick in range(4):
        if tick:
            host.step_to(start + tick)
        witness = host.command(f"/data get block {coordinates}")
        row = recycle.read_furnace(tick, SWORD, witness, "")
        fuel_count = int(SWORD in witness)
        expected_burn = 1001 - tick if tick else 0
        assert row[2:5] == (str(tick), "200", str(expected_burn)), row
        assert fuel_count == int(tick == 0), witness
    host.command("/tick step 197")
    end = time.monotonic() + 25
    while host.clock() < start + 200:
        if time.monotonic() > end:
            raise AssertionError("The furnace never received 200 world ticks.")
        time.sleep(0.1)
    assert host.clock() == start + 200
    placement.editor.wait_for(actor, "the smelted output in the menu", lambda:
        any(slot["slot"] == 302 and (slot["stack"] or {}).get("item") == "minecraft:iron_ingot"
            for slot in actor.call("menu")["slots"]))
    row = recycle.read_furnace(200, SWORD, host.command(f"/data get block {coordinates}"), "")
    assert row[2:5] == ("0", "200", "801"), row
    actor.call("click-slot", 302, "shift")
    placement.editor.wait_for(actor, "the iron ingot claimed by the player", lambda:
                             multiplayer.count(actor, "minecraft:iron_ingot") == 1)
    print("The sword burned for the original 1,000-tick budget and smelted iron at tick 200.", flush=True)


def main():
    os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ("ctl", "client", "resources"):
        parser.add_argument(parameter, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--case", choices=CASES, action="append")
    parser.add_argument("--probe-baseline", action="store_true")
    parser.add_argument("--craft-only", action="store_true")
    parser.add_argument("--anvil-only", action="store_true")
    parser.add_argument("--block-only", action="store_true")
    parser.add_argument("--fuel-only", action="store_true")
    parser.add_argument("--sound-parameters", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures" / "cardboard-sword-swings-java.csv").open(newline="") as stream:
        swings = {row["case"]: row for row in csv.DictReader(stream)}
    frames = defaultdict(list)
    with (ROOT / "fixtures" / "cardboard-sword-targets-java.csv").open(newline="") as stream:
        for row in csv.DictReader(stream):
            frames[row["case"]].append(row)
    cases = args.case or CASES
    expected_world = "CardboardSwordLAN" if args.lan else "CardboardSwordSolo"
    with TemporaryDirectory(prefix="hc-sword-") as directory:
        with fixture_world(args, expected_world, render=True, pack=args.pack) as host:
            host.commands((
                "/fill 0 100 -13 25 100 21 minecraft:stone",
                "/fill 0 101 -13 25 107 21 minecraft:air",
            ))
            with package.filters.actor_for(host, args, Path(directory) if args.lan else None) as (actor, name):
                host.command(f"/gamemode survival {name}")
                if args.craft_only:
                    craft(host, actor, name)
                    return
                if args.anvil_only:
                    anvil(host, actor, name)
                    return
                if args.block_only:
                    block(host, actor, name, args.sound_parameters)
                    return
                if args.fuel_only:
                    fuel(host, actor, name)
                    return
                for scenario in cases:
                    run_case(host, actor, name, scenario, swings[scenario], frames[scenario],
                             args.probe_baseline, args.sound_parameters)
    if not args.probe_baseline:
        print(f"Matched {sum(len(frames[case]) for case in cases)} Java Cardboard Sword target samples.")

if __name__ == "__main__":
    main()
