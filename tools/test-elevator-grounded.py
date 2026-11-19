#!/usr/bin/env python3
"""Board and leave the upper elevator landing with two survival players."""

import argparse
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

spec = importlib.util.spec_from_file_location(
    "elevator_passengers", Path(__file__).with_name("test-multiplayer-elevator.py")
)
trip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trip)
elevator = trip.elevator
multiplayer = trip.multiplayer
SCENARIO = "elevator-grounded"


def step(host, ticks):
    start = host.clock()
    for offset in range(1, ticks + 1):
        host.step_to(start + offset)


def grounded(client, seat):
    state = client.call("state")
    player = state["player"]
    wanted = (seat[0] + 0.5, 11.0 + trip.JAVA_FOOT_CLEARANCE, seat[2] + 0.5)
    position = trip.relative(player["position"])
    if (state["gamemode"] == "survival" and player["on_ground"] and not player["flying"]
            and all(abs(actual - expected) < 1e-7
                    for actual, expected in zip(position, wanted, strict=True))):
        return position
    return None


def run(args, scratch):
    with fixture_world(args, SCENARIO, elevator.TEMPLATE, render=True, pack=args.pack) as host:
        network = host.call("lan", "open", "0", "commands", "force")
        host_name = host.call("lan", "status")["host"]
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(args, scratch, address, trip.GUEST, render=True,
                                       scenario=SCENARIO, pack=args.pack) as guest:
            multiplayer.until("the guest to join", lambda: any(
                connection["name"] == trip.GUEST and connection["placed"]
                for connection in host.call("lan", "status")["guests"]
            ))
            host.commands((
                "/gamerule random_tick_speed 0",
                "/scoreboard objectives add elevator_ride dummy",
                f"/place template create:{elevator.TEMPLATE.with_suffix('')} {elevator.as_argument((0, 0, 0))}",
                f"/setblock {elevator.as_argument(trip.HOST_SEAT)} create:white_seat",
            ))
            step(host, 15)
            trip.aim_block(host, host, elevator.PRIMARY, (7.5, 11.0, 4.5))
            host.call("interact", *elevator.at(elevator.PRIMARY))
            step(host, 5)

            riders = ((host_name, host, trip.HOST_SEAT), (trip.GUEST, guest, trip.GUEST_SEAT))
            for name, client, seat in riders:
                # A fixed approach beside the lower cabin gives the players
                # solid footing while they reach for their seats in survival.
                approach = elevator.as_argument((seat[0], seat[1] - 1, seat[2] + 2))
                host.call("command", f"/setblock {approach} minecraft:smooth_stone")
                host.call("command", f"/gamemode survival {name}")
                multiplayer.until(f"{name} to enter survival",
                                  lambda: client.call("state")["gamemode"] == "survival", 4)
                trip.board(host, client, seat)
                multiplayer.until(f"{name} to board the cabin", lambda: trip.ride(host, name), 4)

            host.command(f"/setblock {elevator.as_argument(elevator.LEVER)} "
                         "minecraft:lever[face=floor,facing=west,powered=true]")
            step(host, 67)
            if elevator.sample(host)[-2] != "10.000000000":
                raise RuntimeError("The cabin did not settle at the upper floor.")

            for name, client, seat in riders:
                client.call("key", "shift", "down")
                try:
                    multiplayer.until(f"{name} to dismount", lambda: not trip.ride(host, name), 3)
                finally:
                    client.call("key", "shift", "up")
                multiplayer.until(f"{name} to land on the cabin",
                                  lambda: grounded(client, seat), 4)

            step(host, 8)
            for name, client, seat in riders:
                position = grounded(client, seat)
                if position is None:
                    raise RuntimeError(f"{name} could not stay on the cabin floor.")
                print(f"{name} dismounted and stayed grounded at {position} in survival.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    with TemporaryDirectory(prefix="hc-elevator-grounded-") as scratch:
        run(parser.parse_args(), Path(scratch))
