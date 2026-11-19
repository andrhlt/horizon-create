#!/usr/bin/env python3
"""Give a real conductor a two-stop timetable and compare the Java trip."""
import argparse
import csv
from importlib import import_module
from math import isclose
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

conductor = import_module("test-train-conductor")
approach = import_module("test-manual-station-approach")
train = conductor.train
link = import_module("test-redstone-link")
LINK_POSITIONS = ((train.X + 12, train.Y, train.Z + 3), (train.X + 15, train.Y, train.Z + 3))
PROGRAM = ('{"create:train_schedule":{Cyclic:0b,Entries:['
           '{Conditions:[[{Data:{TimeUnit:0,Value:3},Id:"create:delay"}]],'
           'Instruction:{Data:{Text:"Origin"},Id:"create:destination"}},'
           '{Conditions:[[{Data:{TimeUnit:0,Value:5},Id:"create:delay"}]],'
           'Instruction:{Data:{Text:"Terminal"},Id:"create:destination"}}]}}')
POWER_TIME_PROGRAM = PROGRAM.replace(
    '{Data:{TimeUnit:0,Value:3},Id:"create:delay"}',
    '{Data:{},Id:"create:powered"},{Data:{Hour:6,Minute:1,Rotation:9},Id:"create:time_of_day"}',
)
FREQUENCY = 'Frequency:[{id:"minecraft:quartz",count:1},{id:"minecraft:iron_ingot",count:1}]'
LINK_PROGRAM = PROGRAM.replace(
    '{Data:{TimeUnit:0,Value:3},Id:"create:delay"}',
    '{Id:"create:redstone_link",Data:{Inverted:0,' + FREQUENCY + '}},'
    '{Id:"create:redstone_link",Data:{Inverted:1,' + FREQUENCY + '}}',
)
TITLE_THROTTLE_PROGRAM = '{"create:train_schedule":{Cyclic:0b,Entries:[{Conditions:[[{Data:{TimeUnit:0,Value:3},Id:"create:delay"}]],Instruction:{Data:{Text:"Origin"},Id:"create:destination"}},{Instruction:{Data:{Text:"Night freight"},Id:"create:rename"}},{Instruction:{Data:{Value:10},Id:"create:throttle"}},{Conditions:[[{Data:{TimeUnit:0,Value:5},Id:"create:delay"}]],Instruction:{Data:{Text:"Terminal"},Id:"create:destination"}}]}}'
REVERSE_PROGRAM = PROGRAM.replace('"Origin"', '"West"').replace('"Terminal"', '"East"').replace("Value:3", "Value:5")
ITEM_CARGO_PROGRAM = '{"create:train_schedule":{Cyclic:0b,Entries:[{Conditions:[[{Data:{Item:{count:1,id:"minecraft:paper"},Measure:1,Operator:2,Threshold:"1"},Id:"create:item_threshold"},{Data:{Item:{count:1,id:"minecraft:paper"},Measure:0,Operator:2,Threshold:"71"},Id:"create:item_threshold"}],[{Data:{Item:{count:1,id:"minecraft:paper"},Measure:0,Operator:0,Threshold:"71"},Id:"create:item_threshold"}]],Instruction:{Data:{Text:"Origin"},Id:"create:destination"}},{Conditions:[[{Data:{TimeUnit:0,Value:5},Id:"create:delay"}]],Instruction:{Data:{Text:"Terminal"},Id:"create:destination"}}]}}'
FLUID_CARGO_PROGRAM = '{"create:train_schedule":{Cyclic:0b,Entries:[{Conditions:[[{Data:{Bucket:{count:1,id:"minecraft:water_bucket"},Operator:0,Threshold:"2"},Id:"create:fluid_threshold"},{Data:{Bucket:{count:1,id:"minecraft:water_bucket"},Operator:1,Threshold:"3"},Id:"create:fluid_threshold"}],[{Data:{Bucket:{count:1,id:"minecraft:water_bucket"},Operator:2,Threshold:"2"},Id:"create:fluid_threshold"}]],Instruction:{Data:{Text:"Origin"},Id:"create:destination"}},{Conditions:[[{Data:{TimeUnit:0,Value:5},Id:"create:delay"}]],Instruction:{Data:{Text:"Terminal"},Id:"create:destination"}}]}}'
IDLE_CARGO_PROGRAM = '{"create:train_schedule":{Cyclic:0b,Entries:[{Conditions:[[{Data:{TimeUnit:0,Value:5},Id:"create:idle"}]],Instruction:{Data:{Text:"Origin"},Id:"create:destination"}},{Conditions:[[{Data:{TimeUnit:0,Value:5},Id:"create:delay"}]],Instruction:{Data:{Text:"Terminal"},Id:"create:destination"}}]}}'
PROGRAMS = {"powered_time": POWER_TIME_PROGRAM, "link": LINK_PROGRAM,
            "title_throttle": TITLE_THROTTLE_PROGRAM, "reverse": REVERSE_PROGRAM,
            "item_cargo": ITEM_CARGO_PROGRAM, "fluid_cargo": FLUID_CARGO_PROGRAM,
            "idle_cargo": IDLE_CARGO_PROGRAM, "hopper_cargo": IDLE_CARGO_PROGRAM, "hopper_cargo_insert": IDLE_CARGO_PROGRAM}
