#!/usr/bin/env python3
"""Compare original Ejector item trajectories and physical stack release."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

launch = import_module("test-depot-ejector-launch")
multiplayer = import_module("test-multiplayer")
ORIGIN = (5, 105, -11)
LOOSE = (
    '@e[type=minecraft:item,x=4,y=104,z=-12,dx=11,dy=14,dz=3,limit=1,'
    'nbt={Item:{id:"minecraft:iron_ingot"}}]'
)


def vector(reply, key):
    match = re.search(rf"\b{key}: \[([^\]]+)\]", reply)
    if not match:
        return None
    return [float(value.strip().rstrip("df")) for value in match[1].split(",")]


def items_near(control, item):
    return [entry for entry in control.call("entities", 16, "minecraft:item")["entities"]
            if entry["item"]["item"] == item]


def item_ids(control, item):
    return [entry["id"] for entry in items_near(control, item)]


def match_item_phase(control, phase):
    # Vanilla checks a grounded item on (tickCount + entityId) % 4.
    dummy = "minecraft:gold_ingot"
    for count in range(1, 5):
        control.command(f'/summon minecraft:item 8.5 110 -10.5 '
                        f'{{Item:{{id:"{dummy}",count:1}},PickupDelay:32767s}}')
        ids = multiplayer.until("the temporary entity is visible",
                                lambda: ids if len(ids := item_ids(control, dummy)) == count else None)
        if (max(ids) + 1) % 4 == phase:
            break
    else:
        raise RuntimeError("Unable to start the item entity on the original Java phase.")
    control.command(f'/kill @e[type=minecraft:item,nbt={{Item:{{id:"{dummy}"}}}}]')


def run(args):

    filename = "depot-ejector-air-java.csv" if args.open_air else "depot-ejector-obstacle-java.csv"
    reference = args.reference or ROOT / "fixtures" / filename
    with reference.open() as source:
        rows = csv.reader(source)
        header, expected = next(rows), list(rows)
    actual = []
    first_release = next((int(row[0]), int(row[4])) for row in expected if row[3] != "0")
    world = "EjectorOpenAir" if args.open_air else "EjectorObstacle"
    if args.multiplayer:
        world += "LAN"
    with ExitStack() as stack:
        control = stack.enter_context(fixture_world(args, world, pack=args.pack))
        launch.setup(control)
        block = "minecraft:air" if args.open_air else "minecraft:smooth_stone"
        point = (9, 105, -11) if args.open_air else (7, 108, -11)
        control.command(f"/setblock {' '.join(map(str, point))} {block}")
        guest = None
        if args.multiplayer:
            port = control.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejector-impact-")))
            name = "EjectArcGuest"
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, scenario="ejector-obstacle", pack=args.pack,
            ))
            multiplayer.until("guest enters the Ejector fixture", lambda: any(
                player["name"] == name and player["placed"]
                for player in control.call("lan", "status")["guests"]
            ))
            control.commands((f"/gamemode spectator {name}", f"/tp {name} 8.5 106 -10.5"))
            multiplayer.until("guest sees the launch course",
                              lambda: guest.call("block", *point)["block"] == block)
        start = control.clock()
        for row in expected:
            tick = int(row[0])
            control.step_to(start + tick)
            if tick == 12:
                control.commands((
                    f'/data merge block {launch.EJECTOR} '
                    f'{{Items:[{{Slot:0b,id:"{launch.ITEM}",count:3}}],BeltPosition:0.5f}}',
                    f"/setblock {launch.POWER} minecraft:air",
                ))
            if tick == first_release[0] - 1:
                match_item_phase(control, first_release[1])
            flying, received, loose, impact = control.commands((
                f"/data get block {launch.EJECTOR} LaunchedItems",
                f"/data get block {launch.DEPOT} Items",
                f"/data get entity {LOOSE}",
                f"/data get block {launch.EJECTOR} EarlyTargetTime",
            ))
            age = re.search(r"\bTime: (\d+)", flying)
            count = launch.count(loose)
            position = vector(loose, "Pos")
            speed = vector(loose, "Motion")
            if count and (position is None or speed is None):
                raise RuntimeError(f"Missing item position or velocity at tick {tick}: {loose}")
            phase = -1
            if count:
                position = [axis - origin for axis, origin in zip(position, ORIGIN, strict=True)]
                ids = multiplayer.until("released item is visible", lambda: item_ids(control, launch.ITEM))
                (item_id,) = ids
                phase = item_id % 4
                if guest:
                    visible = multiplayer.until(f"guest sees the released stack at tick {tick}",
                                                lambda: items_near(guest, launch.ITEM))
                    if [(entry["id"], entry["item"]["count"]) for entry in visible] != [(item_id, count)]:
                        raise RuntimeError(f"Wrong guest item contents at tick {tick}: {visible}")
            elif guest and items_near(guest, launch.ITEM):
                raise RuntimeError(f"The guest saw a loose ingot before the release at tick {tick}.")
            actual.append([
                str(tick), age[1] if age else "-1", str(launch.count(received)), str(count), str(phase),
                *(f"{value:.6f}" for value in (position or [0] * 3)),
                *(f"{value:.6f}" for value in (speed or [0] * 3)),
                f"{launch.value(impact) or 0:.6f}",
            ])
        if guest:
            final_pos = [float(axis) + origin for axis, origin in zip(expected[-1][5:8], ORIGIN, strict=True)]
            multiplayer.until("guest sees the stack at its settled position",
                              lambda: any(all(abs(a - b) < .002 for a, b in zip(item["pos"], final_pos, strict=True))
                                          for item in items_near(guest, launch.ITEM)))
            control.commands((f"/gamemode survival {name}",
                              f"/tp {name} {' '.join(map(str, final_pos))}"))
            for tick in range(start + int(expected[-1][0]) + 1, start + int(expected[-1][0]) + 5):
                control.step_to(tick)
                if multiplayer.count(guest, launch.ITEM) == 3:
                    break
            multiplayer.until("guest picks up all three ingots", lambda: multiplayer.count(guest, launch.ITEM) == 3)
    if args.trace:
        with args.trace.open("w") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(actual)
    differences = [
        (want, got) for want, got in zip(expected, actual, strict=True)
        if want[:5] != got[:5]
        or any(abs(float(a) - float(b)) > .000002 for a, b in zip(want[5:], got[5:], strict=True))
    ]
    if differences:
        raise RuntimeError(f"Ejector item release differed on {len(differences)} Java ticks: {differences[:8]}")
    print(f"Weighted Ejector flight, stack release, and item motion matched {len(actual)} Java ticks.")
    if args.multiplayer:
        print("The guest saw the stack on release and collected all three ingots where it landed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--open-air", action="store_true")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    run(parser.parse_args())
