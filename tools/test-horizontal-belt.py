#!/usr/bin/env python3
"""Connect a belt in Horizon and replay Java's reversal and depot handoff."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")

STRUCTURE = Path("gametest/processing/wheat_milling.nbt")
START = "5 104 -11"
MOTOR = "5 104 -12"
DEPOT = "9 104 -11"


def motor_speed(control, speed):
    control.command(f"/data merge block {MOTOR} {{ScrollValue:{speed}}}")


def connect(control):
    control.commands((
        "/fill 3 103 -15 12 103 -6 minecraft:smooth_stone",
        f"/setblock {START} create:shaft[axis=z]",
        "/setblock 8 104 -11 create:shaft[axis=z]",
        "/setblock 6 104 -11 minecraft:short_grass",
        "/give @s create:belt_connector",
    ))
    control.call("tp", 6.5, 104, -8.5)
    control.call("select", "create:belt_connector")
    for _ in range(3):
        if "create:belt_connector" in control.command("/data get entity @s SelectedItem"):
            break
        control.call("wait", 1)
    else:
        raise RuntimeError("The server did not equip the connector")
    for _ in range(2):
        control.call("interact", 5, 104, -11)
        if "CreateBeltFirstShaft" in control.command("/data get entity @s SelectedItem"):
            break
    else:
        raise RuntimeError("The first shaft was never selected")

    for _ in range(5):
        control.step_to(control.clock() + 1)
    control.call("interact", 8, 104, -11)
    for x, part in ((5, "start"), (6, "middle"), (7, "middle"), (8, "end")):
        info = control.call("block", x, 104, -11)
        if not info["state"].startswith("create:belt[") or f"part={part}" not in info["state"]:
            raise RuntimeError(f"Connector did not place the {part} at x={x}: {info}")


def sample(control, tick):
    belt, depot = control.commands((f"/data get block {START}", f"/data get block {DEPOT}"))
    speed = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)", belt)
    if not speed or "create:depot" not in depot:
        raise RuntimeError(f"Cannot read belt or depot: {belt}, {depot}")
    positions = {"iron": -1.0, "gold": -1.0}
    for carried in re.findall(r"\{([^{}]*\{[^{}]*\}[^{}]*)\}", belt):
        item = re.search(r'\bid: "minecraft:(iron|gold)_ingot"', carried)
        pos = re.search(r"\bPos: (-?\d+(?:\.\d+)?)", carried)
        if item and pos:
            positions[item[1]] = float(pos[1])
    # The Java fixture inserts one of each ingot and keeps the depot output single-stack.
    return [str(tick), str(int(float(speed[1]))),
            *(f"{positions[item]:.7f}" for item in ("iron", "gold")),
            *(str(int(f'"minecraft:{item}_ingot"' in depot)) for item in ("iron", "gold"))]


def run(args):
    with (ROOT / "fixtures/horizontal_belt-java.csv").open() as file:
        rows = csv.reader(file)
        header, expected = next(rows), list(rows)
    actual = []
    with fixture_world(args, "Horizontal-belt", STRUCTURE, render=True) as control:
        connect(control)
        control.command(f"/setblock {MOTOR} create:creative_motor[facing=south]")
        motor_speed(control, -48)
        control.command(f"/setblock {DEPOT} create:depot")
        control.step_to(control.clock() + 1)
        control.command(
            f'/data merge block {START} {{Inventory:{{PositiveOrder:1b,Items:['
            '{Item:{id:"minecraft:iron_ingot",count:1},PrevPos:0.4375f,Pos:0.4375f,Angle:180},'
            '{Item:{id:"minecraft:gold_ingot",count:1},PrevPos:1.7375f,Pos:1.7375f,Angle:180}]}}'
        )
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
            if tick in (17, 25):
                motor_speed(control, 48 if tick == 17 else -48)
            if tick == 53:
                control.command(f"/item replace block {DEPOT} container.0 with minecraft:air")
            if tick == 8:
                control.command("/time set noon")
                control.call("look-at", 7, 104.6, -10.2)
                control.call("key", "f1", "tap")
                control.call("wait", 4)
                control.call("screenshot", ROOT / ".local/horizontal_belt.png")
    path = ROOT / ".local/horizontal_belt-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [
        (a, b) for a, b in zip(expected, actual, strict=True)
        if a[:2] != b[:2] or a[4:] != b[4:] or
        any(abs(float(a[i]) - float(b[i])) > 0.000001 for i in (2, 3))
    ]
    if differences:
        raise SystemExit(f"Belt differs on {len(differences)} ticks. "
                         f"First rows (Java, Horizon): {differences[:5]}. See {path}")
    print(f"Horizontal belt matched {len(actual)} Java ticks. See {path}")


def run_reopen(args):
    with fixture_world(args, "Horizontal-belt-reopen", STRUCTURE, render=False) as control:
        connect(control)
        control.command(f"/setblock {MOTOR} create:creative_motor[facing=south]")
        motor_speed(control, 0)
        control.step_to(control.clock() + 1)
        end = "8 104 -11"
        layout = tuple(control.call("block", *map(int, pos.split()))["state"] for pos in (START, end))
        control.call("save")
        control.restart()
        reopened = tuple(control.call("block", *map(int, pos.split()))["state"] for pos in (START, end))
        if reopened != layout:
            raise RuntimeError(f"Idle belt connections changed across save/reopen: {layout} -> {reopened}")

        motor_speed(control, 48)
        control.command(
            f'/data merge block {START} {{Inventory:{{PositiveOrder:1b,Items:['
            '{Item:{id:"minecraft:iron_ingot",count:1},PrevPos:2.5f,Pos:2.5f,Angle:180}]}}'
        )
        for _ in range(4):
            control.step_to(control.clock() + 1)

        def carried():
            data = control.command(f"/data get block {START} Inventory.Items")
            count = sum(map(int, re.findall(r"count: (\d+)", data)))
            positions = [float(value) for value in re.findall(r"\bPos: (-?\d+(?:\.\d+)?)", data)]
            return count, positions, data

        def speed():
            data = control.command(f"/data get block {START}")
            match = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)", data)
            return float(match[1]) if match else 0.0

        count_before, position_before, data_before = carried()
        if count_before != 1 or not position_before:
            raise RuntimeError(f"Active belt lost its iron ingot before save: {data_before}")
        control.call("save")
        control.restart()
        control.step_to(control.clock() + 1)
        count_after, position_after, data_after = carried()
        if count_after != 1 or not position_after or speed() != 48:
            raise RuntimeError(f"Active belt cargo or speed changed across reopen: speed={speed()}, {data_after}")
        for _ in range(4):
            control.step_to(control.clock() + 1)
        count_resumed, position_resumed, data_resumed = carried()
        if count_resumed != 1 or not position_resumed or position_resumed[0] == position_after[0]:
            raise RuntimeError(f"Active belt did not resume moving its retained item: {data_resumed}")
    print("Idle belt connections and active moving cargo/speed survived save/reopen; item travel resumed.")


def run_backpressure(args):
    with fixture_world(args, "Horizontal-belt-backpressure", STRUCTURE, render=True) as control:
        connect(control)
        control.commands((
            f"/setblock {MOTOR} create:creative_motor[facing=south]",
            f"/data merge block {MOTOR} {{ScrollValue:-48}}",
            f"/setblock {DEPOT} create:depot",
            f"/item replace block {DEPOT} container.0 with minecraft:diamond 64",
        ))
        control.step_to(control.clock() + 1)
        control.command(
            f'/data merge block {START} {{Inventory:{{PositiveOrder:1b,Items:['
            '{Item:{id:"minecraft:iron_ingot",count:1},PrevPos:0.5f,Pos:0.5f,Angle:180}]}}'
        )
        for _ in range(40):
            control.step_to(control.clock() + 1)
        data = control.command(f"/data get block {START} Inventory.Items")
        count = sum(map(int, re.findall(r"count: (\d+)", data)))
        positions = [float(value) for value in re.findall(r"\bPos: (-?\d+(?:\.\d+)?)", data)]
        depot = control.command(f"/data get block {DEPOT} Items")
        if count != 1 or not positions or positions[0] < 3.5 or "minecraft:diamond" not in depot:
            speed_data = control.command(f"/data get block {START} Speed")
            raise RuntimeError(f"Full Depot did not hold the Belt's iron ingot at its output: {data}; {depot}; {speed_data}")
        control.command(f"/item replace block {DEPOT} container.0 with minecraft:air")
        for _ in range(8):
            control.step_to(control.clock() + 1)
        remaining = control.command(f"/data get block {START} Inventory.Items")
        depot = control.command(f"/data get block {DEPOT} Items")
        if "minecraft:iron_ingot" not in depot or "minecraft:iron_ingot" in remaining:
            raise RuntimeError(f"Belt did not resume transfer after Depot space opened: {remaining}; {depot}")
    print("A full Depot backpressured the moving item; opening its slot resumed transfer without item loss.")


def run_lan(args):
    guest_name = "BeltGuest"
    with TemporaryDirectory(prefix="hc-belt-lan-") as directory:
        with fixture_world(args, "Horizontal-belt-lan", STRUCTURE, render=True) as host:
            host.commands((
                "/fill 3 103 -15 12 103 -6 minecraft:smooth_stone",
                f"/setblock {START} create:shaft[axis=z]",
                "/setblock 6 104 -11 create:shaft[axis=z]",
                "/setblock 8 104 -11 create:shaft[axis=z]",
            ))
            network = host.call("lan", "open", "0", "commands", "force")
            with multiplayer.joined_client(
                args, Path(directory), f"127.0.0.1:{network['port']}", guest_name,
                render=True, scenario="horizontal-belt-lan",
            ) as guest:
                multiplayer.until("belt guest joined", lambda: any(
                    player["name"] == guest_name and player["placed"]
                    for player in host.call("lan", "status")["guests"]
                ))
                host.commands((f"/gamemode survival {guest_name}", f"/give {guest_name} create:belt_connector"))
                guest.call("tp", 6.5, 104, -8.5)
                guest.call("select", "create:belt_connector")
                multiplayer.until("guest received Belt Connector", lambda:
                                 multiplayer.count(guest, "create:belt_connector") == 1)
                guest.call("interact", 5, 104, -11)
                guest.call("wait", 2)
                host.command("/setblock 8 104 -11 create:shaft[axis=x]")
                guest.call("interact", 8, 104, -11)
                guest.call("wait", 2)
                if not host.call("block", 5, 104, -11)["state"].startswith("create:shaft["):
                    raise RuntimeError("A connector with mismatched shaft axes placed a belt")
                host.command("/setblock 8 104 -11 create:shaft[axis=z]")
                guest.call("key", "shift", "down")
                guest.call("interact", 5, 104, -11)
                guest.call("key", "shift", "up")
                guest.call("wait", 2)
                shaft = host.call("block", 5, 104, -11)["state"]
                if not shaft.startswith("create:shaft[axis=z"):
                    raise RuntimeError(f"Sneaking should clear selection without placing a belt: {shaft}")
                if multiplayer.count(guest, "create:belt_connector") != 1:
                    raise RuntimeError("Sneaking cleared selection but consumed the Connector")
                guest.call("interact", 8, 104, -11)
                guest.call("wait", 2)
                guest.call("interact", 5, 104, -11)
                for pos, part in (((5, 104, -11), "end"), ((6, 104, -11), "pulley"),
                                  ((7, 104, -11), "middle"), ((8, 104, -11), "start")):
                    multiplayer.until(f"host saw {part} at {pos}", lambda pos=pos, part=part: (
                        (state := host.call("block", *pos)["state"]).startswith("create:belt[")
                        and f"part={part}" in state
                    ))
                if multiplayer.count(guest, "create:belt_connector") != 0:
                    raise RuntimeError("Guest's successful belt placement did not consume the connector")
                host.command(f"/give {guest_name} create:wrench")
                guest.call("select", "create:wrench")
                guest.call("interact", 6, 104, -11)
                multiplayer.until("guest removed the pulley with a Wrench", lambda:
                                 "part=middle" in host.call("block", 6, 104, -11)["state"])
                multiplayer.until("guest received the pulley shaft", lambda:
                                 multiplayer.count(guest, "create:shaft") == 1)
    print("LAN guest placed the belt, cleared the pulley with a Wrench, and recovered its shaft.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--reopen", action="store_true")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--backpressure", action="store_true")
    args = parser.parse_args()
    action = run_backpressure if args.backpressure else run_lan if args.lan else run_reopen if args.reopen else run
    action(args)


if __name__ == "__main__":
    main()
