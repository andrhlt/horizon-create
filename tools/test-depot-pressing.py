#!/usr/bin/env python3
"""Compare a powered press and depot through two stamping cycles in Horizon."""

import argparse
import csv
from importlib import import_module
import os
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/wheat_milling.nbt")
PRESS = "5 106 -11"
MOTOR = "4 106 -11"
DEPOT = "5 104 -11"


def scalar(nbt, key, default=0):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", nbt)
    return int(float(match[1])) if match else default


def item_counts(tag, ingot, sheet):
    ingots = held = buffered = 0
    # Individual stacks in the engine's Items list have one Slot each.
    items = re.search(r"\bItems: \[([^\]]*)\]", tag)
    if items:
        for stack in re.findall(r"\{([^{}]*)\}", items[1]):
            slot = scalar(stack, "Slot", -1)
            count = scalar(stack, "count", 1)
            if slot == 0 and f'"{ingot}"' in stack:
                ingots += count
            elif slot == 0 and f'"{sheet}"' in stack:
                held += count
            elif slot > 0 and f'"{sheet}"' in stack:
                buffered += count
    return ingots, held, buffered


def head_offset(nbt):
    if not scalar(nbt, "Running"):
        return 0.0
    current = scalar(nbt, "Ticks")
    sample = (scalar(nbt, "PrevTicks") + current) / 2
    curve = (sample / 120) ** 3 if current < 160 else (240 - sample) / 80
    return min(1.0, max(0.0, curve)) * 19 / 16


def sample(control, tick, ingot, sheet):
    press, depot = control.commands((f"/data get block {PRESS}", f"/data get block {DEPOT}"))
    if "create:mechanical_press" not in press or "create:depot" not in depot:
        raise RuntimeError(f"Press rig is missing a block entity: {press}, {depot}")
    return [
        str(tick),
        *(str(scalar(press, key)) for key in ("Speed", "Running", "Finished", "Mode", "Ticks")),
        *map(str, item_counts(depot, ingot, sheet)),
        f"{head_offset(press):.6f}",
    ]


def power_on(control):
    control.command(f"/setblock {MOTOR} create:creative_motor[facing=east]")
    control.command(f"/data merge block {MOTOR} {{ScrollValue:128}}")


def playback(control):
    marker = "CREATE_ELEVATOR_PLAYBACK "
    event_log = control.socket.parent / "ctl.log"
    for line in event_log.read_text().splitlines():
        if marker not in line:
            continue
        identifier, source, x, y, z, volume, pitch = line.split(marker, 1)[1].split(",")
        if identifier not in ("create:mechanical_press_activation", "create:mechanical_press_activation_compounded_1"):
            continue
        if source not in ("4", "block") or tuple(map(float, (x, y, z))) != (5.5, 106.5, -10.5):
            raise RuntimeError(f"Unexpected Depot Press sound source: {line}")
        yield f"{identifier}/{float(volume):.6f}/{float(pitch):.6f}"


def run(args):
    material = "brass" if args.brass else "iron"
    ingot = "create:brass_ingot" if args.brass else "minecraft:iron_ingot"
    sheet = f"create:{material}_sheet"
    fixture = "depot_brass_pressing" if args.brass else "depot_pressing"
    with (ROOT / f"fixtures/{fixture}-java.csv").open() as file:
        rows = csv.reader(file)
        header, expected = next(rows), list(rows)
    actual = []
    sound_ticks = {}
    heard = 0
    if args.sound:
        os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
        multiplayer = import_module("test-multiplayer")
        with (ROOT / "fixtures/depot-press-sound-java.csv").open() as file:
            sound_ticks = {int(row["tick"]): row["sounds"].split(";") for row in csv.DictReader(file)}
    with fixture_world(args, fixture, STRUCTURE, render=True, pack=args.pack) as control:
        if args.sound:
            control.command("/gamemode spectator")
            control.call("tp", 8.5, 104, -8.3)
        power_on(control)
        control.command(f"/setblock {PRESS} create:mechanical_press[facing=east]")
        control.command(f"/setblock {DEPOT} create:depot")
        control.step_to(control.clock() + 1)
        control.command(f"/item replace block {DEPOT} container.0 with {ingot} 2")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick, ingot, sheet))
            if args.sound:
                events = sound_ticks.get(tick, [])
                if events:
                    multiplayer.until(f"Depot Press impact at tick {tick}",
                                      lambda: len(list(playback(control))) >= heard + len(events))
                sounds = list(playback(control))
                if events != sounds[heard:]:
                    raise RuntimeError(f"Depot Press audio at tick {tick}: {sounds[heard:]}, expected {events}")
                heard = len(sounds)
                if control.clock() != start + tick:
                    raise RuntimeError("The measured sound advanced the server tick")
            if tick == 15:
                control.command(f"/setblock {MOTOR} minecraft:air")
            if tick == 21:
                power_on(control)
            if tick == 24:
                control.command("/fill 2 103 -14 11 103 -6 minecraft:smooth_stone")
                control.command("/time set noon")
                control.call("tp", 8.5, 104, -8.3)
                control.call("look-at", 5.4, 105.3, -10.5)
                control.call("key", "f1", "tap")
                control.call("wait", 5)
                control.call("screenshot", ROOT / f".local/{fixture}.png")

    path = ROOT / f".local/{fixture}-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True)
                   if a[:-1] != b[:-1] or abs(float(a[-1]) - float(b[-1])) > 0.000002]
    if differences:
        raise SystemExit(f"Press differs on {len(differences)} ticks. "
                         f"First rows (Java, Horizon): {differences[:5]}. See {path}")
    print(f"Depot pressing matched {len(actual)} Java ticks. See {path}")
    if args.sound:
        print(f"Depot Press matched {heard} Java impact cues across both stamps and a power cut.")
    if args.brass:
        craft_deployer(args)


def craft_deployer(args):
    crafting = import_module("test-survival-crafting")
    with fixture_world(args, "Brass-hand-crafting", render=True, pack=args.pack) as control:
        control.commands((
            "/tp @s 12.5 170 26.5",
            "/fill 8 169 22 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:brass_sheet 4",
            "/item replace entity @s hotbar.1 with create:andesite_alloy",
            "/item replace entity @s hotbar.2 with create:electron_tube",
            "/item replace entity @s hotbar.3 with create:andesite_casing",
        ))
        control.call("wait", 5)
        control.call("interact", 12, 170, 24, "up")
        for item, slots in (
            ("create:andesite_alloy", (101,)),
            ("create:brass_sheet", (103, 104, 105, 107)),
        ):
            crafting.distribute(control, crafting.inventory_slot(control, item), slots)
        crafting.craft(control, "create:brass_hand", 1)
        for item, slot in (
            ("create:electron_tube", 101),
            ("create:andesite_casing", 104),
            ("create:brass_hand", 107),
        ):
            crafting.distribute(control, crafting.inventory_slot(control, item), (slot,))
        crafting.craft(control, "create:deployer", 1)
        counts = control.call("inventory")["counts"]
        if any(counts.get(item, 0) for item in (
            "create:brass_hand", "create:brass_sheet", "create:andesite_alloy",
            "create:electron_tube", "create:andesite_casing",
        )):
            raise RuntimeError(f"The two recipes did not consume their inputs: {counts}")
    print("The original Brass Hand and Deployer recipes crafted one of each and consumed every input.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--brass", action="store_true")
    parser.add_argument("--sound", action="store_true")
    args = parser.parse_args()
    if args.sound and not args.brass:
        parser.error("The original audio trace uses the brass fixture. Pass --brass.")
    run(args)


if __name__ == "__main__":
    main()
