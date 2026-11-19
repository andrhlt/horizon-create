#!/usr/bin/env python3
"""Check standing survival players on both legs of a Horizon LAN elevator trip."""

import argparse
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

spec = importlib.util.spec_from_file_location(
    "elevator_passengers", Path(__file__).with_name("test-multiplayer-elevator.py")
)
trip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trip)
elevator = trip.elevator
multiplayer = trip.multiplayer
SCENARIO = "elevator-standing"


def near(actual, expected):
    return all(abs(a - b) <= 1e-8 for a, b in zip(actual, expected, strict=True))


def feet(client):
    return trip.relative(client.call("state")["player"]["position"])


def standing(client, expected):
    state = client.call("state")
    player = state["player"]
    return (
        state["gamemode"] == "survival"
        and player["health"] > 0
        and not player["flying"]
        and player["on_ground"]
        and near(trip.relative(player["position"]), expected)
    )


def cabin_floor(host):
    at = trip.pos_reply(host.command(f"/data get entity {elevator.CART} Pos"))
    return trip.relative(at)[1] + 1.0 + trip.JAVA_FOOT_CLEARANCE


def move(host, riders, lever, landing):
    host.command(f"/setblock {elevator.as_argument(lever)} "
                 "minecraft:lever[face=floor,facing=west,powered=true]")
    start = host.clock()
    for tick in range(1, 68):
        host.step_to(start + tick)
        floor = cabin_floor(host)
        for name, client, x, z in riders:
            expected = (x, floor, z)

            def at_floor():
                if not standing(client, expected):
                    return False
                server = trip.pos_reply(host.command(f"/data get entity {name} Pos"))
                return near(trip.relative(server), expected)

            try:
                multiplayer.until(f"{name} to reach {expected} at travel tick {tick}", at_floor, 3)
            except RuntimeError as error:
                raise RuntimeError(f"{error}. Last client position was {feet(client)}.") from error
    if abs(floor - (landing + trip.JAVA_FOOT_CLEARANCE)) > 1e-8 or any(
            trip.ride(host, name) for name, *_ in riders):
        raise RuntimeError(f"Expected two unmounted players at floor {landing}, cabin at {floor}.")



def move_live(host, riders, lever, landing, delay=False):
    host.command(f"/setblock {elevator.as_argument(lever)} "
                 "minecraft:lever[face=floor,facing=west,powered=true]")
    if delay:
        multiplayer.until("ascending cabin to be between floors", lambda: 3 < cabin_floor(host) < 5, 5)
        host.call("server-hold", "on")
        try:
            host.call("wait", 2)
        finally:
            host.call("server-hold", "off")
    multiplayer.until(f"cabin to arrive at {landing}",
                      lambda: abs(cabin_floor(host) - landing - trip.JAVA_FOOT_CLEARANCE) <= 1e-8, 15)
    for name, client, x, z in riders:
        expected = (x, landing + trip.JAVA_FOOT_CLEARANCE, z)
        def arrived():
            server = trip.pos_reply(host.command(f"/data get entity {name} Pos"))
            return standing(client, expected) and near(trip.relative(server), expected)
        multiplayer.until(f"{name} to stand at {expected}", arrived, 3)


def run(args, scratch):
    with fixture_world(args, args.scenario, elevator.TEMPLATE, render=True, pack=args.pack) as host:
        network = host.call("lan", "open", "0", "commands", "force")
        host_name = host.call("lan", "status")["host"]
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(args, scratch, address, trip.GUEST, render=True,
                                       scenario=args.scenario, pack=args.pack) as guest:
            multiplayer.until("the guest to join", lambda: any(
                connection["name"] == trip.GUEST and connection["placed"]
                for connection in host.call("lan", "status")["guests"]
            ))
            host.command("/tick unfreeze")
            for client in (host, guest):
                client.call("script", script=(
                    "key space down\nwait 1\nkey space up\nwait 1\n"
                    "key space down\nwait 1\nkey space up\n"
                ))
                multiplayer.until("creative flight for fixture setup",
                                  lambda: client.call("state")["player"]["flying"], 3)
            host.command("/tick freeze")
            host.commands((
                "/gamerule random_tick_speed 0",
                "/gamerule fall_damage false",
                "/scoreboard objectives add elevator_ride dummy",
                f"/place template create:{elevator.TEMPLATE.with_suffix('')} {elevator.as_argument((0, 0, 0))}",
                f"/setblock {elevator.as_argument(trip.GUEST_SEAT)} minecraft:air",
            ))
            start = host.clock()
            for tick in range(1, 16):
                host.step_to(start + tick)
            trip.aim_block(host, host, elevator.PRIMARY, (7.5, 11.0, 4.5))
            host.call("interact", *elevator.at(elevator.PRIMARY))
            start = host.clock()
            for tick in range(1, 6):
                host.step_to(start + tick)

            riders = ((host_name, host, 5.5, 2.5), (trip.GUEST, guest, 4.5, 2.5))
            for name, client, x, z in riders:
                deck = (x, 2.0, z)
                trip.place_standing_rider(host, client, name, deck)
                supported = (x, 2.0 + trip.JAVA_FOOT_CLEARANCE, z)
                multiplayer.until(f"{name} to stand on the lower deck",
                                  lambda: standing(client, supported), 4)

            if args.live:
                host.command("/tick unfreeze")
                move_live(host, riders, elevator.LEVER, 11.0, delay=args.delay)
                move_live(host, riders, elevator.BOTTOM_LEVER, 2.0)
            else:
                move(host, riders, elevator.LEVER, 11.0)
                move(host, riders, elevator.BOTTOM_LEVER, 2.0)
            for name, client, x, z in riders:
                client.call("script", script="key space down\nwait 1\nkey space up\n")
                multiplayer.until(f"{name} to jump independently", lambda: feet(client)[1] > 2.05, 3)
                multiplayer.until(f"{name} to land on the lower deck",
                                  lambda: standing(client, (x, 2.0 + trip.JAVA_FOOT_CLEARANCE, z)), 3)
            if args.live:
                print("Both Horizon clients reached both landings at normal tick rate, then jumped independently.")
            else:
                print("Host and LAN guest stood unmounted on the cabin for all 134 travel ticks, "
                      "then jumped and landed independently.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--live", action="store_true", help="Run both legs at the normal tick rate")
    parser.add_argument("--delay", action="store_true", help="Hold cabin packets briefly during ascent")
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    args = parser.parse_args()
    if args.delay and not args.live:
        parser.error("--delay requires --live")
    args.scenario = SCENARIO
    if args.live:
        args.scenario += "-delayed" if args.delay else "-live"
        os.environ["HORIZON_CREATE_STANDING_TRACE"] = "1"
    with TemporaryDirectory(prefix="elevator-standing-") as scratch:
        run(args, Path(scratch))
    if args.live:
        check = trip.load("check-elevator-standing-motion")
        check.verify(ROOT / f".local/horizon-{args.scenario}.log")
        check.verify(ROOT / f".local/{args.scenario}-{trip.GUEST.lower()}.log")
