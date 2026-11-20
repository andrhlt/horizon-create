#!/usr/bin/env python3
"""Check item and fluid exchange on one rotating bearing, including save/reopen."""

import argparse
from collections import Counter
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

mounted = import_module("test-mounted-storage")
multiplayer = import_module("test-multiplayer")
comparator = import_module("test-mounted-port-comparator")
visuals = import_module("test-mounted-moving-port-render")

STRUCTURE = Path("gametest/contraptions/mounted_item_extract.nbt")
BEARING = "15 119 -10"
LEVER = (15, 120, -11)
LEVER_STATE = "minecraft:lever[face=wall,facing=north,powered="
ITEM = "portable_storage_interface"
FLUID = "portable_fluid_interface"
ITEM_PORT = (18, 118, -10)
FLUID_PORT = (18, 115, -10)
FAR_PORT = (20, 118, -10)
HOPPER = (18, 117, -10)
CHEST = (18, 117, -11)
FEEDER = (18, 119, -10)
TANK = (18, 114, -11)
PUMP = (18, 115, -11)
PAPER = "minecraft:paper"
EMERALD = "minecraft:emerald"
BLOCKER = "minecraft:cobblestone"
WATER = "minecraft:water"
GUEST = "PortOperator"
coords = comparator.coords


def inventory(reply):
    pairs = mounted.cargo(reply)
    return Counter({name: int(count) for name, _, count in
                    (pair.partition("=") for pair in pairs.split("|") if pair)})


def observe(world, *, assembled=True):
    item_path = f"{BEARING} MountedItems" if assembled else "15 118 -10 Items"
    tank_path = (f'{BEARING} MovedBlocks[{{BlockState:{{Name:"create:fluid_tank"}}}}].Entity.TankContent'
                 if assembled else "15 115 -10 TankContent")
    item, hopper, chest, feeder, tank, fixed, item_timer, fluid_timer = world.commands((
        f"/data get block {item_path}",
        f"/data get block {coords(HOPPER)} Items",
        f"/data get block {coords(CHEST)} Items",
        f"/data get block {coords(FEEDER)} Items",
        f"/data get block {tank_path}",
        f"/data get block {coords(TANK)} TankContent",
        f"/data get block {coords(ITEM_PORT)} Timer",
        f"/data get block {coords(FLUID_PORT)} Timer",
    ))
    contents = tuple(map(inventory, (item, hopper, chest, feeder)))
    for reply in (tank, fixed):
        assert not mounted.amount(reply, "amount") or WATER in reply, reply
    water = tuple(mounted.amount(reply, "amount") for reply in (tank, fixed))
    timers = tuple(int(mounted.data(reply) or 0) for reply in (item_timer, fluid_timer))
    return contents, water, timers


def setup(world):
    world.commands((
        f"/place template create:{STRUCTURE.with_suffix('')} 14 116 -12",
        '/data modify block 15 118 -10 Items set value [{Slot:0b,id:"minecraft:paper",count:16}]',
        "/fill 15 116 -11 15 117 -10 minecraft:stone",
        "/setblock 16 116 -10 minecraft:air",
        "/setblock 15 115 -11 create:portable_fluid_interface[facing=north]",
        "/setblock 15 115 -10 create:fluid_tank",
        '/data merge block 15 115 -10 {TankContent:{Fluid:{id:"minecraft:water",amount:5000}}}',
        "/summon minecraft:marker 15 115 -11 {CreateSuperGlue:1b,From:[0d,0d,0d],To:[1d,4d,2d]}",
        f"/setblock {coords(ITEM_PORT)} minecraft:air",
        f"/setblock {coords(FAR_PORT)} create:{ITEM}[facing=west]",
        f"/setblock {coords(FLUID_PORT)} create:{FLUID}[facing=east]",
        f"/setblock {coords(FEEDER)} minecraft:hopper[facing=down]",
        "/setblock 18 120 -10 minecraft:redstone_block",
        f"/item replace block {coords(FEEDER)} container.0 with {EMERALD} 8",
        f"/setblock {coords(HOPPER)} minecraft:hopper[facing=down]",
        *(f"/item replace block {coords(HOPPER)} container.{slot} with {BLOCKER} 64" for slot in range(5)),
        "/setblock 17 114 -11 create:creative_motor[facing=up]{ScrollValue:256}",
        "/setblock 17 115 -11 create:cogwheel[axis=y]",
        f"/setblock {coords(TANK)} create:fluid_tank",
        f'/data merge block {coords(TANK)} {{TankContent:{{Fluid:{{id:"{WATER}",amount:8000}}}}}}',
        f"/setblock {coords(PUMP)} create:mechanical_pump[facing=down]",
        "/setblock 18 116 -11 create:fluid_pipe[down=true,south=true]",
        "/setblock 18 116 -10 create:fluid_pipe[down=true,north=true]",
    ))


