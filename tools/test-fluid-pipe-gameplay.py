#!/usr/bin/env python3
"""Exercise Create pipe acquisition, player interactions and fluid continuity."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

pipes = import_module("test-encased-fluid-pipe")
crafting = import_module("test-machine-crafting")
multiplayer = import_module("test-multiplayer")
PIPE, GLASS, SMART = (f"create:{name}fluid_pipe" for name in ("", "glass_", "smart_"))
WRENCH = "create:wrench"
WATER, LAVA = "minecraft:water", "minecraft:lava"
WATER_BUCKET, LAVA_BUCKET = f"{WATER}_bucket", f"{LAVA}_bucket"
ENV = {"HORIZON_NO_AUDIO": "1"}
STRAIGHT_WET = f"{PIPE}[east=true,west=true,north=false,south=false,up=false,down=false,waterlogged=true]"
GLASS_X = f"{GLASS}[axis=x,waterlogged=true]"


def block(control, pos, block_id, **properties):
    data = control.call("block", *pos)["state"]
    name, _, suffix = data.partition("[")
    actual = dict(entry.split("=", 1) for entry in suffix.rstrip("]").split(",") if entry)
    return name == block_id and all(actual.get(key) == value for key, value in properties.items())


def observe(host, actor, pos, block_id, **properties):
    multiplayer.until(f"{pos} to be {block_id} {properties} on host",
                      lambda: block(host, pos, block_id, **properties))
    if actor is not host:
        multiplayer.until(f"{pos} to reach the LAN guest",
                          lambda: block(actor, pos, block_id, **properties))


def move(host, actor, player, x, y, z):
    host.command(f"/tp {player} {x} {y} {z}")
    multiplayer.until(f"{player} to reach {(x, y, z)}", lambda: all(
        abs(actual - target) < 0.01
        for actual, target in zip(actor.call("state")["player"]["position"], (x, y, z), strict=True)
    ))


def filter_value(host, pos):
    data = host.command(f"/data get block {pipes.coords(pos)} Filter")
    if data == "Found no elements matching Filter":
        return None
    if "has the following block data" not in data:
        raise RuntimeError(f"Could not read the Smart Pipe filter at {pos}: {data}")
    match = re.search(r'id: "([^"]+)"', data)
    return match[1] if match else None


def set_filter(host, actor, pos, item, height):
    actor.call("select", item or 9)
    initial_count = pipes.inventory(actor, item) if item else None
    if item:
        assert initial_count > 0, actor.call("inventory")["counts"]
    pipes.aim(actor, pos, height)
    target = actor.call("looking-at").get("block")
    if not target or target["pos"] != list(pos):
        raise RuntimeError(f"Filter aim at {target}; expected {pos}")
    actor.call("mouse", "right", "click")
    multiplayer.until(f"Smart Pipe filter to become {item}",
                      lambda: filter_value(host, pos) == item)
    if item:
        current_count = pipes.inventory(actor, item)
        assert current_count == initial_count, (item, initial_count, current_count, actor.call("inventory")["counts"])


def craft_pipes(host):
    for name, slots, count in (
        ("fluid_pipe", "create:copper_sheet,minecraft:copper_ingot,create:copper_sheet", 4),
        ("fluid_pipe_vertical", "create:copper_sheet,minecraft:copper_ingot,create:copper_sheet", 4),
        ("smart_fluid_pipe", "create:brass_sheet,create:fluid_pipe,create:electron_tube", 1),
    ):
        crafting.replay(host, {
            "recipe": f"crafting/kinetics/{name}",
            "width": "3" if name == "fluid_pipe" else "1",
            "slots": slots,
            "output": SMART if name == "smart_fluid_pipe" else PIPE,
            "count": str(count),
            "remainder": "",
        })


def interactions(args):
    name = "FluidPipeGameplayLAN" if args.lan else "FluidPipeGameplay"
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, name, render=not args.lan, pack=args.pack, env=ENV))
        actor, player = pipes.test_actor(stack, args, host, name)
        host.commands((
            "/fill 8 169 16 24 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            f"/gamemode survival {player}",
        ))
        if not args.lan:
            move(host, actor, player, 12.5, 170, 26.5)
            craft_pipes(host)

        pos = (12, 170, 20)
        host.commands((
            "/setblock 11 170 20 create:fluid_tank",
            f"/item replace entity {player} hotbar.0 with {PIPE}",
            f"/item replace entity {player} hotbar.1 with {WRENCH}",
            f"/item replace entity {player} hotbar.2 with {WATER_BUCKET}",
            f"/item replace entity {player} hotbar.3 with {LAVA_BUCKET}",
            f"/item replace entity {player} hotbar.4 with {SMART}",
        ))
        move(host, actor, player, 12.5, 170, 22.5)
        multiplayer.until("Fluid Pipe in the hotbar", lambda: pipes.inventory(actor, PIPE) == 1)
        actor.call("select", PIPE)
        actor.call("interact", 12, 169, 20, "up")
        observe(host, actor, pos, PIPE, east="true", west="true", north="false", south="false")

        # A perpendicular neighbor adds a bend, and removal restores the straight pipe.
        host.command("/setblock 12 170 19 create:fluid_tank")
        observe(host, actor, pos, PIPE, north="true", west="true", east="false", south="false")
        host.command("/setblock 12 170 19 minecraft:air")
        observe(host, actor, pos, PIPE, east="true", west="true", north="false")
        host.command(f"/setblock {pipes.coords(pos)} {STRAIGHT_WET}")
        observe(host, actor, pos, PIPE, waterlogged="true")
        move(host, actor, player, 14.5, 170, 20.5)
        actor.call("select", WRENCH)
        actor.call("interact", *pos, "east")
        observe(host, actor, pos, PIPE, east="true", west="true", waterlogged="true")
        move(host, actor, player, 12.5, 170, 22.5)
        pipes.use(actor, pos, WRENCH)
        observe(host, actor, pos, GLASS, axis="x", waterlogged="true")
        pipes.use(actor, pos, WRENCH)
        observe(host, actor, pos, PIPE, east="true", west="true", waterlogged="true")
        pipes.use(actor, pos, WRENCH)
        observe(host, actor, pos, GLASS, axis="x", waterlogged="true")
        pipes.use(actor, pos, WRENCH, sneak=True)
        observe(host, actor, pos, WATER)
        multiplayer.until("exactly one Fluid Pipe returned by the Wrench",
                          lambda: pipes.inventory(actor, PIPE) == 1)

        # The wall model uses its vertical openings even with horizontal facing.
        smart_pos = (16, 171, 20)
        host.command("/setblock 16 170 20 create:fluid_tank")
        move(host, actor, player, 16.5, 170, 22.5)
        actor.call("select", SMART)
        actor.call("interact", 16, 170, 20, "up")
        observe(host, actor, smart_pos, SMART, face="wall")

        # Use the canonical wall pose to aim at the slot from a known position.
        host.commands((
            f"/setblock {pipes.coords(smart_pos)} {SMART}[face=wall,facing=north]",
            "/setblock 16 170 18 minecraft:stone",
            f"/item replace entity {player} hotbar.8 with minecraft:air",
        ))
        observe(host, actor, smart_pos, SMART, face="wall", facing="north")
        move(host, actor, player, 16.5, 171, 18.5)
        for item in (WATER_BUCKET, LAVA_BUCKET, None, WATER_BUCKET):
            set_filter(host, actor, smart_pos, item, .71)
        if not args.lan:
            host.command(f"/setblock 12 170 20 {GLASS_X}")
            host.restart()
            observe(host, host, pos, GLASS, axis="x", waterlogged="true")
            observe(host, host, smart_pos, SMART, face="wall", facing="north")
            assert filter_value(host, smart_pos) == WATER_BUCKET
    print(f"{name}: placement, wrench conversion and pickup, filter replace/clear passed."
          + (" Both LAN clients converged." if args.lan else " All three recipes and idle reopen passed."))


def storage(host, at):
    data = host.command(f"/data get block {pipes.coords(at)} TankContent")
    if "has the following block data" not in data:
        raise RuntimeError(f"Could not read the tank at {at}: {data}")
    amount = re.search(r"\bamount: (\d+)", data)
    if not amount:
        return None, 0
    fluid = re.search(r'id: "([^"]+)"', data)
    return fluid[1], int(amount[1])


def fill(host, at, fluid, amount):
    contents = f'{{Fluid:{{id:"{fluid}",amount:{amount}}}}}' if amount else "{}"
    host.command(f"/data merge block {pipes.coords(at)} {{TankContent:{contents}}}")
    if amount == 0 and storage(host, at)[1] != 0:
        host.command(f"/data remove block {pipes.coords(at)} TankContent.Fluid")
    assert storage(host, at) == ((fluid, amount) if amount else (None, 0))


def advance(host, ticks):
    start = host.clock()
    host.command(f"/tick step {ticks}")
    multiplayer.until(f"the server to finish {ticks} ticks", lambda: host.clock() == start + ticks)


def rig(host, x, fluid, amount, filter_item):
    host.commands((
        f"/setblock {x} 171 20 create:fluid_tank",
        f"/setblock {x} 172 20 create:mechanical_pump[facing=up]",
        f"/setblock {x + 1} 172 20 create:cogwheel[axis=y]",
        f"/setblock {x + 1} 171 20 create:creative_motor[facing=up]{{ScrollValue:128}}",
        f'/setblock {x} 173 20 {SMART}[face=wall,facing=north]{{Filter:{{id:"{filter_item}",count:1}}}}',
        f"/setblock {x} 174 20 {GLASS}[axis=y]",
        f"/setblock {x} 175 20 create:fluid_tank",
    ))
    fill(host, (x, 171, 20), fluid, amount)


def balances(host, x, fluid, total):
    before, after = (storage(host, (x, y, 20)) for y in (171, 175))
    assert all(entry[0] in (None, fluid) for entry in (before, after)), (before, after)
    assert before[1] + after[1] == total, (before, after)
    return before[1], after[1]


def lifecycle(args):
    with fixture_world(args, "FluidPipeLifecycle", pack=args.pack, env=ENV) as host:
        # Different fluids run side by side. The lava filter initially rejects.
        rig(host, 10, WATER, 7000, WATER_BUCKET)
        rig(host, 16, LAVA, 1000, WATER_BUCKET)
        fill(host, (10, 175, 20), WATER, 8000)
        advance(host, 22)
        for x in (10, 16):
            speed = host.command(f"/data get block {x} 172 20 Speed")
            assert re.search(r"(?<![.\d])-?128\.0f\b", speed), speed
        assert balances(host, 10, WATER, 15000) == (7000, 8000)
        assert balances(host, 16, LAVA, 1000) == (1000, 0)
        fill(host, (10, 175, 20), WATER, 0)
        host.command(f'/data merge block 16 173 20 {{Filter:{{id:"{LAVA_BUCKET}",count:1}}}}')
        advance(host, 24)
        before = balances(host, 10, WATER, 7000)
        assert 0 < before[1] < 7000, before
        assert balances(host, 16, LAVA, 1000) == (0, 1000)
        host.restart()
        assert filter_value(host, (10, 173, 20)) == WATER_BUCKET
        assert filter_value(host, (16, 173, 20)) == LAVA_BUCKET
        observe(host, host, (10, 174, 20), GLASS, axis="y")
        after = balances(host, 10, WATER, 7000)
        assert after[1] >= before[1], (before, after)

        # Block the open break to keep all fluid measurable in the two tanks.
        host.command("/setblock 10 174 20 minecraft:stone")
        blocked = balances(host, 10, WATER, 7000)
        advance(host, 16)
        assert balances(host, 10, WATER, 7000) == blocked
        host.command(f"/setblock 10 174 20 {GLASS}[axis=y]")
        advance(host, 150)
        assert balances(host, 10, WATER, 7000) == (0, 7000)
        assert balances(host, 16, LAVA, 1000) == (0, 1000)
        # Empty-source control: both pumps stay driven after the tanks drain,
        # and neither destination can gain fluid on subsequent powered ticks.
        empty_source_balances = (balances(host, 10, WATER, 7000), balances(host, 16, LAVA, 1000))
        advance(host, 20)
        assert (balances(host, 10, WATER, 7000), balances(host, 16, LAVA, 1000)) == empty_source_balances
        for x in (10, 16):
            assert abs(pipes.branched.reading(host.command(f"/data get block {x} 172 20"), "Speed")) == 128
    print("Vertical linear flow, full and empty tanks, mixed-fluid separation, active reopen and powered reconnect passed.")


def collision(args):
    template = "gametest/fluids/3_pipe_combine"
    path = ROOT / "fixtures/fluid-pipe-collision-java.csv"
    with path.open(newline="") as stream:
        reader = csv.reader(stream)
        header, expected = next(reader), list(reader)
    actual = []
    with fixture_world(args, "FluidPipeCollision", Path(template + ".nbt"), pack=args.pack, env=ENV) as host:
        host.commands((
            f"/place template create:{template} 3 96 -12",
            "/setblock 5 97 -10 create:mechanical_pump[facing=east,waterlogged=false]",
            "/setblock 6 100 -8 minecraft:stone",
            "/tp @s 6.5 101 -7.5",
        ))
        source_lava = (8, 97, -11)
        sources_water = ((8, 97, -10), (8, 97, -9))
        destination = (4, 97, -10)
        junction = (6, 97, -10)
        fill(host, source_lava, LAVA, 3022)
        start = host.clock()
        for row in expected:
            tick = int(row[0])
            if tick:
                host.step_to(start + tick)
            at = pipes.coords(junction)
            cobble, basic, pipe_items = host.commands((
                f"/execute if block {at} minecraft:cobblestone",
                f"/execute if block {at} {PIPE}",
                f'/data get entity @e[type=minecraft:item,nbt={{Item:{{id:"{PIPE}"}}}},limit=1] Item.count',
            ))
            if cobble.startswith("Test passed"):
                junction_block = "minecraft:cobblestone"
            elif basic.startswith("Test passed"):
                junction_block = PIPE
            else:
                raise RuntimeError(f"Unexpected junction at tick {tick}: {host.call('block', *junction)}")
            count = re.search(r"has the following entity data: (\d+)", pipe_items)
            dropped = int(count[1]) if count else 0
            received = storage(host, destination)
            water = [storage(host, at) for at in sources_water]
            lava = storage(host, source_lava)
            assert lava[0] == LAVA and all(entry[0] == WATER for entry in water), (lava, water)
            assert lava[1] + (received[1] if received[0] == LAVA else 0) == 3022
            assert sum(entry[1] for entry in water) + (received[1] if received[0] == WATER else 0) == 7978
            row = (tick, junction_block, dropped, received[0] or "minecraft:empty",
                   received[1], lava[1], *(entry[1] for entry in water))
            actual.append(list(map(str, row)))
    output = ROOT / ".local/fluid-pipe-collision-horizon.csv"
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(java, horizon) for java, horizon in zip(expected, actual, strict=True) if java != horizon]
    if differences:
        raise RuntimeError(f"Conflicting fronts differed on {len(differences)} Java samples: {differences[:5]}")
    print(f"Conflicting water/lava fronts matched all {len(expected)} Java ticks. "
          "The junction became cobblestone, dropped one basic pipe, and conserved both fluids.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda value: Path(value).resolve(strict=True))
    scenario = parser.add_mutually_exclusive_group()
    scenario.add_argument("--lan", action="store_true")
    scenario.add_argument("--lifecycle", action="store_true")
    scenario.add_argument("--collision", action="store_true")
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    if args.lifecycle:
        lifecycle(args)
    elif args.collision:
        collision(args)
    else:
        interactions(args)


if __name__ == "__main__":
    main()
