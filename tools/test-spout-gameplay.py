#!/usr/bin/env python3
"""Exercise Spout LAN delivery, belt backpressure, and saved processing."""

import argparse
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

multiplayer = import_module("test-multiplayer")
belt = import_module("test-horizontal-belt")

GUEST = "SpoutGuest"
START = belt.START
MOTOR = belt.MOTOR
DEPOT = (9, 104, -11)
SPOUT = (6, 106, -11)
BARREL = (5, 106, -11)
HOPPER = (5, 105, -11)
INPUT = "minecraft:glass_bottle"
OUTPUT = "minecraft:potion"


def position(pos):
    return " ".join(map(str, pos))


def nbt_items(data):
    """Return item/count pairs from an Items list, including nested components."""
    match = re.search(r"\bItems: \[", data)
    if match:
        start = match.end()
    elif (match := re.search(r"block data:\s*\[", data)):
        start = match.end()
    elif data.lstrip().startswith("["):
        start = data.index("[") + 1
    else:
        return []
    depth = 1
    quoted = escaped = False
    end = start
    for end in range(start, len(data)):
        char = data[end]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                break
    contents = data[start:end]
    entries = []
    depth = 0
    quoted = escaped = False
    entry_start = None
    for index, char in enumerate(contents):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            if depth == 0:
                entry_start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and entry_start is not None:
                entry = contents[entry_start:index + 1]
                item = re.search(r'\bid: "([^"]+)"', entry)
                count = re.search(r"\b(?:count|Count): (\d+)", entry)
                if item and count:
                    entries.append((item[1], int(count[1]), entry))
    return entries


def counts(data):
    result = {}
    for item, count, _ in nbt_items(data):
        result[item] = result.get(item, 0) + count
    return result


def spout_values(control):
    data = control.command(f"/data get block {position(SPOUT)}")
    timer = re.search(r"\bProcessingTicks: (-?\d+)", data)
    amount = re.search(r"\bamount: (\d+)", data)
    if not timer:
        raise RuntimeError(f"Cannot read Spout processing state: {data}")
    return int(timer[1]), int(amount[1]) if amount else 0, data


def belt_data(control):
    return control.command(f"/data get block {START} Inventory.Items")


def add_water_spout(control, amount=250):
    control.command(f"/setblock {position(SPOUT)} create:spout")
    control.command(
        f'/data merge block {position(SPOUT)} '
        f'{{ProcessingTicks:-1,Tanks:[{{TankContent:{{Fluid:{{id:"minecraft:water",amount:{amount}}}}}}}]}}'
    )


def add_bottle_to_belt(control, *, position_value=0.5, segment=0):
    control.command(
        f'/data merge block {START} {{Inventory:{{PositiveOrder:1b,Items:['
        f'{{Item:{{id:"{INPUT}",count:1}},PrevPos:{position_value}f,Pos:{position_value}f,'
        f'Angle:180,PrevOffset:0.0f,Offset:0.0f,InSegment:{segment},InDirection:1}}]}}}}'
    )


def setup_belt_spout(control, *, tank=250, speed=-48):
    belt.connect(control)
    control.command(f"/setblock {MOTOR} create:creative_motor[facing=south]")
    control.command(f"/data merge block {MOTOR} {{ScrollValue:{speed}}}")
    add_water_spout(control, tank)
    control.command(f"/setblock {position(DEPOT)} create:depot")
    control.step_to(control.clock() + 1)


