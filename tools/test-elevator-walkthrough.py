#!/usr/bin/env python3
"""Walk across a moving elevator and exit through a paired landing door."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

spec = spec_from_file_location("elevator_service", Path(__file__).with_name("test-elevator-service.py"))
service = module_from_spec(spec)
spec.loader.exec_module(service)
trip = service.trip
elevator = trip.elevator
multiplayer = trip.multiplayer
SCENARIO = "elevator-walkthrough"
CABIN = (4, 2, 1)
LANDING = ((4, 11, 0), (5, 11, 0))
CONTACT_APPROACH = (2.5, 10.0, 4.0)
# Java can resolve the rider a small distance above the exact collision face.
GROUND_TOLERANCE = 0.001


def place_doors(host):
    host.commands((
        "/gamerule random_tick_speed 0",
        "/gamerule fall_damage false",
        f"/place template create:{elevator.TEMPLATE.with_suffix('')} {elevator.as_argument((0, 0, 0))}",
        f"/setblock {elevator.as_argument(trip.GUEST_SEAT)} minecraft:air",
        f"/fill {elevator.as_argument((4, 10, -6))} {elevator.as_argument((5, 10, 0))} minecraft:smooth_stone",
        f"/setblock {elevator.as_argument((2, 9, 4))} minecraft:smooth_stone",
        *(
            f"/setblock {elevator.as_argument(service.above(p, dy))} "
            f"create:train_door[facing=north,half={half},hinge={hinge},open=false,powered=false]"
            for p, hinge in zip((CABIN, *LANDING), ("left", "left", "right"), strict=True)
            for dy, half in enumerate(("lower", "upper"))
        ),
        f"/summon minecraft:marker {elevator.as_argument((4.5, 1, 1.5))}"
        " {CreateSuperGlue:1b,From:[-0.5d,0d,-0.5d],To:[0.5d,3d,0.5d]}",
    ))


def step(host, ticks, live=False):
    target = host.clock() + ticks
    if not live:
        host.command(f"/tick step {ticks}")
    multiplayer.until(f"world to reach tick {target}", lambda: host.clock() >= target)


def snapshot(client):
    state = client.call("state")
    player = state["player"]
    position = trip.relative(player["position"])
    grounded = state["gamemode"] == "survival" and player["health"] > 0 and player["on_ground"]
    return position, grounded and not player["flying"]


def walk(client, frames):
    client.call("script", script=f"key w down\nwait {frames}\nkey w up\nwait 3\n")


def look(client, at):
    client.call("look-at", *elevator.at(at))


def deck(host):
    response = host.command(f"/data get entity {elevator.CART} Pos")
    return trip.relative(trip.pos_reply(response))[1] + 1


def stable_at(client, at):
    pose, grounded = snapshot(client)
    return grounded and all(abs(actual - wanted) <= GROUND_TOLERANCE
                            for actual, wanted in zip(pose, at, strict=True))


def position(host, client, name, at):
    x, y, z = at
    # A client arriving from outside the cabin's tracking radius needs the
    # collision snapshot before the artificial test spawn reaches the deck.
    host.command(f"/tp {name} {elevator.as_argument((x, y + 0.5, z))}")
    try:
        multiplayer.until(f"{name} to stand at {at}", lambda: stable_at(client, at), 4)
    except RuntimeError as error:
        raise RuntimeError(f"{error}. Last pose: {snapshot(client)}.") from error


def ensure_paired_state(expected, *clients):
    coords = [service.above(p, dy) for p in LANDING for dy in (0, 1)]
    for client in clients:
        observed = []

        def all_halves_match():
            observed[:] = [service.open_state(client, pos) for pos in coords]
            return observed == [expected] * len(coords)

        try:
            multiplayer.until(f"both halves of each landing leaf to be {expected}", all_halves_match, 4)
        except RuntimeError as error:
            raise RuntimeError(f"{error}. Landing states: {observed}.") from error


def ride_and_walk(host, riders, live):
    starting_x = (4.25, 5.10)
    for (client, name), x in zip(riders, starting_x, strict=True):
        trip.place_standing_rider(host, client, name, (x, 2.0, 2.5))
        look(client, (12.0, 3.6, 2.5))
    if live:
        host.command("/tick unfreeze")
    host.command(f"/setblock {elevator.as_argument(elevator.LEVER)} minecraft:lever[face=floor,facing=west,powered=true]")
    step(host, 15, live)
    before = deck(host)
    with ThreadPoolExecutor(max_workers=3) as pool:
        walk_briefly = [pool.submit(walk, client, 3) for client, _ in riders]
        step(host, 7, live)
        for walk_input in walk_briefly:
            walk_input.result()
    floor = deck(host)
    if floor <= before:
        raise RuntimeError(f"Elevator did not rise while the players walked: {before} to {floor}.")
    for (client, name), x in zip(riders, starting_x, strict=True):
        def walked_on_deck():
            pose, grounded = snapshot(client)
            # A live client can coast for a tick before the next cabin pose.
            # Sample again while the cabin is still traveling.
            on_deck = before <= pose[1] < 11 and pose[1] <= deck(host) + 0.3
            if not live:
                on_deck = abs(pose[1] - floor) <= GROUND_TOLERANCE
            return grounded and x + 0.25 < pose[0] < 6.2 and on_deck

        try:
            multiplayer.until(f"{name} to walk east on the moving deck", walked_on_deck, 2)
        except RuntimeError as error:
            raise RuntimeError(f"{error}. Last pose: {snapshot(client)}.") from error
    print(f"Both riders walked east as the deck rose from {before:.6f} to {floor:.6f}.", flush=True)
    step(host, 60, live)
    if deck(host) != 11:
        raise RuntimeError("The elevator did not settle at the upper floor.")


def walkthrough(host, riders, opening):
    at = (4.5, 11.0, 2.5)
    for index, (client, name) in enumerate(riders):
        other, other_name = riders[1 - index]
        position(host, other, other_name, (5.5 - index, 11.0, -5.5))
        position(host, client, name, at)
        look(client, (4.5, 12.6, -3.5))
        walk(client, 16 if opening else 10)
        pose, grounded = snapshot(client)
        if abs(pose[1] - at[1]) > GROUND_TOLERANCE or not grounded:
            raise RuntimeError(f"{name} fell off the deck while walking at the upper door: {pose}.")
        moved_correctly = pose[2] < -0.35 if opening else 2.2 < pose[2] < 2.45
        if not moved_correctly:
            raise RuntimeError(f"{name} did not {'exit' if opening else 'stop at'} the door: {pose}.")
        server = trip.relative(trip.pos_reply(host.command(f"/data get entity {name} Pos")))
        crossed_landing = server[2] < -0.35
        if crossed_landing != opening or abs(server[1] - at[1]) > GROUND_TOLERANCE:
            raise RuntimeError(f"The server saw {name} at {server} after the door crossing.")
        print(f"{name} crossed the landing: {crossed_landing}.", flush=True)


def run(args, scratch):
    scenario = f"{SCENARIO}-live" if args.live else SCENARIO
    with fixture_world(args, scenario, elevator.TEMPLATE, render=True, pack=args.pack) as host:
        network = host.call("lan", "open", "0", "commands", "force")
        host_name = host.call("lan", "status")["host"]
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(args, scratch, address, trip.GUEST, render=True, scenario=scenario, pack=args.pack) as guest:
            multiplayer.until("the LAN guest to join", lambda: any(
                connection["name"] == trip.GUEST and connection["placed"]
                for connection in host.call("lan", "status")["guests"]
            ))
            host.command("/tick unfreeze")
            for client in (host, guest):
                client.call("script", script="key space down\nwait 1\nkey space up\nwait 1\nkey space down\nwait 1\nkey space up\n")
                multiplayer.until("creative flight for test setup", lambda: client.call("state")["player"]["flying"])
            host.command("/tick freeze")
            place_doors(host)
            step(host, 15)
            trip.aim_block(host, host, elevator.PRIMARY, (7.5, 11.0, 4.5))
            host.call("interact", *elevator.at(elevator.PRIMARY))
            step(host, 4)
            service.floor_editor(host, guest, trip.UPPER, CONTACT_APPROACH, -5)
            step(host, 3)
            riders = ((host, host_name), (guest, trip.GUEST))
            ride_and_walk(host, riders, args.live)
            ensure_paired_state("false", host, guest)
            walkthrough(host, riders, opening=False)
            service.floor_editor(host, guest, trip.UPPER, CONTACT_APPROACH, 4)
            step(host, 10, args.live)
            ensure_paired_state("true", host, guest)
            walkthrough(host, riders, opening=True)
            service.floor_editor(host, guest, trip.UPPER, CONTACT_APPROACH, -4)
            step(host, 10, args.live)
            ensure_paired_state("false", host, guest)
            print("Both survival players walked across the moving deck, stopped at closed doors, "
                  "and exited when both leaves opened and then closed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--live", action="store_true", help="Ride and cross the doors at normal tick rate")
    for path in ("ctl", "client", "resources"):
        parser.add_argument(path, type=lambda value: Path(value).resolve(strict=True))
    with TemporaryDirectory(prefix="hc-walk-") as scratch:
        run(parser.parse_args(), Path(scratch))
