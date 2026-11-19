#!/usr/bin/env python3
"""Replay the Java two-player elevator trip with a Horizon host and LAN guest."""

import argparse
import csv
import importlib.util
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


multiplayer = load("test-multiplayer")
elevator = load("test-elevator")
SCENARIO = "multiplayer-elevator"
GUEST = "ElevatorGuest"
SEAT = "create_elevator_seat"
CONTROLS = "create_elevator_controls"
LOWER = (2, 1, 2)
UPPER = (2, 10, 2)
GUEST_SEAT = (4, 2, 2)
HOST_SEAT = (5, 2, 2)
JAVA_FOOT_CLEARANCE = 0.000100100
RETURN = re.compile(r"\bTargetFloor: (-?\d+)")
STRING = re.compile(r'\b(ShortName|LongName): ("(?:[^"\\]|\\.)*")')


def prop(client, local, key):
    state = client.call("block", *elevator.at(local))["state"]
    return str(f"{key}=true" in state).lower()


def pos_reply(reply):
    found = elevator.POSITION.search(reply)
    if not found:
        raise RuntimeError(f"Missing position in {reply}")
    return tuple(map(float, found.groups()))


def teleport(host, client, pos):
    if client is host:
        client.call("tp", *pos)
    else:
        host.command(f"/tp {GUEST} {' '.join(map(str, pos))}")
    multiplayer.until("client to receive its setup position",
                      lambda: all(abs(a - b) < 1e-4 for a, b in zip(
                          client.call("state")["player"]["position"], pos, strict=True)), 3)



def place_standing_rider(host, client, name, position):
    x, y, z = position
    destination = " ".join(map(str, elevator.at((x, y + 0.01, z))))
    teleport = f"/tp {name} {destination}"
    host.command(teleport)
    host.command(f"/gamemode survival {name}")
    multiplayer.until(f"{name} to enter survival", lambda: client.call("state")["gamemode"] == "survival")
    host.command(teleport)
    client.call("wait", 3)

def aim_block(host, client, local, approach):
    teleport(host, client, elevator.at(approach))
    client.call("wait", 3)
    client.call("look-at-block", *elevator.at(local))


def find_hitbox(host, tag, *, local_x=None):
    clauses = [f"tag={tag}", "type=minecraft:interaction", "limit=1"]
    if local_x is not None:
        world_x = elevator.ORIGIN[0] + local_x
        clauses.extend((f"x={world_x}", "dx=0", "y=96", "dy=16", "z=-12", "dz=6"))
    return pos_reply(host.command(f"/data get entity @e[{','.join(clauses)}] Pos"))


def board(host, client, seat):
    x, y, z = find_hitbox(host, SEAT, local_x=seat[0])
    teleport(host, client, (x, y, z + 1.8))
    client.call("wait", 3)
    client.call("look-at", x, y + 0.2, z)
    client.call("use-item")
    client.call("wait", 2)


def edit(host, client, local, approach, names):
    aim_block(host, client, local, approach)
    client.call("interact", *elevator.at(local))
    client.call("wait", 3)
    for index, name in enumerate(names):
        if index:
            client.call("key", "tab", "tap")
        client.call("type", name)
    client.call("key", "enter", "tap")
    client.call("wait", 2)


def floor_names(host, at):
    reply = host.command(f"/data get block {elevator.as_argument(at)}")
    fields = {key: json.loads(value) for key, value in STRING.findall(reply)}
    return [fields.get("ShortName", ""), fields.get("LongName", "")]


def relative(pos):
    return tuple(value - origin for value, origin in zip(pos, elevator.ORIGIN, strict=True))


def ride(host, name):
    host.command(f"/scoreboard players set {name} elevator_ride 0")
    host.call("command", f"/execute store success score {name} elevator_ride as {name} on vehicle if entity @s")
    score = host.command(f"/scoreboard players get {name} elevator_ride")
    found = re.search(r"\bhas ([01])\b", score)
    if not found:
        raise RuntimeError(f"Could not query mount: {score}")
    return found[1] == "1"


def wait_for_selected_floor(host, floor):
    command = f"/data get block {elevator.as_argument(elevator.PRIMARY)}"
    pending = re.compile(rf"\bSelectedFloor: {elevator.at(floor)[1]}\b")
    multiplayer.until("the elevator to receive the selected destination",
                      lambda: pending.search(host.command(command)), 3)


def sample(host, name, tick, rider_positions):
    primary, cabin = host.commands((
        f"/data get block {elevator.as_argument(elevator.PRIMARY)}",
        f"/data get entity {elevator.CART} Pos",
    ))
    match = RETURN.search(primary)
    target = str(int(match[1]) - elevator.ORIGIN[1]) if match else ""
    position = elevator.POSITION.search(cabin)
    row = {
        "tick": str(tick),
        "bottom_lit": prop(host, elevator.BOTTOM, "lit"),
        "top_lit": prop(host, elevator.TOP, "lit"),
        "cabin_y": f"{float(position[2]) - elevator.ORIGIN[1]:.9f}" if position else "",
        "target_y": target,
    }
    for floor, pos in (("lower", LOWER), ("upper", UPPER)):
        row[f"{floor}_short"], row[f"{floor}_long"] = floor_names(host, pos)
    for tag, player in (("host", name), ("guest", GUEST)):
        row[f"{tag}_mounted"] = str(ride(host, player)).lower() if rider_positions else ""
        measured = relative(pos_reply(host.command(f"/data get entity {player} Pos"))) if rider_positions else ("", "", "")
        for axis, value in zip("xyz", measured, strict=True):
            row[f"{tag}_{axis}"] = f"{value:.9f}" if rider_positions else value
    return row