def run_backpressure(args):
    with fixture_world(args, "SpoutOutputBackpressure", belt.STRUCTURE, render=True) as control:
        setup_belt_spout(control)
        control.command(f"/item replace block {position(DEPOT)} container.0 with minecraft:diamond 64")
        add_bottle_to_belt(control)
        for _ in range(55):
            control.step_to(control.clock() + 1)
            data = belt_data(control)
            products = [(count, entry) for item, count, entry in nbt_items(data) if item == OUTPUT]
            if products:
                break
        else:
            timer, amount, spout = spout_values(control)
            raise RuntimeError(
                f"The Spout did not produce a water potion while the output Depot was full: "
                f"timer={timer}, fluid={amount}, spout={spout}; belt={belt_data(control)}"
            )
        if sum(count for count, _ in products) != 1:
            raise RuntimeError(f"The blocked belt did not retain exactly one Spout output: {data}")
        positions = [float(value) for _, entry in products
                     if (match := re.search(r"\bPos: (-?\d+(?:\.\d+)?)", entry))
                     for value in (match[1],)]
        if not positions or any(abs(value - 1.5) > 0.01 for value in positions):
            raise RuntimeError(f"The potion did not remain held at the Spout behind the full output Depot: {data}")
        timer, amount, _ = spout_values(control)
        if amount != 0:
            raise RuntimeError(f"The Spout should consume exactly 250 mB once: {amount} mB left")
        control.command(f"/item replace block {position(DEPOT)} container.0 with minecraft:air")
        for _ in range(60):
            control.step_to(control.clock() + 1)
            depot = control.command(f"/data get block {position(DEPOT)} Items")
            if counts(depot).get(OUTPUT, 0):
                break
        remaining = belt_data(control)
        if counts(depot).get(OUTPUT, 0) != 1 or counts(remaining).get(OUTPUT, 0):
            raise RuntimeError(f"Opening the Depot failed to release exactly one potion: {depot}; {remaining}")
    print("The Spout output waited at a full Depot and transferred once the Depot was cleared.")


def item_positions(data, item):
    positions = []
    for found, _, entry in nbt_items(data):
        if found == item and (match := re.search(r"\bPos: (-?\d+(?:\.\d+)?)", entry)):
            positions.append(float(match[1]))
    return positions


def run_boundaries(args):
    with fixture_world(args, "SpoutBoundaries", belt.STRUCTURE, render=False) as control:
        setup_belt_spout(control, tank=249)
        add_bottle_to_belt(control)

        # A valid bottle with one mB less than its 250 mB requirement must
        # remain at the Spout without consuming fluid or starting a cycle.
        for _ in range(24):
            control.step_to(control.clock() + 1)
            timer, amount, spout = spout_values(control)
            positions = item_positions(belt_data(control), INPUT)
            if positions and any(abs(value - 1.5) < 0.01 for value in positions):
                break
        if (timer, amount) != (-1, 249) or not positions or not any(
            abs(value - 1.5) < 0.01 for value in positions
        ):
            raise RuntimeError(f"Insufficient fluid did not hold the bottle idle at the Spout: {spout}; {belt_data(control)}")

        control.command(f"/data merge block {position(SPOUT)} {{Tanks:[{{TankContent:{{Fluid:{{id:\"minecraft:water\",amount:250}}}}}}]}}")
        control.command(f"/data merge block {MOTOR} {{ScrollValue:-48}}")
        for _ in range(24):
            control.step_to(control.clock() + 1)
            timer, amount, spout = spout_values(control)
            if timer >= 0:
                break
        else:
            raise RuntimeError(f"Valid bottle never started Spout processing: {spout}; {belt_data(control)}")
        if not any(abs(value - 1.5) < 0.01 for value in item_positions(belt_data(control), INPUT)):
            raise RuntimeError(f"Bottle was not held at the Spout when processing began: {belt_data(control)}")
        started_timer = timer
        control.step_to(control.clock() + 1)
        timer, amount, spout = spout_values(control)
        if timer != started_timer - 1 or amount != 250:
            raise RuntimeError(
                f"Powered belt did not advance the active Spout cycle: "
                f"started={started_timer}, now=({timer}, {amount}), {spout}"
            )

        # Once held, machine timing must continue even after the belt's RPM is
        # removed. The item stays centered while the independent Spout timer
        # advances to -1 without moving the held bottle or consuming fluid.
        control.command(f"/data merge block {MOTOR} {{ScrollValue:0}}")
        stopped_timer, stopped_amount, stopped_spout = spout_values(control)
        if stopped_timer != timer or stopped_amount != amount:
            raise RuntimeError(
                f"Stopping the belt changed Spout state before a tick: "
                f"powered=({timer}, {amount}), stopped=({stopped_timer}, {stopped_amount}), {stopped_spout}"
            )
        previous = stopped_timer
        for _ in range(24):
            control.step_to(control.clock() + 1)
            timer, amount, spout = spout_values(control)
            if timer != previous - 1:
                raise RuntimeError(
                    f"Spout timing stopped or skipped with zero belt speed: "
                    f"started={started_timer}, {previous} -> {timer}; {spout}; {belt_data(control)}"
                )
            previous = timer
            if timer == -1:
                break
        else:
            raise RuntimeError(f"Zero-speed Spout timer did not finish: {spout}; {belt_data(control)}")
        if (timer, amount) != (-1, 250) or counts(belt_data(control)).get(INPUT, 0) != 1 or not any(
            abs(value - 1.5) < 0.01 for value in item_positions(belt_data(control), INPUT)
        ):
            raise RuntimeError(f"Zero-speed Spout moved or consumed the held bottle: {spout}; {belt_data(control)}")

        # Restarting the belt invokes the held-item callback and fills exactly once.
        control.command(f"/data merge block {MOTOR} {{ScrollValue:-48}}")
        for _ in range(24):
            control.step_to(control.clock() + 1)
            timer, amount, spout = spout_values(control)
            if counts(belt_data(control)).get(OUTPUT, 0):
                break
        else:
            raise RuntimeError(f"Restarted belt did not fill the held bottle: {spout}; {belt_data(control)}")
        # Let the route settle so a successful fill cannot be mistaken for a
        # stuck or duplicated belt item. The sole output may now be in the
        # Depot rather than on the belt.
        for _ in range(12):
            control.step_to(control.clock() + 1)
        belt = belt_data(control)
        depot = control.command(f"/data get block {position(DEPOT)} Items")
        timer, amount, spout = spout_values(control)
        if (counts(belt).get(OUTPUT, 0) + counts(depot).get(OUTPUT, 0) != 1
                or counts(belt).get(INPUT, 0) or counts(depot).get(INPUT, 0)
                or amount != 0 or timer != -1):
            raise RuntimeError(
                f"Restarted Spout fill did not settle to one output: {spout}; belt={belt}; depot={depot}"
            )

    # Use a separate route for rejected input: the first belt's shortage
    # bottle is deliberately held in its transport state until fluid arrives.
    with fixture_world(args, "SpoutRejectedInput", belt.STRUCTURE, render=False) as control:
        setup_belt_spout(control, tank=250)
        control.command(
            f'/data merge block {START} {{Inventory:{{PositiveOrder:1b,Items:['
            '{Item:{id:"minecraft:cobblestone",count:1},PrevPos:0.5f,Pos:0.5f,Angle:180}]}}}'
        )
        for _ in range(60):
            control.step_to(control.clock() + 1)
            depot = control.command(f"/data get block {position(DEPOT)} Items")
            if counts(depot).get("minecraft:cobblestone", 0):
                break
        timer, amount, spout = spout_values(control)
        if counts(depot).get("minecraft:cobblestone", 0) != 1 or (timer, amount) != (-1, 250):
            raise RuntimeError(
                f"Rejected input did not pass through unchanged: {depot}; {spout}; "
                f"belt={belt_data(control)}"
            )
    print("Insufficient fluid held the bottle without starting; cobblestone passed through; and a held bottle filled once after belt restart and settled without duplication.")


