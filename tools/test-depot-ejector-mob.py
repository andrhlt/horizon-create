#!/usr/bin/env python3
"""Replay the Weighted Ejector launching a stock falling mob."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
obstacle = import_module("test-depot-ejector-obstacle")
track = import_module("test-track-crafting")
EJECTOR = (5, 104, -11)


def setup(control, flat):
    control.commands((
        "/fill 3 103 -13 14 103 -9 minecraft:smooth_stone",
        "/fill 3 104 -13 14 112 -9 minecraft:air",
        *(("/fill 8 104 -12 13 106 -10 minecraft:smooth_stone",) if not flat else ()),
        "/setblock 5 104 -11 create:weighted_ejector[facing=east]{HorizontalDistance:4,VerticalDistance:0}",
        "/setblock 5 104 -12 create:creative_motor[facing=south]{ScrollValue:128}",
        "/gamemode spectator @s",
        "/tp @s 8.5 105 -9.5",
    ))


def run(args):
    mode = "offset" if args.offset else "flat" if args.flat else "center"
    reference = args.reference or ROOT / "fixtures" / f"depot-ejector-mob-{mode}-java.csv"
    with reference.open() as source:
        data = csv.reader(source)
        header, expected = next(data), list(data)
    actual = []
    with ExitStack() as stack:
        world = f"EjectorMob{mode.title()}" + ("LAN" if args.multiplayer else "")
        control = stack.enter_context(fixture_world(args, world, pack=args.pack))
        setup(control, args.flat)
        guest = None
        if args.multiplayer:
            port = control.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejector-mob-")))
            name = "EjectorMobGuest"
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, scenario="ejector-mob", pack=args.pack,
            ))
            multiplayer.until("the mob fixture guest joins", lambda: any(
                player["name"] == name and player["placed"]
                for player in control.call("lan", "status")["guests"]
            ))
            control.commands((f"/gamemode spectator {name}", f"/tp {name} 8.5 106 -9.5"))
            multiplayer.until("guest sees the Weighted Ejector", lambda:
                              guest.call("block", *EJECTOR)["block"] == "create:weighted_ejector")
        start = control.clock()
        for row in expected:
            tick = int(row[0])
            control.step_to(start + tick)
            if tick == 12:
                x = 5.875 if args.offset else 5.5
                control.commands((
                    f'/summon minecraft:pig {x} 106.5 -10.5 {{Tags:["EjectorPig"],Silent:1b}}',
                    '/attribute @e[type=minecraft:pig,tag=EjectorPig,limit=1] minecraft:movement_speed base set 0',
                ))
            state, mob = control.commands((
                "/data get block 5 104 -11 State",
                "/data get entity @e[type=minecraft:pig,tag=EjectorPig,limit=1]",
            ))
            matched = re.search(r"\b(CHARGED|LAUNCHING|RETRACTING)\b", state)
            if matched is None:
                raise RuntimeError(f"No Ejector state at tick {tick}: {state}")
            if tick < 12:
                actual.append([str(tick), matched[1], "false", *row[3:]])
                continue
            pos, motion = (obstacle.vector(mob, key) for key in ("Pos", "Motion"))
            ground = re.search(r"\bOnGround: (true|false|[01]b)", mob)
            if not pos or not motion or not ground:
                raise RuntimeError(f"Could not read pig state at tick {tick}: {mob}")
            point = [v - b for v, b in zip(pos, EJECTOR, strict=True)]
            health = track.field(mob, "Health")
            actual.append([
                str(tick), matched[1], "true", *[f"{v:.8f}" for v in (*point, *motion)],
                "true" if ground[1] in ("true", "1b") else "false", f"{health:.2f}",
            ])
            if guest and tick == 31:
                multiplayer.until("guest sees the pig in flight", lambda: any(
                    7 < entity["pos"][0] < 10 and entity["pos"][1] > 108
                    for entity in guest.call("entities", 16, "minecraft:pig")["entities"]
                ))
        if guest:
            multiplayer.until("guest sees the pig at the Java landing point", lambda: any(
                abs(entity["pos"][0] - (EJECTOR[0] + float(expected[-1][3]))) < .05
                and abs(entity["pos"][1] - (EJECTOR[1] + float(expected[-1][4]))) < .05
                for entity in guest.call("entities", 16, "minecraft:pig")["entities"]
            ))
    if args.trace:
        with args.trace.open("w") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(actual)
    differences = [(want, got) for want, got in zip(expected, actual, strict=True)
                   if want[:3] != got[:3] or want[9:] != got[9:]
                   or any(abs(float(a) - float(b)) > .000002
                          for a, b in zip(want[3:9], got[3:9], strict=True))]
    if differences:
        raise RuntimeError(f"Falling pig differed on {len(differences)} Java ticks: {differences[:8]}")
    print(f"Falling pig, launch and landing matched all {len(actual)} Java ticks.")
    if args.multiplayer:
        print("The guest saw the pig in flight and at the original landing point.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path)
    course = parser.add_mutually_exclusive_group()
    course.add_argument("--offset", action="store_true")
    course.add_argument("--flat", action="store_true")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    run(parser.parse_args())