def observe_client(client, role, row):
    for name, local in (("bottom_lit", elevator.BOTTOM), ("top_lit", elevator.TOP)):
        multiplayer.until(f"{role} to see {name}={row[name]} on tick {row['tick']}",
                          lambda: prop(client, local, "lit") == row[name], 3)
    if row[f"{role}_y"]:
        wanted = tuple(float(row[f"{role}_{axis}"]) for axis in "xyz")
        actual = None

        def same_position():
            nonlocal actual
            actual = relative(client.call("state")["player"]["position"])
            return tuple(f"{coordinate:.9f}" for coordinate in actual) == tuple(
                row[f"{role}_{axis}"] for axis in "xyz"
            )

        try:
            multiplayer.until(f"{role} to reach {wanted} on tick {row['tick']}", same_position, 3)
        except RuntimeError as error:
            raise RuntimeError(f"{error}. Last {role} position: {actual}.") from error


def check_trip(args, reference, scratch):
    with fixture_world(args, SCENARIO, elevator.TEMPLATE, render=True, pack=args.pack) as host:
        network = host.call("lan", "open", "0", "commands", "force")
        host_name = host.call("lan", "status")["host"]
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(args, scratch, address, GUEST, render=True, scenario=SCENARIO, pack=args.pack) as guest:
            multiplayer.until("the independent guest is placed",
                              lambda: any(p["name"] == GUEST and p["placed"]
                                          for p in host.call("lan", "status")["guests"]))
            host.command("/tick unfreeze")
            for client in (host, guest):
                client.call("script", script="key space down\nwait 1\nkey space up\nwait 1\nkey space down\nwait 1\nkey space up\n")
                multiplayer.until("creative flight before placing the fixture",
                                  lambda: client.call("state")["player"]["flying"], 3)
            host.command("/tick freeze")
            while host.clock() % 20 != 2:
                host.step_to(host.clock() + 1)
            host.commands((
                "/gamerule random_tick_speed 0",
                "/scoreboard objectives add elevator_ride dummy",
                f"/place template create:{elevator.TEMPLATE.with_suffix('')} {elevator.as_argument((0, 0, 0))}",
                f"/setblock {elevator.as_argument(HOST_SEAT)} create:white_seat",
            ))
            start = host.clock()
            actual = []
            for expected in reference:
                tick = int(expected["tick"])
                if tick:
                    host.step_to(start + tick)
                row = sample(host, host_name, tick, tick > 20)
                actual.append(row)
                if tick >= 16 and not args.record_only:
                    observe_client(host, "host", row)
                    observe_client(guest, "guest", row)
                if tick == 15:
                    aim_block(host, host, elevator.PRIMARY, (7.5, 11.0, 4.5))
                    host.call("interact", *elevator.at(elevator.PRIMARY))
                elif tick == 18:
                    edit(host, host, LOWER, (0.5, 1.0, 2.5), ("G", "Ground"))
                    edit(host, guest, UPPER, (2.5, 10.0, 4.0), ("U", "Upper"))
                elif tick == 19:
                    if (floor_names(host, LOWER), floor_names(host, UPPER)) != (["G", "Ground"], ["U", "Upper"]):
                        raise RuntimeError(f"The floor editors did not persist both names: {row}")
                elif tick == 20:
                    board(host, host, HOST_SEAT)
                    board(host, guest, GUEST_SEAT)
                    for name in (host_name, GUEST):
                        if not ride(host, name):
                            raise RuntimeError(f"{name}'s click did not board the cabin.")
                elif tick == 25:
                    x, y, z = find_hitbox(host, CONTROLS)
                    guest.call("look-at", x, y + 0.5, z)
                    guest.call("script", script="scroll-at 10 10 1\nuse-item\n")
                    wait_for_selected_floor(host, UPPER)
                elif tick == 90:
                    # Java injects a sneak packet into embedded server players.
                    # Leave through the server without adding creative flight input.
                    host.commands((
                        f"/ride {host_name} dismount",
                        f"/ride {GUEST} dismount",
                    ))
                if host.clock() != start + tick:
                    raise RuntimeError(f"World advanced while applying inputs on tick {tick}.")
            return actual


def run(args):
    reference = ROOT / "fixtures/elevator-passengers-java.csv"
    with reference.open() as stream:
        reader = csv.DictReader(stream)
        expected = list(reader)
        headings = reader.fieldnames
    with TemporaryDirectory(prefix="hc-elevator-mp-") as scratch:
        actual = check_trip(args, expected, Path(scratch))
    output = ROOT / ".local/multiplayer-elevator-horizon.csv"
    with output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, headings, lineterminator="\n")
        writer.writeheader()
        writer.writerows(actual)
    if args.record_only:
        print(f"Recorded {len(actual)} ticks at {output}.")
        return
    errors = [(a["tick"], {key: (a[key], b[key]) for key in a if a[key] != b[key]})
              for a, b in zip(expected, actual, strict=True) if a != b]
    if errors:
        raise SystemExit(f"{len(errors)} multiplayer elevator differences. First six: {errors[:6]}. See {output}")
    print(f"Host and LAN guest matched Java across all {len(actual)} elevator ticks. See {output}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--record-only", action="store_true")
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
