#!/usr/bin/env python3
"""Compare real Hopper insert and extract through a powered train item port.

Apply java-scheduled-hopper-cargo-trace.patch and
java-powered-hopper-cargo-trace.patch to the pinned Create checkout.
Run ./gradlew -PparityPoweredHopperCargo=pull runGameTestServer and repeat
with =push for the original powered and resumed slot custody ticks.
"""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

schedule = import_module("test-scheduled-station-approach")
train, conductor = schedule.train, schedule.conductor
multiplayer = conductor.multiplayer
wrench = import_module("test-wrench")
ROOT = Path(__file__).resolve().parent.parent
PORT = schedule.PORT_POS
POWER = (PORT[0], PORT[1], PORT[2] + 1)
coords = schedule.coordinates


def block_enabled(world, hopper):
    return wrench.state(world.call("block", *hopper)["state"])[1].get("enabled", "false") == "true"


def observe(world, hopper):
    raw_port, powered, owner, raw_chest, raw_hopper = world.commands((
        f"/data get block {coords(PORT)} Timer",
        f"/execute if block {coords(POWER)} minecraft:redstone_block",
        f"/data get block {coords(PORT)} TrainPort",
        f"/data get entity {train.ENTITY} {schedule.CHEST_ITEMS}",
        f"/data get block {coords(hopper)} Items",
    ))

    def count(reply, slot, item):
        data = reply.partition("data: ")[2]
        return next((entry["count"] for entry in conductor.entry.snbt(data)
                     if entry["Slot"] == slot and entry["id"] == item), 0) if data else 0

    timer = int(raw_port.partition("data: ")[2] or 0)
    powered = powered.startswith("Test passed")
    connected = 4 <= timer <= 64 and "data:" in owner and not powered
    return (
        powered, block_enabled(world, hopper), timer, connected,
        count(raw_chest, 0, "minecraft:paper"), count(raw_hopper, 0, "minecraft:paper"),
        count(raw_chest, 1, "minecraft:paper"), count(raw_chest, 2, "minecraft:redstone"),
    )


def exercise(world, guest, pushing):
    hopper, lock = schedule.hopper_position(pushing), schedule.hopper_lock(pushing)
    variant = "push" if pushing else "pull"
    with (ROOT / f"fixtures/powered_hopper_{variant}-java.csv").open() as file:
        reference = list(csv.DictReader(file))
    # Align the final idle countdown in the two otherwise independent assembly rigs.
    first_timer = int(reference[0]["timer"])
    for _ in range(15):
        if observe(world, hopper)[2] == first_timer:
            break
        world.step_to(world.clock() + 1)
    else:
        raise RuntimeError(f"The parked item port never reached the Java start timer {first_timer}.")
    differences = []
    edits = {
        27: (f"/setblock {coords(POWER)} minecraft:redstone_block", f"/setblock {coords(lock)} minecraft:air"),
        31: (f"/setblock {coords(POWER)} minecraft:air",),
        32: (f"/setblock {coords(lock)} minecraft:redstone_block",),
    }
    for index, row in enumerate(reference):
        tick = int(row["tick"])
        if index:
            world.step_to(world.clock() + 1)
        actual = observe(world, hopper)
        expected = (
            row["powered"] == "true", row["hopper_enabled"] == "true",
            int(row["timer"]), row["connected"] == "true",
            *(int(row[key]) for key in ("mounted_paper", "hopper_paper", "other_paper", "redstone")),
        )
        if actual != expected:
            differences.append((tick, actual, expected))
        if guest and tick in (30, 36):
            multiplayer.until("the guest to see the Hopper lock", lambda: block_enabled(guest, hopper) == expected[1])
        if tick not in edits:
            continue
        if guest is None:
            world.commands(edits[tick])
            continue
        for edit in edits[tick]:
            _, x, y, z, block = edit.split()
            guest.call("command", edit)
            multiplayer.until("the guest's redstone change on the host", lambda: (
                world.call("block", x, y, z)["block"] == block
            ))
    if differences:
        raise RuntimeError(f"{len(differences)} powered Hopper differences (tick, Horizon, Java): {differences[:12]}")
    print(f"Powered port {variant}, real Hopper lock and slot custody matched all {len(reference)} Java ticks.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--multiplayer", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    variant = "push" if args.push else "pull"
    label = f"powered-hopper-{variant}" + ("-lan" if args.multiplayer else "")
    with fixture_world(args, label, train.STRUCTURE, render=True, pack=args.pack) as world:
        train.setup(world, after_station=lambda world: schedule.place_cargo_stations(
            world, portable=True, inserting=args.push
        ), take_controls=False)
        schedule.verify_cargo(world, initial_count=63 if args.push else 64)
        if not args.multiplayer:
            exercise(world, None, args.push)
            return
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        name = "PortHopperGuest"
        with TemporaryDirectory(prefix="hc-phg-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", name, render=True,
            scenario=label, pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to join", lambda: any(
                player["name"] == name and player["placed"] for player in world.call("lan", "status")["guests"]
            ))
            world.commands((f"/gamemode spectator {name}", f"/tp {name} 8.5 118 -5.7"))
            multiplayer.until("the parked Hopper to load", lambda: guest.call("block", *schedule.hopper_position(args.push))[
                "block"
            ] == "minecraft:hopper")
            exercise(world, guest, args.push)


if __name__ == "__main__":
    main()