STAGES = ("PRE_TRANSIT", "IN_TRANSIT", "POST_TRANSIT")
FLUID_PORT_MODES = ("train_fluid_port", "train_fluid_port_fill", "train_fluid_port_powered", "train_fixed_port_lifecycle")
for mode in FLUID_PORT_MODES:
    PROGRAMS[mode] = IDLE_CARGO_PROGRAM.replace("Value:5", "Value:55", 1)
PORTABLE_FLUID_POS = (train.X + 3, train.Y + 3, train.Z + 2)
PUMP_POS = (train.X + 4, train.Y + 3, train.Z + 2)
PUMP_MOTOR = (train.X + 3, train.Y + 4, train.Z + 2)
PUMP_SINK = (train.X + 6, train.Y + 3, train.Z + 2)
TRAIN_WATER = 'CreateTrain.Blocks[{BlockState:{Name:"create:fluid_tank"}}].Entity.TankContent.Fluid.amount'


def coordinates(at):
    return " ".join(map(str, at))


def place_train_fluid_port(world, *, filling=False):
    place_stations(world)
    a, b, c = PORTABLE_FLUID_POS
    x, y, z = PUMP_POS
    tank = f"{x} {y} {train.Z}"
    fixed = coordinates(PUMP_SINK)
    source = fixed if filling else tank
    facing = "west" if filling else "east"
    world.commands((
        f"/setblock {a} {b} {train.Z} create:portable_fluid_interface[facing=south]",
        f"/setblock {a} {b} {c} create:portable_fluid_interface[facing=north]",
        f"/setblock {tank} create:fluid_tank",
        f"/setblock {fixed} create:fluid_tank",
        f'/data merge block {source} {{TankContent:{{Fluid:{{id:"minecraft:water",amount:2750}}}}}}',
        f"/setblock {x} {y} {z} create:mechanical_pump[facing={facing}]",
        f"/setblock {x + 1} {y} {z} create:glass_fluid_pipe[axis=x]",
        f"/setblock {x} {y + 1} {z} create:cogwheel[axis=x]",
    ))



def place_stations(world):
    approach.place_stations(world)
    conductor.scenario_setup(world)
    for pos, name in (
        (train.STATION, "Origin"),
        (approach.DESTINATION, "Terminal"),
        ((train.X - 6, train.Y, train.Z + 2), "Wrong way"),
    ):
        target = " ".join(map(str, pos))
        world.command(f'/data merge block {target} {{Name:"{name}"}}')
        if not world.command(f"/data get block {target} Name").endswith(f'"{name}"'):
            raise RuntimeError(f"Could not set {name} for the graph fixture.")


PORT_POS = (train.X + 3, train.Y + 3, train.Z + 2)
HOPPER_MODES = ("hopper_cargo", "hopper_cargo_insert")


def hopper_position(inserting):
    px, py, pz = PORT_POS
    return (px + 1, py, pz) if inserting else (px, py - 1, pz)


def hopper_lock(inserting):
    hx, hy, hz = hopper_position(inserting)
    return hx + 1, hy, hz
CHEST_ITEMS = 'CreateTrain.Blocks[{BlockState:{Name:"minecraft:chest"}}].VanillaEntity.Items'
CARGO_CHEST = "CreateTrain.Blocks[{Pos:[I;3,2,0]}]"
VAULT_ITEMS = f"{CARGO_CHEST}.Items"
LEADING_CHEST = "CreateTrain.Blocks[{Pos:[I;2,1,0]}]"


def place_mounted_storage(world, position, storage, *, pieces=64):
    target = coordinates(position)
    if storage == "vault":
        world.commands((
            f"/setblock {target} create:item_vault[axis=x]",
            f'/data merge block {target} {{Inventory:{{Items:[{{Slot:0,id:"minecraft:paper",count:{pieces}}},'
            '{Slot:1,id:"minecraft:paper",count:7},{Slot:2,id:"minecraft:redstone",count:64}]}}',
        ))
        world.step_to(world.clock() + 1)
    else:
        world.commands((
            f"/setblock {target} minecraft:{storage}",
            f"/item replace block {target} container.0 with minecraft:paper {pieces}",
            f"/item replace block {target} container.1 with minecraft:paper 7",
            f"/item replace block {target} container.2 with minecraft:redstone 64",
        ))


def add_leading_chest(world, inserting, *, barrel=False, vault=False, vanilla=None):
    x, y, z = train.X + 3, train.Y + 2, train.Z
    world.command(f"/setblock {x} {y} {z} minecraft:chest")
    if inserting:
        world.commands(f"/item replace block {x} {y} {z} container.{slot} with minecraft:paper 64"
                       for slot in range(27))
    if barrel or vault or vanilla:
        place_mounted_storage(world, (train.X + 4, train.Y + 3, train.Z),
                              "vault" if vault else vanilla or "barrel", pieces=63 if inserting else 64)


def chest_slots(reply):
    value = reply.partition("data: ")[2]
    return sorted((item["Slot"], item["id"], item["count"])
                  for item in conductor.entry.snbt(value)) if value else []


def verify_leading_chest(world, inserting):
    block, inventory = world.commands((
        f"/data get entity {train.ENTITY} {LEADING_CHEST}.BlockState.Name",
        f"/data get entity {train.ENTITY} {LEADING_CHEST}.VanillaEntity.Items",
    ))
    expected = [(slot, "minecraft:paper", 64) for slot in range(27)] if inserting else []
    if not block.endswith('"minecraft:chest"') or chest_slots(inventory) != expected:
        raise RuntimeError(f"The leading mounted chest changed or is missing: {block}, {inventory}")