def tick(world, count):
    target = world.clock() + count
    world.command(f"/tick step {count}")
    multiplayer.until(f"the server to finish tick {target}", lambda: world.clock() == target)


def wait_for_state(world, check, limit, phase):
    start = world.clock()
    for elapsed in range(limit + 1):
        state = observe(world)
        cargo_conserved(state)
        if check(state):
            print(f"{phase}: {elapsed} ticks, {state}", flush=True)
            return state
        if elapsed < limit:
            world.step_to(start + elapsed + 1)
    raise AssertionError((phase, state))


def cargo_conserved(state):
    items, water, _ = state
    totals = sum(items, Counter())
    assert (totals[PAPER], totals[EMERALD], sum(water)) == (16, 8, 13000), state


def run(args):
    label = "dual-port-bearing-lan" if args.lan else "dual-port-bearing"
    with ExitStack() as sessions:
        world = sessions.enter_context(fixture_world(
            args, label, STRUCTURE, render=args.lan, pack=args.pack, env={"HORIZON_NO_AUDIO": "1"},
        ))
        setup(world)
        powered = [mounted.data(reply) for reply in world.commands(
            f"/data get block {coords(station)} Powered" for station in (FAR_PORT, FLUID_PORT)
        )]
        assert all(value in ("", "0b") for value in powered), powered
        guest = None
        with ExitStack() as guests:
            if args.lan:
                port = world.call("lan", "open", "0", "commands", "force")["port"]
                scratch = Path(guests.enter_context(TemporaryDirectory(prefix="hc-dual-port-")))
                guest = guests.enter_context(multiplayer.joined_client(
                    args, scratch, f"127.0.0.1:{port}", GUEST, render=True, scenario=label,
                    pack=args.pack, env={"HORIZON_NO_AUDIO": "1"},
                ))
                multiplayer.until("the dock operator to join", lambda: any(
                    player["name"] == GUEST and player["placed"]
                    for player in world.call("lan", "status")["guests"]
                ))
                world.commands((f"/gamemode survival {GUEST}", f"/attribute {GUEST} minecraft:gravity base set 0",
                                f"/tp {GUEST} 15.5 118.5 -13.5"))
                multiplayer.until("the operator to see the bearing lever", lambda:
                                  "powered=true" in guest.call("block", *LEVER)["state"])
                guest.call("interact", *LEVER, "north")
                multiplayer.until("the guest to start the bearing", lambda:
                                  "powered=false" in world.call("block", *LEVER)["state"])
            else:
                comparator.lever_state(world, world, LEVER, LEVER_STATE, False)
            start = world.clock()
            actor_paths = [f"{BEARING} {visuals.actor_path(name)}.WorkingPos" for name in (ITEM, FLUID)]
            for step in range(1, 29):
                world.step_to(start + step)
                replies = world.commands(f"/data get block {path}" for path in actor_paths)
                assert all(not mounted.data(reply) for reply in replies), replies
            spinning = mounted.data(world.command(f"/data get block {BEARING} Angle"))
            assert float(spinning.removesuffix("f")) < -100, spinning
            closed = observe(world)
            cargo_conserved(closed)
            assert closed[1:] == ((5000, 8000), (0, 0)), closed

            world.commands((
                f"/setblock {coords(ITEM_PORT)} create:{ITEM}[facing=west]",
                f"/setblock {coords(FLUID_PORT)} create:{FLUID}[facing=west]",
            ))
            full = wait_for_state(world, lambda s: min(s[2]) > 4, 90, "Both pairs docked")
            active = [mounted.data(reply) for reply in world.commands(
                f"/data get block {path}" for path in actor_paths
            )]
            assert active == ["[I; 18, 118, -10]", "[I; 18, 115, -10]"], active
            tick(world, 6)
            blocked = observe(world)
            assert blocked[:2] == full[:2], ("Full destinations accepted cargo", full, blocked)
            assert full[0][0][PAPER] == 16 and full[0][1][BLOCKER] == 320, full
            assert full[1] == (5000, 8000), full
            cargo_conserved(full)

            world.commands((
                "/setblock 18 120 -10 minecraft:air",
                f"/setblock {coords(PUMP)} create:mechanical_pump[facing=up]",
            ))
            inserted = wait_for_state(world, lambda s: s[0][0][EMERALD] > 0 and s[1] == (8000, 5000),
                                      100, "Both mounted stores received cargo")
            assert inserted[0][1][BLOCKER] == 320, inserted
            tick(world, 2)
            saturated = observe(world)
            cargo_conserved(saturated)
            assert saturated[1] == (8000, 5000), saturated
            # Remove the five full control stacks without dropping them into
            # the world. Paper, emeralds and water stay in the closed system.
            world.commands((
                "/setblock 18 120 -10 minecraft:redstone_block",
                *(f"/item replace block {coords(HOPPER)} container.{slot} with minecraft:air"
                  for slot in range(5)),
                f"/setblock {coords(HOPPER)} minecraft:hopper[facing=north]",
                f"/setblock {coords(PUMP)} create:mechanical_pump[facing=down]",
                "/data merge block 17 114 -11 {ScrollValue:128}",
            ))
            extracted = wait_for_state(world, lambda s: (
                s[0][2][PAPER] > 0 and s[1][1] > inserted[1][1] and min(s[2]) > 4
            ), 100, "Both fixed receivers took cargo")
            cargo_conserved(extracted)
            if guest:
                for station in (ITEM_PORT, FLUID_PORT):
                    multiplayer.until("the guest to see the extended receiver", lambda:
                                      "extended=true" in guest.call("block", *station)["state"])
                world.command(f"/tp {GUEST} 18.5 116 -13.5")
                multiplayer.until("the operator to reach the output", lambda:
                                  tuple(guest.call("state")["player"]["position"]) == (18.5, 116, -13.5))
                guest.call("interact", *CHEST, "north")
                multiplayer.until("the guest to see paper in the output", lambda: any(
                    (entry["stack"] or {}).get("item") == PAPER
                    and entry["stack"]["count"] == extracted[0][2][PAPER]
                    for entry in guest.call("menu")["slots"]
                ))
                print("The survival guest toggled the bearing, saw both docks and opened the paper chest.",
                      flush=True)
        watch = (
            *actor_paths,
            f"{BEARING} Angle",
            f"{BEARING} Stalled",
            *(f"{coords(station)} {field}" for station in (ITEM_PORT, FLUID_PORT)
              for field in ("Timer", "Powered", "Bearing", "ConnectedAt", "LastContact")),
        )
        def dock_status():
            return [mounted.data(reply) for reply in world.commands(
                f"/data get block {path}" for path in watch
            )]

        print(f"Saved dock: {world.clock()}, {dock_status()}", flush=True)
        world.call("save")
        world.restart()
        print(f"Reopened dock: {world.clock()}, {dock_status()}", flush=True)
        reopened = observe(world)
        cargo_conserved(reopened)
        try:
            wait_for_state(world, lambda s: (
                min(s[2]) > 4 and s[0][2][PAPER] > reopened[0][2][PAPER] and s[1][1] > reopened[1][1]
            ), 16, "Both transfers advanced after docked reopen")
        except AssertionError:
            print(f"Dock after bounded reacquisition: {world.clock()}, {dock_status()}", flush=True)
            raise

        comparator.lever_state(world, world, LEVER, LEVER_STATE, True)
        tick(world, 8)
        running = mounted.data(world.command(f"/data get block {BEARING} Running"))
        assert running == "0b", (running, dock_status())
        placed_ports = ((16, 118, -10), (16, 115, -10), ITEM_PORT, FLUID_PORT)
        port_states = [world.call("block", *port)["state"] for port in placed_ports]
        for placed, name, facing in zip(port_states, (ITEM, FLUID, ITEM, FLUID),
                                        ("east", "east", "west", "west"), strict=True):
            assert placed.startswith(f"create:{name}[") and f"facing={facing}" in placed, placed
        undocked = observe(world, assembled=False)
        cargo_conserved(undocked)
        assert undocked[2] == (0, 0), undocked
        world.call("save")
        world.restart()
        tick(world, 4)
        assert mounted.data(world.command(f"/data get block {BEARING} Running")) == "0b"
        assert observe(world, assembled=False) == undocked, "Undocked save changed cargo or connection"
        assert [world.call("block", *port)["state"] for port in placed_ports] == port_states
        print("Both stationary interfaces stayed disconnected after disassembly and idle reopen.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    run(parser.parse_args())
