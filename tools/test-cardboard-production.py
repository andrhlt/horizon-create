#!/usr/bin/env python3
"""Compare Create Pulp mixing and Cardboard pressing to pinned Java."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

fluid = import_module("test-fluid-food")
mp = import_module("test-multiplayer")
cases = ((-12, "minecraft:bamboo", 250), (-7, "minecraft:sugar_cane", 500),
         (-2, "minecraft:oak_sapling", 250), (3, "minecraft:bamboo", 249))
DEPOT = (9, 104, -12)
DEPOT_POS = " ".join(map(str, DEPOT))
CARDBOARD = "create:cardboard"


def setup(world):
    world.commands((
        "/fill 3 103 -14 12 103 5 minecraft:smooth_stone",
        "/fill 3 104 -14 12 111 5 minecraft:air",
        "/tp @s 7.5 104 -3.5",
    ))
    for z, _, _ in cases:
        world.commands((
            f"/setblock 4 105 {z} create:creative_motor[facing=up]{{ScrollValue:256}}",
            f"/setblock 4 106 {z} create:cogwheel[axis=y]",
            f"/setblock 5 106 {z} create:mechanical_mixer",
            f"/setblock 5 104 {z} create:basin",
        ))
    world.commands((
        "/setblock 8 106 -12 create:creative_motor[facing=east]{ScrollValue:128}",
        "/setblock 9 106 -12 create:mechanical_press[facing=east]",
        f"/setblock {DEPOT_POS} create:depot",
    ))


def feed(world):
    for z, item, water in cases:
        world.commands((
            f'/data merge block 5 104 {z} {{InputTanks:[{{TankContent:{{Fluid:{{id:"minecraft:water",amount:{water}}}}}}},{{}}]}}',
            f"/item replace block 5 104 {z} container.0 with {item} 4",
        ))
    world.command(f"/item replace block {DEPOT_POS} container.0 with create:pulp")


def observe(world, tick):
    queries = [command for z, _, _ in cases for command in (
        f"/data get block 5 106 {z}", f"/data get block 5 104 {z}",
    )]
    replies = iter(world.commands((*queries, f"/data get block {DEPOT_POS} Items")))
    rows = []
    for rig, (_, item, _) in enumerate(cases):
        mixer, basin = next(replies), next(replies)
        rows.append([
            str(tick), str(rig),
            *(str(int(fluid.number(mixer, name))) for name in ("Speed", "Running", "Ticks", "ProcessingTicks")),
            str(fluid.count(basin, item)), str(fluid.quantity(basin, "InputTanks")),
            str(fluid.count(basin, "create:pulp")),
        ])
    depot = next(replies)
    return rows, [str(tick), str(fluid.count(depot, "create:pulp")), str(fluid.count(depot, CARDBOARD))]


def read(name):
    with (ROOT / "fixtures" / f"{name}-java.csv").open() as source:
        rows = csv.reader(source)
        return next(rows), list(rows)


def compare(name, head, reference, actual, lan):
    suffix = "-lan" if lan else ""
    with (ROOT / ".local" / f"{name}-horizon{suffix}.csv").open("w", newline="") as output:
        out = csv.writer(output, lineterminator="\n")
        out.writerow(head)
        out.writerows(actual)
    differences = [(a, b) for a, b in zip(reference, actual, strict=True) if a != b]
    print(name, len(reference), "total rows", len(differences), "differences", differences[:6], flush=True)
    return not differences


def reopen_active(args):
    with fixture_world(args, "CardboardProductionReopen", pack=args.pack) as world:
        setup(world)
        for _ in range(2):
            world.step_to(world.clock() + 1)
        start = world.clock()
        for tick in range(5):
            if tick:
                world.step_to(start + tick)
            if tick == 4:
                feed(world)
        for tick in range(5, 16):
            world.step_to(start + tick)

        before_pulp, before_press = observe(world, 15)
        world.command("/save-all flush")
        world.restart()
        after_pulp, after_press = observe(world, 0)
        assert all(int(row[3]) == 1 for row in before_pulp[:3]), before_pulp
        assert all(
            (int(row[6]), int(row[8])) in {(4, 0), (0, 1)}
            for row in after_pulp[:3]
        ), (before_pulp, after_pulp)
        assert int(after_pulp[3][6]) == 4 and int(after_pulp[3][8]) == 0, after_pulp[3]
        assert int(after_press[1]) + int(after_press[2]) == 1, (before_press, after_press)

        # Finish the same in-flight batches after reload and confirm each
        # eligible input produces once, while the 249 mB control remains idle.
        for _ in range(35):
            world.step_to(world.clock() + 1)
        rows, press = observe(world, 50)
        assert [int(row[-1]) for row in rows] == [1, 1, 1, 0], rows
        assert [int(row[-3]) for row in rows] == [0, 0, 0, 4], rows
        assert int(press[-1]) == 1, press

        # Once idle, preserve finished outputs and both block orientations.
        world.commands((
            "/setblock 7 104 -5 create:cardboard_block[axis=x]",
            "/setblock 10 104 -5 create:bound_cardboard_block[axis=z]",
            "/save-all flush",
        ))
        world.restart()
        rows, press = observe(world, 50)
        assert [int(row[-1]) for row in rows] == [1, 1, 1, 0], rows
        assert int(press[-1]) == 1, press
        assert world.call("block", 7, 104, -5)["state"] == "create:cardboard_block[axis=x]"
        assert world.call("block", 10, 104, -5)["state"] == "create:bound_cardboard_block[axis=z]"
    print("Active Pulp mixing and pressing survived reopen; three eligible batches and one press completed once.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--reopen", action="store_true")
    args = parser.parse_args()
    if args.reopen:
        reopen_active(args)
        return
    pulp_head, pulp_reference = read("cardboard-pulp")
    press_head, press_reference = read("cardboard-press")
    pulp, pressed = [], []
    with ExitStack() as stack:
        scenario = "CardboardProductionLAN" if args.lan else "CardboardProductionTrace"
        world = stack.enter_context(fixture_world(args, scenario, pack=args.pack))
        setup(world)
        guest = None
        if args.lan:
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            directory = Path(stack.enter_context(TemporaryDirectory(prefix="hc-pulp-")))
            name = "PulpGuest"
            guest = stack.enter_context(mp.joined_client(
                args, directory, f"127.0.0.1:{port}", name, scenario="cardboard-production", pack=args.pack,
            ))
            mp.until("guest to join", lambda: any(
                player["name"] == name and player["placed"] for player in world.call("lan", "status")["guests"]
            ))
            world.commands((f"/gamemode survival {name}", f"/tp {name} 9.5 104 -9.5 180 30"))
            mp.until("guest to reach the Press", lambda:
                     tuple(guest.call("state")["player"]["position"]) == (9.5, 104, -9.5))
            mp.until("guest to see the Depot", lambda: guest.call("block", *DEPOT)["block"] == "create:depot")
        for _ in range(2):
            world.step_to(world.clock() + 1)
        start = world.clock()
        for tick in range(len(press_reference)):
            if tick:
                world.step_to(start + tick)
            rows, press = observe(world, tick)
            pulp.extend(rows)
            pressed.append(press)
            if tick == 4:
                feed(world)
        if guest:
            assert mp.count(guest, CARDBOARD) == 0
            guest.call("interact", *DEPOT, "up")
            mp.until("guest to collect the pressed Cardboard", lambda: mp.count(guest, CARDBOARD) == 1)
            assert fluid.count(world.command(f"/data get block {DEPOT_POS} Items"), CARDBOARD) == 0
            print("LAN guest collected the finished Cardboard from the Depot.", flush=True)
    pulp_ok = compare("cardboard-pulp", pulp_head, pulp_reference, pulp, args.lan)
    press_ok = compare("cardboard-press", press_head, press_reference, pressed, args.lan)
    raise SystemExit(0 if pulp_ok and press_ok else 1)


if __name__ == "__main__":
    main()