def place_cargo_stations(world, *, portable=False, inserting=False):
    place_stations(world)
    x, y, z = train.X + (4 if portable else 3), train.Y + 3, train.Z
    world.commands((
        f"/setblock {x} {y} {z} minecraft:chest",
        f"/item replace block {x} {y} {z} container.0 with minecraft:paper {63 if inserting else 64}",
        f"/item replace block {x} {y} {z} container.1 with minecraft:paper 7",
        f"/item replace block {x} {y} {z} container.2 with minecraft:redstone 64",
    ))
    if portable:
        hx, hy, hz = hopper_position(inserting)
        px, py, pz = PORT_POS
        lx, ly, lz = hopper_lock(inserting)
        facing = "west" if inserting else "down"
        world.commands((
            f"/setblock {px} {py} {train.Z} create:portable_storage_interface[facing=south]",
            f"/setblock {px} {py} {pz} create:portable_storage_interface[facing=north]",
            f"/setblock {lx} {ly} {lz} minecraft:redstone_block",
            f"/setblock {hx} {hy} {hz} minecraft:hopper[facing={facing}]",
        ))
        if inserting:
            world.command(f"/item replace block {hx} {hy} {hz} container.0 with minecraft:paper")


def place_hopper_cargo_stations(world):
    place_cargo_stations(world, portable=True)


def verify_cargo(world, *, initial_count=64, two_chests=False, vault=False):
    items_path = VAULT_ITEMS if vault else f"{CARGO_CHEST}.VanillaEntity.Items" if two_chests else CHEST_ITEMS
    raw = world.command(f"/data get entity {train.ENTITY} {items_path}")
    _, found, items = raw.partition("entity data: ")
    expected = [(0, "minecraft:paper", initial_count), (1, "minecraft:paper", 7), (2, "minecraft:redstone", 64)]
    if not found:
        raise RuntimeError(f"The assembled train did not mount its loaded chest: {raw}")
    assert sorted((tag["Slot"], tag["id"], tag["count"]) for tag in conductor.entry.snbt(items)) == expected


def verify_stock_storage(world, storage):
    kinds = {
        "chest": "minecraft:chest",
        "barrel": "minecraft:barrel",
        "vault": "create:item_vault",
        "trapped_chest": "minecraft:trapped_chest",
        "purple_shulker_box": "minecraft:purple_shulker_box",
    }
    if storage == "empty":
        for kind in kinds.values():
            block = f'CreateTrain.Blocks[{{BlockState:{{Name:"{kind}"}}}}]'
            if "entity data:" in world.command(f"/data get entity {train.ENTITY} {block}"):
                raise RuntimeError(f"The empty carriage mounted {kind}")
        return
    kind = kinds[storage]
    block = f'CreateTrain.Blocks[{{BlockState:{{Name:"{kind}"}}}}]'
    item_data = "Items" if storage == "vault" else "VanillaEntity.Items"
    raw = world.command(f"/data get entity {train.ENTITY} {block}.{item_data}")
    expected = [(0, "minecraft:paper", 64), (1, "minecraft:paper", 7), (2, "minecraft:redstone", 64)]
    if chest_slots(raw) != expected:
        raise RuntimeError(f"Expected the loaded mounted {kind}, read {raw}")


TANKS = (("minecraft:water", 2750), ("minecraft:lava", 8000))


def place_fluid_cargo_stations(world):
    place_stations(world)
    y, z = train.Y + 3, train.Z
    for x, (fluid, amount) in enumerate(TANKS, start=train.X + 3):
        world.commands((
            f"/setblock {x} {y} {z} create:fluid_tank",
            f'/data merge block {x} {y} {z} {{TankContent:{{Fluid:{{id:"{fluid}",amount:{amount}}}}}}}',
        ))


def verify_fluid_cargo(world):
    for x, (fluid, amount) in enumerate(TANKS, start=2):
        selector = f"CreateTrain.Blocks[{{Pos:[I;{x},2,0]}}].Entity.TankContent.Fluid"
        raw = world.command(f"/data get entity {train.ENTITY} {selector}")
        _, found, value = raw.partition("entity data: ")
        if not found:
            raise RuntimeError(f"The assembled carriage did not mount the {fluid} tank: {raw}")
        stored = conductor.entry.snbt(value)
        if (stored.get("id"), stored.get("amount")) != (fluid, amount):
            raise RuntimeError(f"The assembled train did not preserve {amount} mB of {fluid}: {stored}")


def place_reverse_stations(world):
    approach.place_stations(world, stations=((train.X - 13, 90), (train.X + 18, -90)))
    conductor.SEATS = (train.X + 2, train.X + 3)
    conductor.scenario_setup(world)
    for pos, label in ((approach.DESTINATION, "West"), (approach.REVERSE_DESTINATION, "East")):
        x, y, z = pos
        world.command(f'/data merge block {x} {y} {z} {{Name:"{label}"}}')


def place_signal(world, ahead, *, power=True):
    x, y, z = train.X - ahead, train.Y, train.Z
    world.commands((
        "/item replace entity @s hotbar.0 with create:track_signal",
        f"/tp @s {x + 2.5} {y} {z + .5} 90 20",
    ))
    world.call("wait", 3)
    world.call("select", "create:track_signal")
    train.click_track(world, x)
    a, b, c = x, y, z + 3
    world.command(f"/tp @s {a + .5} {b} {c + 2.5} 180 20")
    world.call("wait", 3)
    world.call("interact", a, b - 1, c, "up")
    world.call("wait", 3)
    if not world.command(f"/execute if block {a} {b} {c} create:track_signal").startswith("Test passed"):
        raise RuntimeError("Could not place the westbound signal.")
    if power:
        world.command(f"/setblock {a} {b + 1} {c} minecraft:redstone_block")
    return a, b, c