def find_slot(client, item):
    return next((slot["slot"] for slot in client.call("menu").get("slots", [])
                 if (slot.get("stack") or {}).get("item") == item), None)


def open_barrel(guest, host):
    guest.call("tp", 5.5, 105, -8.5)
    guest.call("wait", 1)
    guest.call("look-at", BARREL[0] + 0.5, BARREL[1] + 0.5, BARREL[2] + 0.5)
    guest.call("interact", *BARREL, "south")
    multiplayer.until("guest to open the input Barrel", lambda:
                      guest.call("screen")["screen"] == "container")


def run_lan(args, scratch):
    with fixture_world(args, "SpoutLAN", belt.STRUCTURE, render=True) as host:
        setup_belt_spout(host)
        host.commands((
            f"/setblock {position(HOPPER)} minecraft:hopper[facing=down]",
            f"/setblock {position(BARREL)} minecraft:barrel[facing=up]",
        ))
        network = host.call("lan", "open", "0", "commands", "force")
        with multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{network['port']}", GUEST,
            render=True, scenario="spout-lan",
        ) as guest:
            multiplayer.until("Spout guest to join", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((f"/gamemode survival {GUEST}", f"/clear {GUEST}",
                           f"/give {GUEST} {INPUT} 1"))
            multiplayer.until("guest bottle to synchronize", lambda:
                             multiplayer.count(guest, INPUT) == 1)
            open_barrel(guest, host)
            source_slot = find_slot(guest, INPUT)
            if source_slot is None:
                raise RuntimeError(f"Guest bottle is absent from the Barrel menu: {guest.call('menu')}")
            guest.call("click-slot", source_slot, "shift")
            multiplayer.until("guest bottle to enter the source Barrel", lambda:
                             counts(host.command(f"/data get block {position(BARREL)} Items")).get(INPUT, 0) == 1)
            guest.call("close")
            multiplayer.until("guest to close the source Barrel", lambda:
                             guest.call("screen")["screen"] != "container")

            for _ in range(70):
                host.step_to(host.clock() + 1)
                if counts(host.command(f"/data get block {position(DEPOT)} Items")).get(OUTPUT, 0):
                    break
            depot = host.command(f"/data get block {position(DEPOT)} Items")
            if counts(depot).get(OUTPUT, 0) != 1:
                raise RuntimeError(f"Guest-fed bottle did not reach the output Depot: {depot}")
            guest.call("tp", 9.5, 105, -8.5)
            guest.call("wait", 1)
            guest.call("look-at", DEPOT[0] + 0.5, DEPOT[1] + 0.5, DEPOT[2] + 0.5)
            guest.call("select", 9)
            guest.call("interact", *DEPOT, "up")
            multiplayer.until("guest to collect the water potion", lambda:
                             multiplayer.count(guest, OUTPUT) == 1
                             and counts(host.command(f"/data get block {position(DEPOT)} Items")) == {})
            inventory = host.command(f"/data get entity {GUEST} Inventory")
            if 'minecraft:water' not in inventory:
                raise RuntimeError(f"Guest potion is missing the water contents: {inventory}")
            timer, amount, spout = spout_values(host)
            if amount or timer != -1:
                raise RuntimeError(f"Spout did not finish after guest collection: {spout}")
    print("A LAN guest fed a glass bottle into the belt input and collected the host-processed water potion.")


def run_reopen(args):
    with fixture_world(args, "SpoutReopen", belt.STRUCTURE, render=True) as control:
        setup_belt_spout(control, tank=500)
        control.call("save")
        control.restart()
        timer, amount, data = spout_values(control)
        if (timer, amount) != (-1, 500):
            raise RuntimeError(f"Idle Spout state changed across reopen: {data}")

        control.command(f"/data merge block {position(SPOUT)} {{Tanks:[{{TankContent:{{Fluid:{{id:\"minecraft:water\",amount:250}}}}}}]}}")
        add_bottle_to_belt(control)
        for _ in range(30):
            control.step_to(control.clock() + 1)
            timer, amount, data = spout_values(control)
            if 8 <= timer <= 15:
                break
        else:
            raise RuntimeError(f"Spout did not enter a partway filling cycle: {data}")
        saved_timer, saved_amount = timer, amount
        carried = belt_data(control)
        if counts(carried).get(INPUT, 0) != 1:
            raise RuntimeError(f"Partway save has no retained input bottle: {carried}")
        control.call("save")
        control.restart()
        timer, amount, data = spout_values(control)
        if amount != saved_amount or not 5 <= timer <= saved_timer:
            raise RuntimeError(
                f"Partway Spout timer or fluid changed across reopen: "
                f"saved=({saved_timer}, {saved_amount}), reopened=({timer}, {amount}), {data}"
            )
        if counts(belt_data(control)).get(INPUT, 0) != 1:
            raise RuntimeError("The partway bottle was lost across reopen.")
        control.step_to(control.clock() + 1)
        continued_timer, _, data = spout_values(control)
        if continued_timer != timer - 1:
            raise RuntimeError(f"Saved Spout processing did not resume: {data}")
        for _ in range(60):
            control.step_to(control.clock() + 1)
            output = control.command(f"/data get block {position(DEPOT)} Items")
            if counts(output).get(OUTPUT, 0):
                break
        if counts(output).get(OUTPUT, 0) != 1 or spout_values(control)[1] != 0:
            raise RuntimeError(f"Partway Spout operation did not finish after reopen: {output}; {spout_values(control)[2]}")
    print("Idle Spout fluid and a partway bottle/timer survived reopen; the saved fill then completed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    cases = parser.add_mutually_exclusive_group(required=True)
    cases.add_argument("--lan", action="store_true")
    cases.add_argument("--backpressure", action="store_true")
    cases.add_argument("--reopen", action="store_true")
    cases.add_argument("--boundaries", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-spout-lan-") as scratch:
            run_lan(args, scratch)
    elif args.backpressure:
        run_backpressure(args)
    elif args.boundaries:
        run_boundaries(args)
    else:
        run_reopen(args)


if __name__ == "__main__":
    main()
