#!/usr/bin/env python3
"""Replay the original netherite diving suit GameTest against Java Create."""
import argparse
import csv
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/misc/netherite_backtank.nbt")
ORIGIN = (3, 96, -12)
STAND = '@e[type=armor_stand,x=5,y=97,z=-11,distance=..2,limit=1]'
ZOMBIE = '@e[type=zombie,tag=BacktankFixture,limit=1]'
ENTITY_DATA = " has the following entity data: "


def armor_from_stand(control):
    slots = ("feet", "legs", "chest", "head")
    replies = control.commands(f"/data get entity {STAND} ArmorItems[{slot}]" for slot in range(len(slots)))
    armor = {}
    for slot, reply in zip(slots, replies, strict=True):
        _, separator, stack = reply.partition(ENTITY_DATA)
        if not separator or not stack.startswith("{"):
            raise RuntimeError(f"Missing original armor stand equipment in {slot}. {reply}")
        armor[slot] = stack
    return ",".join(f"{slot}:{stack}" for slot, stack in armor.items())


def read_entity(reply):
    if reply == "No entity was found":
        return None
    _, separator, data = reply.partition(ENTITY_DATA)
    if not separator:
        raise RuntimeError(f"Unable to read the zombie. {reply}")
    health = re.search(r"\bHealth: ([-.\d]+)f", data)
    fire = re.search(r"\bFire: (-?\d+)s", data)
    position = re.search(r"\bPos: \[[^,]+, ([-.\d]+)d,", data)
    air = re.search(r'"create:banktank_air": (\d+)', data)
    if not all((health, fire, position, air)):
        raise RuntimeError(f"Missing state from the original diving suit. {data}")
    relative_y = float(position[1]) - ORIGIN[1]
    return f"{float(health[1]):.3f}", fire[1], air[1], f"{relative_y:.6f}"


def run(args):
    with (ROOT / "fixtures/netherite_backtank-java.csv").open() as source:
        reader = csv.reader(source)
        header, expected = next(reader), list(reader)[:args.ticks]

    with TemporaryDirectory(prefix="hc-diving-") as directory:
        trace = Path(directory) / "diving.csv"
        sampled = []
        with fixture_world(args, "Netherite-backtank", STRUCTURE, env={"CREATE_TRACE_DIVING": str(trace)}) as control:
            tick = control.clock()
            for target in range(tick + 1, tick + (int(expected[0][1]) - tick) % 20 + 1):
                control.step_to(target)
            anchor = " ".join(map(str, ORIGIN))
            control.command(f"/place template create:gametest/misc/netherite_backtank {anchor}")
            armor = armor_from_stand(control)
            start = control.clock()
            for tick in range(len(expected)):
                if tick:
                    control.step_to(start + tick)
                if tick == 5:
                    spawned = control.command(
                        f'/summon minecraft:zombie 5.5 99 -8.5 {{Tags:["BacktankFixture"],'
                        f'PersistenceRequired:1b,Fire:-1s,equipment:{{{armor}}}}}'
                    )
                    if "Summoned" not in spawned:
                        raise RuntimeError(spawned)
                sampled.append(read_entity(control.command(f"/data get entity {ZOMBIE}")))

        flags_by_tick = {}
        if trace.is_file():
            with trace.open() as source:
                flags_by_tick = {int(tick): (lava, immune) for tick, lava, immune in csv.reader(source)}

    actual = []
    for tick, entity in enumerate(sampled):
        world_tick = start + tick
        row = [str(tick), str(world_tick % 20), str(int(entity is not None))]
        if entity is None:
            actual.append([*row, "", "", "", "", "", ""])
            continue
        if world_tick not in flags_by_tick:
            raise RuntimeError(f"Missing live mob flags at fixture tick {tick}")
        health, fire, air, y = entity
        lava, immune = flags_by_tick[world_tick]
        actual.append([*row, health, fire, lava, immune, air, y])

    output = ROOT / ".local/netherite_backtank-horizon.csv"
    with output.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [
        (want[0], {name: (reference, observed) for name, reference, observed in zip(header, want, got, strict=True)
                   if reference != observed})
        for want, got in zip(expected, actual, strict=True) if want != got
    ]
    if differences:
        raise SystemExit(f"Netherite backtank differed on {len(differences)} ticks. "
                         f"First differences (Java, Horizon) {differences[:3]}. See {output}")
    print(f"Netherite backtank matched all {len(actual)} Java ticks. See {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--ticks", type=int)
    args = parser.parse_args()
    if args.ticks is not None and args.ticks < 1:
        parser.error("--ticks must be positive")
    run(args)