def wrench_signal(world, position):
    x, y, z = position
    world.commands((
        "/item replace entity @s hotbar.0 with create:wrench",
        f"/tp @s {x + .5} {y} {z + 2.5}",
    ))
    world.call("wait", 3)
    world.call("select", "create:wrench")
    world.call("look-at", x + .5, y + .55, z + .5)
    world.call("mouse", "right", "click")
    world.call("wait", 3)


def observe(world, signal, cross, condition_mode, two_chests=False, vault=False):
    fields = [
        "Speed", "WheelPoints", "ApproachStation", "ArrivedStation", "ApproachDistance",
        "ScheduleRuntime.Stage", "ScheduleRuntime.Entry", "SchedulePaused", "ScheduleCompleted",
    ]
    if signal:
        fields.extend(("WaitingForSignal", "DistanceToSignal"))
    queries = [f"/data get entity {train.ENTITY} CreateTrain.{field}" for field in fields]
    for pos in (signal, cross):
        if pos:
            x, y, z = pos
            queries.append(f"/data get block {x} {y} {z} State")
    if condition_mode == "powered_time":
        x, y, z = train.STATION
        queries.extend((
            "/time query time",
            f"/execute if block {x} {y + 1} {z} minecraft:redstone_block",
            f"/data get entity {train.ENTITY} CreateTrain.ScheduleRuntime.Wait[0]",
        ))
    elif condition_mode == "link":
        queries.extend(f"/data get block {x} {y} {z} Transmit" for x, y, z in LINK_POSITIONS)
        queries.append(f"/data get entity {train.ENTITY} CreateTrain.ScheduleRuntime.Wait[0]")
    elif condition_mode in ("idle_cargo", *HOPPER_MODES):
        queries.extend(f"/data get entity {train.ENTITY} CreateTrain.{field}"
                       for field in ("ScheduleRuntime.Wait[0]", "CargoIdleTicks"))
        if condition_mode in HOPPER_MODES:
            hx, hy, hz = hopper_position(condition_mode == "hopper_cargo_insert")
            px, py, pz = PORT_POS
            cargo_items = VAULT_ITEMS if vault else f"{CARGO_CHEST}.VanillaEntity.Items" if two_chests else CHEST_ITEMS
            queries.extend((
                f"/data get block {px} {py} {pz} Timer",
                f"/data get entity {train.ENTITY} {cargo_items}",
                f"/data get block {hx} {hy} {hz} Items",
            ))
    elif condition_mode in FLUID_PORT_MODES:
        queries.extend((
            f"/data get entity {train.ENTITY} CreateTrain.ScheduleRuntime.Wait[0]",
            f"/data get entity {train.ENTITY} CreateTrain.CargoIdleTicks",
            f"/data get block {coordinates(PORTABLE_FLUID_POS)} Timer",
            f"/data get block {coordinates(PUMP_POS)} Speed",
            f"/data get entity {train.ENTITY} {TRAIN_WATER}",
            f"/data get block {coordinates(PUMP_SINK)} TankContent.Fluid.amount",
        ))
        if condition_mode == "train_fixed_port_lifecycle":
            queries.append(f"/data get block {coordinates(PORTABLE_FLUID_POS)} Distance")
    elif condition_mode in ("item_cargo", "fluid_cargo"):
        queries.extend(f"/data get entity {train.ENTITY} CreateTrain.ScheduleRuntime.Wait[{index}]"
                       for index in (0, 2))
    elif condition_mode == "title_throttle":
        queries.extend(f"/data get entity {train.ENTITY} CreateTrain.{field}"
                       for field in ("ScheduleRuntime.Title", "Throttle"))
    elif condition_mode == "reverse":
        queries.append(f"/data get entity {train.ENTITY} CreateTrain.ApproachBackwards")
    speed, wheels, target, arrived, distance, stage, index, paused, complete, *extra = world.commands(queries)

    def scalar(reply):
        _, separator, value = reply.partition("entity data: ")
        return value if separator else ""

    def decimal(reply):
        value = scalar(reply)
        return float(value[:-1]) if value else 0.0

    def lamp(reply):
        return reply.rsplit(" ", 1)[-1].strip('"')

    speed = decimal(speed)
    wheels = tuple(float(value) for value in re.findall(f"({train.NUMBER})d", wheels))
    if len(wheels) != 4:
        raise RuntimeError(f"Expected four train wheel positions, observed {wheels}.")
    destinations = [approach.DESTINATION]
    if condition_mode == "reverse":
        destinations.append(approach.REVERSE_DESTINATION)

    def matching_station(reply):
        return next((index for index, pos in enumerate(destinations, 1)
                     if reply.endswith("[I; " + ", ".join(map(str, pos)) + "]")), 0)

    target, arrived = matching_station(target), matching_station(arrived)
    origin = int(isclose(wheels[0], 0.5, rel_tol=0, abs_tol=1e-6) and speed == 0.0 and not arrived)
    motion = (speed, *wheels, target, arrived, decimal(distance) if target else 0.0, origin)
    runtime = (STAGES[int(scalar(stage) or "0")], int(scalar(index) or "0"),
               int(paused.endswith("1b")), int(complete.endswith("1b")))
    if condition_mode == "powered_time":
        daytime, powered, condition = extra
        return (*motion, *runtime, int(re.findall(r"(?<!\w)\d+(?!\w)", daytime)[-1]), str(powered.startswith("Test passed")).lower(),
                int(scalar(condition) or "0"))
    if condition_mode == "link":
        first, decoy, condition = extra
        return (*motion, *runtime, int(first.rsplit(" ", 1)[-1]),
                int(decoy.rsplit(" ", 1)[-1]), int(scalar(condition) or "0"))
    if condition_mode in HOPPER_MODES:
        condition, idle, port_timer, cargo, hopper = extra

        def slot_0(reply):
            result = reply.partition("data: ")[2]
            return next((entry["count"] for entry in conductor.entry.snbt(result)
                         if entry["Slot"] == 0 and entry["id"] == "minecraft:paper"), 0) if result else 0

        timer = int(port_timer.partition("data: ")[2] or 0)
        return (*motion, *runtime, int(scalar(condition) or "0"), int(scalar(idle) or "0"),
                str(4 <= timer <= 64).lower(), slot_0(cargo), slot_0(hopper))
    if condition_mode in FLUID_PORT_MODES:
        waiting, idle, port, rpm, source, sink, *extra = (reply.partition("data: ")[2] for reply in extra)
        values = (*motion, *runtime, int(waiting or 0), int(idle or 0), str(4 <= int(port or 0) <= 64).lower(),
                  float(rpm.rstrip("f") or 0), int(source or 0), int(sink or 0))
        if condition_mode == "train_fixed_port_lifecycle":
            values += (int(port or 0), float(extra[0].rstrip("f") or 0))
        return values
    if condition_mode in ("item_cargo", "fluid_cargo", "idle_cargo"):
        return (*motion, *runtime, *(int(scalar(counter) or "0") for counter in extra))
    if condition_mode == "title_throttle":
        title, throttle = extra
        return (*motion, *runtime, scalar(title).strip('"'), decimal(throttle) if scalar(throttle) else 1.0)
    if condition_mode == "reverse":
        return (*motion, *runtime, str(extra[0].endswith("1b")).lower())
    if not signal:
        return (*motion, *runtime)
    waiting, signal_distance, entry_lamp, *other = extra
    light = (lamp(entry_lamp), str(bool(scalar(waiting))).lower(), decimal(signal_distance))
    return (*motion, *runtime, *light, *((lamp(other[0]),) if cross else ()))

