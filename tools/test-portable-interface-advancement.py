#!/usr/bin/env python3
"""Award Drive-by Exchange to the player who placed the stationary port.

In a disposable pinned Create checkout apply java-scheduled-hopper-cargo-trace,
java-powered-hopper-cargo-trace and java-portable-interface-advancement-trace.
Run ./gradlew -PparityPoweredHopperCargo=pull -PparityPortAward runGameTestServer,
then copy run/portable-award-test-server/world to
run/portable-award-client/saves/PortableAwardReference.
Run ./gradlew -PparityPortAward runClient. For the fluid case, copy the saved
fluid dock world from java-train-moving-port-trace to the same scratch saves
directory as PortableFluidAwardReference and run -PparityPortAward=fluid.
Set onboardAccessibility:false and pauseOnLostFocus:false if needed.
"""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

collect = import_module("test-first-advancements")
schedule = import_module("test-scheduled-station-approach")
train = schedule.train
multiplayer = collect.multiplayer
ROOT = Path(__file__).resolve().parent.parent
PORT = schedule.PORT_POS
HOPPER = schedule.hopper_position(False)
LOCK = schedule.hopper_lock(False)
coords = schedule.coordinates
AWARD = ("portable_storage_interface",)
GUEST = "PortAwardGuest"


def place(world, owner, name, fluid):
    block = "create:portable_fluid_interface" if fluid else "create:portable_storage_interface"
    px, py, pz = PORT
    support = px, py, pz + 1
    for command in (
        f"/gamemode survival {name}",
        f"/tp {name} {px + 0.5} {py + 0.1} {pz - 1.5} 0 18",
        f"/setblock {coords(PORT)} minecraft:air",
        f"/setblock {coords(support)} minecraft:smooth_stone",
        f"/item replace entity {name} hotbar.0 with {block}",
    ):
        world.call("command", command)
    multiplayer.until("the placer to receive the stationary port", lambda: multiplayer.count(owner, block) == 1)
    owner.call("select", block)
    owner.call("interact", *support, "north")
    multiplayer.until("the actual facing from the port placement", lambda: (
        "facing=north" in world.call("block", *PORT)["state"]
    ))
    multiplayer.until("the real BlockItem use to consume one port", lambda: multiplayer.count(owner, block) == 0)
    world.command(f"/setblock {coords(support)} minecraft:air")


def observe(world, placer, operator, uuid, fluid):
    contents = (f"{coords(schedule.PUMP_SINK)} TankContent.Fluid.amount"
                if fluid else f"{coords(HOPPER)} Items")
    owner, cargo = world.commands((
        f"/data get block {coords(PORT)} Owner",
        f"/data get block {contents}",
    ))
    stated_owner = re.search(r"\[I; ([^\]]+)\]", owner)
    value = cargo.partition("data: ")[2]
    if fluid:
        count = int(value or 0)
    else:
        count = next((entry["count"] for entry in schedule.conductor.entry.snbt(value)
                      if entry["Slot"] == 0 and entry["id"] == "minecraft:paper"), 0) if value else 0
    won = collect.progress(world, placer, AWARD)[0]
    if operator != placer and collect.progress(world, operator, AWARD)[0] == "true":
        raise RuntimeError("The operator earned Drive-by Exchange without placing the port.")
    return (
        str(stated_owner is not None and stated_owner[1] == uuid).lower(),
        str(stated_owner is not None).lower(),
        won,
        str(count),
    )


def set_from_actor(world, actor, pos, block):
    actor.call("command", f"/setblock {coords(pos)} {block}")
    multiplayer.until(f"the server to apply {block}", lambda: (
        world.call("block", *pos)["block"] == block.partition("[")[0]
    ))


def exercise(world, owner, operator, placer, operator_name, fluid):
    selected = "@s" if placer == "@s" else f"@a[name={placer},limit=1]"
    raw_uuid = world.command(f"/data get entity {selected} UUID")
    uuid = re.search(r"\[I; ([^\]]+)\]", raw_uuid)[1]
    place(world, owner, placer, fluid)
    variant = "fluid" if fluid else "item"
    with (ROOT / f"fixtures/portable_interface_advancement_{variant}-java.csv").open() as file:
        reference = list(csv.DictReader(file))
    changes = []
    for row in reference:
        phase = row["phase"]
        if phase == "start":
            if fluid:
                set_from_actor(world, operator, schedule.PUMP_MOTOR, "create:creative_motor[facing=east]")
            else:
                set_from_actor(world, operator, LOCK, "minecraft:air")
        elif phase == "tick":
            world.step_to(world.clock() + 1)
        elif phase == "replace":
            if not fluid:
                world.command(f"/setblock {coords(LOCK)} minecraft:redstone_block")
            place(world, owner, placer, fluid)
        expected = tuple(row[key] for key in ("owns", "owner_exists", "awarded", "amount"))
        actual = observe(world, placer, operator_name, uuid, fluid)
        if actual != expected:
            changes.append((phase, row["tick"], expected, actual))
        if fluid and phase == "tick" and row["tick"] == "31":
            set_from_actor(world, operator, schedule.PUMP_MOTOR, "minecraft:air")
        if phase == "placed":
            # Warm up the parked port before the controlled release pulse.
            for _ in range(12):
                world.step_to(world.clock() + 1)
    if changes:
        raise RuntimeError(f"{len(changes)} Drive-by Exchange differences: {changes[:12]}")
    print(f"Drive-by Exchange placement, owner clearing and exact award tick matched all {len(reference)} Java samples.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--fluid", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--multiplayer", action="store_true")
    mode.add_argument("--guest-owner", action="store_true")
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    label = "portable-interface-advancement-fluid" if args.fluid else "portable-interface-advancement"
    if args.guest_owner:
        label += "-guest-owner"
    elif args.multiplayer:
        label += "-lan"
    with fixture_world(args, label, train.STRUCTURE, render=True, pack=args.pack) as world:
        setup = schedule.place_train_fluid_port if args.fluid else schedule.place_hopper_cargo_stations
        train.setup(world, after_station=setup, take_controls=False)
        if not args.fluid:
            schedule.verify_cargo(world)
        if not (args.multiplayer or args.guest_owner):
            exercise(world, world, world, "@s", "@s", args.fluid)
            return
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-pag-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
            scenario=label, pack=args.pack,
        ) as guest:
            multiplayer.until("the owner and operator to enter", lambda: any(
                player["name"] == GUEST and player["placed"] for player in world.call("lan", "status")["guests"]
            ))
            if args.guest_owner:
                exercise(world, guest, world, GUEST, "@s", args.fluid)
            else:
                exercise(world, world, guest, "@s", GUEST, args.fluid)


if __name__ == "__main__":
    main()
