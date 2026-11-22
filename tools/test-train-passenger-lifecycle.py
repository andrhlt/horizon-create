#!/usr/bin/env python3
"""Check train seat custody, driver independence and idle/active passenger saves."""
import argparse
import re
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

seats = import_module("test-multiplayer-train-seats")
reopen = import_module("test-manual-train-reopen")
train, mp, elevator = seats.train, seats.multiplayer, seats.elevator
GUEST = seats.GUEST


def step(world, ticks):
    for _ in range(ticks):
        world.step_to(world.clock() + 1)


def driver(world):
    return world.command(f"/data get entity {train.ENTITY} CreateTrain.Driver")


def board(world, actor, name, offset):
    # This rig is still at its assembly station for all boarding operations.
    seats.mount(world, actor, name, offset)


def check_rider(world, actor, name):
    assert elevator.ride(world, name), (name, "lost seat")
    server = elevator.pos_reply(world.command(f"/data get entity {name} Pos"))
    mp.until(f"{name} rider pose convergence", lambda: all(
        abs(a - b) < 0.02 for a, b in zip(
            actor.call("state")["player"]["position"], server, strict=True)))
    return server


def check_carriers(world, expected):
    world.command("/scoreboard players set #carriers elevator_ride 0")
    world.call("command", "/execute as @e[tag=create_train_seat_vehicle] run scoreboard players add #carriers elevator_ride 1")
    result = world.command("/scoreboard players get #carriers elevator_ride")
    match = re.search(r"\bhas (\d+)\b", result)
    assert match and int(match[1]) == expected, result


def run(args):
    with TemporaryDirectory(prefix="hc-passengers-", dir="/private/tmp") as scratch, fixture_world(
        args, "TrainPassengerLifecycle", train.STRUCTURE, render=True, pack=args.pack,
        env={"HORIZON_NO_AUDIO": "1"},
    ) as host:
        def add_seats(world):
            for offset, color in ((3, "red"), (4, "blue")):
                world.command(f"/setblock {train.X+offset} {train.Y+3} {train.Z} create:{color}_seat")

        train.setup(host, before_glue=add_seats, take_controls=False)
        host.command("/scoreboard objectives add elevator_ride dummy")
        host_name = "@s"
        host.command("/attribute @s minecraft:gravity base set 0")
        board(host, host, host_name, 3)
        idle = check_rider(host, host, host_name)
        if args.case == "idle":
            host.call("save")
            host.restart()
            assert check_rider(host, host, host_name) == idle, "Idle rider moved across reopen"
            assert reopen.snapshot(host)[0] == 0
            check_carriers(host, 1)
            print("Idle seated host retained mount and pose across save/reopen.")
            return

        port = host.call("lan", "open", "0", "commands", "force")["port"]
        address = f"127.0.0.1:{port}"
        with mp.joined_client(args, Path(scratch), address, GUEST, render=True,
                              scenario="train-passenger-lifecycle", pack=args.pack) as guest:
            mp.until("passenger join", lambda: any(
                p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]))
            host.command(f"/gamemode survival {GUEST}")
            host.command(f"/attribute {GUEST} minecraft:gravity base set 0")
            board(host, guest, GUEST, 4)
            check_rider(host, guest, GUEST)
            # A passenger's movement input must not acquire or drive controls.
            before = reopen.snapshot(host)
            guest.call("key", "w", "down")
            step(host, 6)
            guest.call("key", "w", "up")
            assert reopen.snapshot(host) == before, "Passenger drove without controls"
            host.call("look-at", train.X+1.5, train.Y+3.45, train.Z+0.5)
            host.call("mouse", "right", "click")
            host.call("wait", 4)
            owner = driver(host)
            assert "[I;" in owner, owner
            reopen.drive(host, "w", 12)
            assert reopen.snapshot(host)[0] > 0, "Seated driver did not move train"
            check_rider(host, host, host_name)
            check_rider(host, guest, GUEST)
            # Dismounting the passenger must leave the driver's custody intact.
            guest.call("key", "shift", "down")
            step(host, 1)
            guest.call("key", "shift", "up")
            assert not elevator.ride(host, GUEST), "Guest could not dismount"
            assert driver(host) == owner, "Passenger dismount released driver"
            print("Passenger movement and dismount left driver custody intact.")
            # Remount through the moving hitbox, rather than a stale block location.
            seat = elevator.pos_reply(host.command(
                "/data get entity @e[type=minecraft:interaction,tag=create_train_seat,sort=furthest,limit=1] Pos"))
            elevator.teleport(host, guest, (seat[0], seat[1], seat[2]+2.15))
            guest.call("look-at", seat[0], seat[1]+0.2, seat[2])
            guest.call("mouse", "right", "click")
            guest.call("wait", 4)
            check_rider(host, guest, GUEST)
            host.call("save")
        if args.case == "interactions":
            print("Host/guest boarding, passenger input, dismount and moving remount passed.")
            return
        # Guest disconnect must leave a usable train, and reopening must keep its
        # geometry and host passenger while permitting normal rejoin recovery.
        moving = reopen.snapshot(host)
        host.restart()
        check_rider(host, host, host_name)
        assert reopen.snapshot(host)[1] > moving[1], "Active train did not resume"
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        with mp.joined_client(args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                              scenario="train-passenger-rejoin", pack=args.pack) as guest:
            mp.until("passenger rejoin", lambda: any(
                p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]))
            check_rider(host, guest, GUEST)
            check_carriers(host, 2)
            host.command(f"/ride {GUEST} dismount")
            assert not elevator.ride(host, GUEST)
            check_rider(host, host, host_name)
        print("Active host passenger save, guest rejoin and independent driver custody passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--case", choices=("idle", "active", "interactions"), default="idle")
    run(parser.parse_args())