RENDER_TICKS = (57, 137, 138, 139, 140, 141, 142)


def capture_port_frame(world, actor, who, scenario, tick):
    x, y, z = PORTABLE_FLUID_POS
    world.command(f"/tp {who} {x - 4.5} {y + 1.2} {z + 0.3}")
    actor.call("wait", 3)
    actor.call("look-at", x + .5, y + .5, z + .5)
    if tick == RENDER_TICKS[0]:
        actor.call("key", "f1", "tap")
    actor.call("wait", 4)
    decision = world.command(f"/execute if block {x} {y} {z} create:portable_fluid_interface[extended=true]")
    extended = decision.startswith("Test passed")
    if extended != (tick < RENDER_TICKS[-1]):
        raise RuntimeError(f"Fixed port extension model state at {tick} was {extended}.")
    actor.call("screenshot", ROOT / f".local/{scenario}-{tick}.png")
    return world.clock()


def verify_port_frames(samples, multiplayer):
    label = "train-fixed-port-render"
    if multiplayer:
        log = ROOT / f".local/{label}-guest-{conductor.GUEST.lower()}.log"
    else:
        log = ROOT / f".local/horizon-{label}.log"
    with (ROOT / "fixtures/train_fixed_port_render-java.csv").open() as stream:
        expected = {int(row["tick"]): row for row in csv.DictReader(stream)}
    assert set(samples.values()) == set(expected), samples
    found = set()
    for line in log.read_text().splitlines():
        _, frame, values = line.partition("CREATE_TRAIN_PORT_FRAME ")
        if not frame:
            continue
        time, partial, prior, current, distance, yaw, pitch, lit, collar, tip, collar_vertices, tip_vertices = values.split()
        tick = samples.get(int(time))
        if tick is None or tick == RENDER_TICKS[-1]:
            continue
        row = expected[tick]
        partial, prior, current, distance, collar, tip = map(float, (partial, prior, current, distance, collar, tip))
        before, after = (float(row[key]) for key in ("extension_previous", "extension"))
        if (lit != row["lit"] or not isclose(distance * prior**2 * .5, before, abs_tol=2e-6)
                or not isclose(distance * current**2 * .5, after, abs_tol=2e-6)):
            # A client can still be drawing its previous snapshot at this tick.
            continue
        assert isclose((prior + partial * (current - prior))**2 * distance * .5, tip, abs_tol=2e-6)
        assert isclose(collar, tip * .5 + .375, abs_tol=2e-6)
        assert (int(yaw), int(pitch)) == (int(row["yaw"]), int(row["pitch"]))
        assert (int(collar_vertices), int(tip_vertices)) == (20, 60)
        found.add(tick)
    missing = set(RENDER_TICKS[:-1]) - found
    if missing:
        raise RuntimeError(f"Java-compatible fixed-port render frames missing at ticks {sorted(missing)}. See {log}.")
    print("Fixed-port mesh offsets and lighting matched six Java render phases and restored the closed model.")


def give_fixture_schedule(world, actor, who, program):
    # Seed a real stack directly into the selected hotbar for this fixture.
    # An Item entity at a joining player's spawn can be collected by the host.
    supply = coordinates((train.X + 5, train.Y + 8, train.Z))
    world.commands((
        f'/setblock {supply} minecraft:chest{{Items:[{{Slot:0b,id:"{conductor.SCHEDULE}",count:1,components:{program}}}]}}',
        f"/item replace entity {who} hotbar.0 from block {supply} container.0",
        f"/item replace block {supply} container.0 with minecraft:air",
        f"/setblock {supply} minecraft:air",
    ))
    actor.call("key", "1", "tap")
    world.step_to(world.clock() + 1)
    conductor.multiplayer.until("the supplied Schedule to be in hand", lambda: conductor.held_count(actor) == 1)


def exercise(world, actor, who, rows, scenario, signal, release_tick, cross, condition_mode,
             *, reopen=False, render_port=False, two_chests=False, vault=False, stock=False):
    world.command(f"/attribute {who} minecraft:gravity base set 0")
    if condition_mode == "powered_time":
        world.commands(("/time pause", "/time set 58"))
    elif condition_mode == "link":
        for index, (x, y, z) in enumerate(LINK_POSITIONS):
            world.commands((
                f"/setblock {x} {y - 1} {z} minecraft:smooth_stone",
                f"/setblock {x} {y} {z} create:redstone_link[facing=up,receiver=false]{link.channel(index == 0)}",
            ))
        x, y, z = LINK_POSITIONS[1]
        world.command(f"/setblock {x} {y} {z - 1} minecraft:redstone_block")
        world.step_to(world.clock() + 1)
    program = PROGRAMS.get(condition_mode, PROGRAM)
    if vault or stock or (condition_mode == "powered_time" and actor is not world):
        give_fixture_schedule(world, actor, who, program)
    else:
        conductor.set_held(world, actor, who, conductor.SCHEDULE, components=program)
    conductor.click(world, actor, who, 0)
    if conductor.assigned(world) is None:
        raise RuntimeError("The seated conductor did not take the timetable.")
    start = world.clock()
    first = int(rows[0]["tick"])
    differences = []
    matching_trace = {int(row["tick"]): row for row in rows}
    completed_reopens = []
    render_samples = {}
    game_tick = start
    observed = 0

    def compare(actual, row):
        for key, value in zip(tuple(row)[1:], actual, strict=True):
            expected = row[key]
            if key == "dock_timer" and int(row["tick"]) < 43:
                continue
            if key in ("stage", "signal", "waiting", "cross_signal", "station_powered", "title", "backwards", "connected"):
                same = value == expected
            else:
                same = isclose(value, float(expected), rel_tol=0.0, abs_tol=2e-6)
            if not same:
                differences.append(f"{row['tick']}/{key} {value} vs {expected}")

    output = ROOT / f".local/{scenario}-horizon.csv"
    with output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(rows[0].keys())
        for row in rows:
            tick = int(row["tick"])
            target_tick = start + tick - first + 1
            if target_tick <= game_tick:
                continue
            world.step_to(target_tick)
            game_tick = target_tick
            actual = observe(world, signal, cross, condition_mode, two_chests, vault)
            writer.writerow((tick, *actual))
            if render_port and tick in RENDER_TICKS:
                render_samples[capture_port_frame(world, actor, who, scenario, tick)] = tick
            compare(actual, row)
            observed += 1
            if reopen and tick in (100, 145):
                world.restart()
                game_tick = world.clock()
                resumed_tick = first + game_tick - start - 1
                compare(observe(world, signal, cross, condition_mode), matching_trace[resumed_tick])
                seats = world.command(f"/data get entity {train.ENTITY} CreateTrain.Blocks")
                if seats.count("SeatOccupant") != 2 or conductor.assigned(world) is None:
                    raise RuntimeError("Reloading changed the original occupants or timetable.")
                completed_reopens.append((tick, resumed_tick))
            if signal and tick == release_tick:
                x, y, z = signal
                world.command(f"/setblock {x} {y + 1} {z} minecraft:air")
            if condition_mode == "powered_time":
                x, y, z = train.STATION
                if tick == 32:
                    world.command(f"/setblock {x} {y + 1} {z} minecraft:redstone_block")
                elif tick == 36:
                    world.commands((f"/setblock {x} {y + 1} {z} minecraft:air", "/time set 266"))
                elif tick == 40:
                    world.command("/time set 267")
            elif condition_mode == "train_fluid_port_powered" and tick in (60, 64):
                x, y, z = PORTABLE_FLUID_POS
                block = "redstone_block" if tick == 60 else "air"
                world.command(f"/setblock {x} {y} {z + 1} minecraft:{block}")
            elif condition_mode in FLUID_PORT_MODES and tick in (27, 68):
                block = "create:creative_motor[facing=east]" if tick == 27 else "minecraft:air"
                world.command(f"/setblock {coordinates(PUMP_MOTOR)} {block}")
            elif condition_mode in HOPPER_MODES and tick in (27, 28):
                x, y, z = hopper_lock(condition_mode == "hopper_cargo_insert")
                block = "air" if tick == 27 else "redstone_block"
                world.command(f"/setblock {x} {y} {z} minecraft:{block}")
            elif condition_mode == "link" and tick in (32, 42):
                x, y, z = LINK_POSITIONS[0]
                block = "redstone_block" if tick == 32 else "air"
                world.command(f"/setblock {x} {y} {z - 1} minecraft:{block}")
    if differences:
        raise RuntimeError(f"{len(differences)} Java trip differences. " + "; ".join(differences[:18]))
    if reopen:
        if len(completed_reopens) != 2:
            raise RuntimeError(f"Expected to reopen both parked and moving states, got {completed_reopens}.")
        print(f"Parked and moving train reopens followed the matching Java trace after {completed_reopens}.")
    print(f"Conductor-driven departure, arrival, waits and completion matched {observed} Java ticks.")
    return render_samples


def run(args):
    condition_mode = None
    if args.reverse_trip:
        name, ahead, release_tick = "scheduled_reverse_trip", None, None
        condition_mode = "reverse"
    elif args.title_throttle:
        name, ahead, release_tick = "scheduled_title_throttle", None, None
        condition_mode = "title_throttle"
    elif args.idle_cargo:
        condition_mode = "idle_cargo"
        name, ahead, release_tick = "scheduled_static_idle_cargo", None, None
    elif args.train_fixed_port_lifecycle:
        condition_mode = "train_fixed_port_lifecycle"
        name, ahead, release_tick = "scheduled_train_fixed_port_lifecycle", None, None
    elif args.train_fluid_port or args.train_fluid_port_fill or args.train_fluid_port_powered:
        if args.train_fluid_port_fill:
            condition_mode = "train_fluid_port_fill"
        elif args.train_fluid_port_powered:
            condition_mode = "train_fluid_port_powered"
        else:
            condition_mode = "train_fluid_port"
        name, ahead, release_tick = f"scheduled_{condition_mode}", None, None
    elif args.hopper_cargo or args.hopper_cargo_insert:
        condition_mode = "hopper_cargo_insert" if args.hopper_cargo_insert else "hopper_cargo"
        name, ahead, release_tick = f"scheduled_{condition_mode}", None, None
    elif args.item_cargo or args.fluid_cargo:
        material = "item" if args.item_cargo else "fluid"
        condition_mode = f"{material}_cargo"
        name, ahead, release_tick = f"scheduled_static_{material}_cargo", None, None
    elif args.link:
        condition_mode = "link"
        name, ahead, release_tick = "scheduled_link", None, None
    elif args.powered_time:
        condition_mode = "powered_time"
        name, ahead, release_tick = "scheduled_powered_time", None, None
    elif args.cross_signal:
        name, ahead, release_tick = "scheduled_cross_signal", 8, 115
    elif args.moving_signal:
        name, ahead, release_tick = "scheduled_moving_signal", 8, 115
    elif args.red_signal:
        name, ahead, release_tick = "scheduled_red_signal", 4, 55
    else:
        name, ahead, release_tick = "scheduled_station_approach", None, None
    with (ROOT / f"fixtures/{name}-java.csv").open() as trace:
        rows = list(csv.DictReader(trace))
    scenario = "train-fixed-port-render" if args.render_fixed_port else name.replace("_", "-")
    if args.stock_storage:
        scenario += f"-{args.stock_storage}"
    if args.two_chests:
        scenario += "-barrel-and-chest" if args.barrel else "-vault-and-chest" if args.vault else "-two-chests"
    if args.mounted_vanilla:
        scenario += f"-{args.mounted_vanilla}"
    if args.multiplayer:
        scenario += "-guest"
    elif args.reopen:
        scenario += "-reopen"
    if args.stock_storage == "empty":
        PROGRAMS["item_cargo"] = ITEM_CARGO_PROGRAM.replace('Threshold:"1"', 'Threshold:"0"').replace('Threshold:"71"', 'Threshold:"0"')
    with fixture_world(args, scenario, train.STRUCTURE, render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        setup = place_reverse_stations if args.reverse_trip else place_stations
        if args.item_cargo and args.stock_storage:
            def setup(world):
                place_stations(world)
                if args.stock_storage != "empty":
                    place_mounted_storage(world, (train.X + 3, train.Y + 3, train.Z), args.stock_storage)
        elif args.item_cargo or args.idle_cargo:
            setup = place_cargo_stations
        elif condition_mode in FLUID_PORT_MODES:
            setup = lambda world: place_train_fluid_port(world, filling=args.train_fluid_port_fill)
        elif args.hopper_cargo_insert:
            setup = lambda world: place_cargo_stations(world, portable=True, inserting=True)
        elif args.hopper_cargo:
            setup = place_hopper_cargo_stations
        elif args.fluid_cargo:
            setup = place_fluid_cargo_stations
        before_glue = None
        if args.two_chests:
            before_glue = lambda actor: add_leading_chest(
                actor, args.hopper_cargo_insert, barrel=args.barrel, vault=args.vault, vanilla=args.mounted_vanilla
            )
        train.setup(world, after_station=setup, before_glue=before_glue, take_controls=False,
                    rear_controls=args.reverse_trip)
        if args.two_chests:
            verify_leading_chest(world, args.hopper_cargo_insert)
        if args.barrel or args.vault or args.mounted_vanilla:
            kind = "create:item_vault" if args.vault else f"minecraft:{args.mounted_vanilla or 'barrel'}"
            rear = world.command(f"/data get entity {train.ENTITY} {CARGO_CHEST}.BlockState.Name")
            if not rear.endswith(f'"{kind}"'):
                raise RuntimeError(f"The rear {kind} did not mount: {rear}")
        if args.stock_storage:
            verify_stock_storage(world, args.stock_storage)
        elif args.item_cargo or args.idle_cargo or args.hopper_cargo or args.hopper_cargo_insert:
            verify_cargo(world, initial_count=63 if args.hopper_cargo_insert else 64, two_chests=args.two_chests, vault=args.vault)
        elif args.fluid_cargo:
            verify_fluid_cargo(world)
        elif condition_mode in FLUID_PORT_MODES:
            carriage_tank = 'CreateTrain.Blocks[{BlockState:{Name:"create:fluid_tank"}}]'
            stored = world.command(f"/data get entity {train.ENTITY} {carriage_tank}")
            if "entity data:" not in stored or ("amount: 2750" in stored) == args.train_fluid_port_fill:
                raise RuntimeError(f"Expected the original mounted tank, read {stored}")
        signal = place_signal(world, ahead) if ahead else None
        cross = None
        if args.cross_signal:
            world.step_to(world.clock() + 1)
            cross = place_signal(world, 4, power=False)
            for _ in range(4):
                world.step_to(world.clock() + 1)
            wrench_signal(world, cross)
        elif signal:
            for _ in range(7):
                world.step_to(world.clock() + 1)
            x, y, z = signal
            if not world.command(f"/data get block {x} {y} {z} State").endswith('"RED"'):
                raise RuntimeError("The westbound signal did not start red.")
        if not args.multiplayer:
            samples = exercise(world, world, "@s", rows, scenario, signal, release_tick, cross,
                               condition_mode, reopen=args.reopen, render_port=args.render_fixed_port,
                               two_chests=args.two_chests, vault=args.vault, stock=bool(args.stock_storage or args.mounted_vanilla))
            if args.two_chests:
                verify_leading_chest(world, args.hopper_cargo_insert)
                verify_cargo(world, initial_count=64 if args.hopper_cargo_insert else 63, two_chests=True, vault=args.vault)
            return samples
        guest_name = conductor.GUEST
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-dispatch-") as scratch, conductor.multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", guest_name,
            render=args.render_fixed_port, scenario=scenario, pack=args.pack,
        ) as guest:
            conductor.multiplayer.until("the timetable guest to join", lambda: any(
                link["name"] == guest_name and link["placed"]
                for link in world.call("lan", "status")["guests"]
            ))
            world.command(f"/gamemode survival {guest_name}")
            samples = exercise(world, guest, guest_name, rows, scenario, signal, release_tick,
                               cross, condition_mode, render_port=args.render_fixed_port, two_chests=args.two_chests, vault=args.vault, stock=bool(args.stock_storage or args.mounted_vanilla))
            if args.two_chests:
                verify_leading_chest(world, args.hopper_cargo_insert)
                verify_cargo(world, initial_count=64 if args.hopper_cargo_insert else 63, two_chests=True, vault=args.vault)
            return samples


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--render-fixed-port", action="store_true")
    session = parser.add_mutually_exclusive_group()
    session.add_argument("--multiplayer", action="store_true")
    session.add_argument("--reopen", action="store_true")
    variants = parser.add_mutually_exclusive_group()
    variants.add_argument("--red-signal", action="store_true")
    variants.add_argument("--moving-signal", action="store_true")
    variants.add_argument("--cross-signal", action="store_true")
    variants.add_argument("--powered-time", action="store_true")
    variants.add_argument("--link", action="store_true")
    variants.add_argument("--item-cargo", action="store_true")
    variants.add_argument("--fluid-cargo", action="store_true")
    variants.add_argument("--idle-cargo", action="store_true")
    variants.add_argument("--hopper-cargo", action="store_true")
    variants.add_argument("--train-fluid-port", action="store_true")
    variants.add_argument("--train-fluid-port-fill", action="store_true")
    variants.add_argument("--train-fluid-port-powered", action="store_true")
    variants.add_argument("--train-fixed-port-lifecycle", action="store_true")
    variants.add_argument("--hopper-cargo-insert", action="store_true")
    variants.add_argument("--title-throttle", action="store_true")
    variants.add_argument("--reverse-trip", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--two-chests", action="store_true")
    storage = parser.add_mutually_exclusive_group()
    storage.add_argument("--barrel", action="store_true")
    storage.add_argument("--vault", action="store_true")
    parser.add_argument("--stock-storage", choices=("barrel", "vault", "empty", "trapped_chest", "purple_shulker_box"))
    storage.add_argument("--mounted-vanilla", choices=("trapped_chest", "purple_shulker_box"))
    args = parser.parse_args()
    if args.mounted_vanilla and not args.two_chests:
        parser.error("--mounted-vanilla requires --two-chests")
    if args.stock_storage and not args.item_cargo:
        parser.error("--stock-storage requires --item-cargo")
    if (args.barrel or args.vault) and not args.two_chests:
        parser.error("--barrel or --vault requires --two-chests")
    if args.two_chests and not (args.hopper_cargo or args.hopper_cargo_insert):
        parser.error("--two-chests requires a hopper cargo fixture")
    if args.reopen and not args.reverse_trip:
        parser.error("--reopen uses the bidirectional timetable fixture")
    if args.render_fixed_port:
        if not args.train_fixed_port_lifecycle:
            parser.error("--render-fixed-port requires --train-fixed-port-lifecycle")
        os.environ["CREATE_TRAIN_PORT_RENDER"] = ",".join(map(str, PORTABLE_FLUID_POS))
    render_samples = run(args)
    if args.render_fixed_port:
        verify_port_frames(render_samples, args.multiplayer)
