#!/usr/bin/env python3
"""Board a moving chain with a wrench and dismount through normal game input."""

import argparse
import csv
from contextlib import ExitStack
import importlib
from math import dist
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


player = importlib.import_module("test-chain-conveyor-player")
chain = player.chain
multiplayer = player.multiplayer
A = (8, 102, -10)
MOTOR = (8, 101, -10)
WRENCH = "create:wrench"
BOARD = "CREATE_CHAIN_RIDE_BOARD "
BOARDED_PATH = re.compile(r"CREATE_CHAIN_RIDE_BOARD \[([^]]+)\],Some\(\[([^]]+)\]\)\,")
EVENT = re.compile(r"CREATE_CHAIN_RIDE_(KEEPALIVE|STOP|EXPIRED) (\d+),([0-9a-f]+)")
POSE = re.compile(r"CREATE_CHAIN_SKYHOOK_POSE (\d+),(true|false),([^,]+),([^,]+),([^\r\n]+)")
ROSTER = re.compile(r"CREATE_CHAIN_SKYHOOK_ROSTER \d+,(\d+)")
STOP = re.compile(r"CREATE_CHAIN_RIDE_TICK \d+,None,None,[^,]+,\d+,true,")


def observe_pose(observer, start, offhand):
    log = observer.socket.parent / "ctl.log"
    poses = POSE.findall(log.read_text()[start:])
    if not poses:
        return False
    # The fixture uses Minecraft's default right main hand.
    with (ROOT / "fixtures/chain-conveyor-skyhook-java.csv").open() as stream:
        part = 3 if offhand else 2
        reference = next(row for row in csv.DictReader(stream)
                         if row["left"] == str(offhand).lower() and int(row["part"]) == part)
    for _, left, _, pitch, roll in poses:
        assert left == str(offhand).lower(), poses
        assert abs(float(pitch) - float(reference["x_rot"])) < 1e-6, poses
        assert abs(float(roll) - float(reference["z_rot"])) < 1e-6, poses
    return True


def run(args):
    mode = "LAN" if args.lan else "Solo"
    env = {"CREATE_CHAIN_RIDE": "1"}
    if args.sustain or args.expire:
        env["CREATE_CHAIN_RIDE_PACKETS"] = "1"
    entry = "rising-reversal" if args.reverse else "loop" if args.loop else "span"
    delta = (6, 2, 3) if args.reverse else (28, 0, 0) if args.sustain else (7, 0, 0)
    protocol = "-sustain" if args.sustain else "-expire" if args.expire else ""
    other = tuple(x + d for x, d in zip(A, delta, strict=True))
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, f"ChainRide-{entry}-{mode}{protocol}", pack=args.pack, env=env))
        if args.sustain:
            world.command("/fill 6 98 -12 38 107 -5 minecraft:air")
        chain.setup(world, A, other, MOTOR, (17, 100, -10), delta, True)
        if args.sustain:
            # Keep this protocol test on a moving span for the whole
            # interval. Other cases exercise the wheel transfers.
            world.command("/fill 7 99 -12 38 99 -5 minecraft:stone")
            world.command(f"/data merge block {chain.coords(MOTOR)} {{ScrollValue:64}}")
        if args.reverse:
            world.command("/fill 10 100 -6 13 100 -4 minecraft:stone")
            feet, look = (11.5, 101.0, -4.5), (11.1793, 103.375, -7.3587)
        elif args.loop:
            world.command("/fill 5 99 -8 7 99 -6 minecraft:stone")
            feet, look = (6.0, 100.0, -7.0), (8.5, 102.25, -9.5)
        else:
            world.command("/fill 10 99 -9 14 99 -5 minecraft:stone")
            feet, look = (12.0, 100.0, -6.25), (12.0, 102.375, -8.783)
        actor, observer, name = world, None, "@s"
        if args.lan:
            port = world.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-chain-ride-")))
            name = "ChainRideGuest"
            actor = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, scenario=f"chain-ride-{entry}-{args.dismount}{protocol}", pack=args.pack, env=env,
            ))
            multiplayer.until("guest to enter the chain world", lambda: any(
                guest["name"] == name and guest["placed"] for guest in world.call("lan", "status")["guests"]
            ))
            if args.observe:
                observer_name = "ChainObserver"
                observer = stack.enter_context(multiplayer.joined_client(
                    args, scratch, f"127.0.0.1:{port}", observer_name, render=True,
                    scenario=f"chain-ride-observer-{entry}-{args.offhand}{protocol}", pack=args.pack,
                    env={"CREATE_CHAIN_RIDE_POSE": "1", "HORIZON_NO_AUDIO": "1"},
                ))
                multiplayer.until("observer to enter the chain world", lambda: any(
                    guest["name"] == observer_name and guest["placed"]
                    for guest in world.call("lan", "status")["guests"]
                ))
                world.command(f"/gamemode spectator {observer_name}")
                world.command(f"/tp {observer_name} 11.5 102.0 -4.0")
                multiplayer.until("observer's camera to reach the chain", lambda:
                                  observer.call("state")["player"]["position"] == [11.5, 102.0, -4.0])
                observer.call("look-at", 12.0, 101.0, -8.8)
        world.command(f"/gamemode survival {name}")
        if args.offhand:
            world.command(f"/item replace entity {name} weapon.offhand with {WRENCH}")
            multiplayer.until("wrench to arrive in the offhand", lambda:
                              multiplayer.count(actor, WRENCH) == 1)
        else:
            player.equip(world, actor, name, WRENCH, WRENCH)
        world.command(f"/tp {name} {chain.coords(feet)}")
        multiplayer.until("player to reach the chain", lambda:
                          actor.call("state")["player"]["position"] == list(feet))
        actor.call("look-at", *look)
        world.command("/tick unfreeze")
        log = actor.socket.parent / "ctl.log"
        if observer:
            observer_log = observer.socket.parent / "ctl.log"
            offset = observer_log.stat().st_size
        actor.call("use-item")
        multiplayer.until(f"right click to board the {entry}", lambda: BOARD in log.read_text())
        boarding = next(line for line in log.read_text().splitlines() if line.startswith(BOARD))
        if args.loop:
            assert ",None," in boarding, boarding
        else:
            path = BOARDED_PATH.search(boarding)
            assert path is not None, boarding
            origin, edge = (tuple(map(int, field.split(","))) for field in path.groups())
            assert edge in (delta, tuple(-offset for offset in delta)), boarding
        if args.reverse:
            destination = [x + offset for x, offset in zip(origin, edge, strict=True)]
            back = [-offset for offset in edge]
            world.command(f"/data merge block {chain.coords(MOTOR)} {{ScrollValue:-128}}")
            reversal = f"Some({destination}),Some({back}),"
            multiplayer.until("rider to transfer across the reversing span", lambda: reversal in log.read_text())
        multiplayer.until("the moving chain to pull the rider", lambda:
                          dist(actor.call("state")["player"]["position"], feet) > 0.6)
        if args.lan:
            def authority_moved():
                reply = world.command(f"/data get entity {name} Pos")
                values = re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?d", reply)
                return len(values) == 3 and dist([float(value[:-1]) for value in values], feet) > 0.6
            multiplayer.until("the host to see the rider move", authority_moved)
        host_log = world.socket.parent / "ctl.log"
        if observer:
            multiplayer.until("observer to render the hanging pose", lambda:
                              observe_pose(observer, offset, args.offhand))
            assert "1" in ROSTER.findall(observer_log.read_text()[offset:])
        if args.expire:
            multiplayer.until("the host to register the rider", lambda:
                              "CREATE_CHAIN_RIDE_KEEPALIVE " in host_log.read_text())
            actor.call("quit")
            multiplayer.until("the host to expire the disconnected rider", lambda:
                              "CREATE_CHAIN_RIDE_EXPIRED " in host_log.read_text())
            events = [(kind, int(tick), uuid) for kind, tick, uuid in EVENT.findall(host_log.read_text())]
            last = [tick for kind, tick, uuid in events if kind == "KEEPALIVE"][-1]
            expired = [tick for kind, tick, uuid in events if kind == "EXPIRED"]
            assert all(kind != "STOP" for kind, _, _ in events), events
            with (ROOT / "fixtures/chain-conveyor-riding-authority-java.csv").open() as stream:
                java = [row for row in csv.DictReader(stream) if row["scenario"] == "expiry"]
            final_refresh = max(int(row["tick"]) for row in java if row["action"] == "keepalive")
            expiry = next(int(row["tick"]) for row in java if int(row["tick"]) > final_refresh and row["ttl"] == "0")
            assert expired == [last + expiry - final_refresh], events
            if observer:
                multiplayer.until("observer to clear the expired rider from its roster", lambda:
                                  ROSTER.findall(observer_log.read_text()[offset:])[-1:] == ["0"])
                print("LAN observer: expired rider cleared")
            print(f"{mode}: disconnected rider expired after {expiry - final_refresh} Java ticks")
            return
        if args.sustain:
            actor.call("wait", 110)
            kept = host_log.read_text().count("CREATE_CHAIN_RIDE_KEEPALIVE ")
            assert kept >= 8, f"host accepted {kept} keepalives during the sustained ride"
            assert STOP.search(log.read_text()) is None, "rider came off before the sustained ride ended"
            assert authority_moved()

        if args.dismount == "release":
            world.command(f"/clear {name} {WRENCH}")
        else:
            actor.call("key", "shift", "down")
        multiplayer.until("rider to dismount", lambda: STOP.search(log.read_text()))
        if args.sustain:
            multiplayer.until("the host to accept the ride stop", lambda:
                              "CREATE_CHAIN_RIDE_STOP " in host_log.read_text())
            events = EVENT.findall(host_log.read_text())
            assert [kind for kind, _, _ in events].count("STOP") == 1, events
            assert not any(kind == "EXPIRED" for kind, _, _ in events), events
            print(f"{mode}: {kept} validated keepalives and one explicit stop after 110 ticks")
        if observer:
            multiplayer.until("observer to receive the cleared roster", lambda:
                              ROSTER.findall(observer_log.read_text()[offset:])[-1:] == ["0"])
            observer.call("wait", 4)
            after = observer_log.stat().st_size
            observer.call("wait", 4)
            assert not POSE.findall(observer_log.read_text()[after:]), "observer kept the hanging pose"
            print(f"LAN observer: {'left' if args.offhand else 'right'} arm pose appeared and cleared")
        if args.dismount == "sneak":
            actor.call("key", "shift", "up")
            assert multiplayer.count(actor, WRENCH) == 1
        assert log.read_text().count(BOARD) == 1
        print(f"{mode}: real {entry} boarding, player motion, and {args.dismount} dismount")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve())
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--observe", action="store_true")
    parser.add_argument("--offhand", action="store_true")
    entry = parser.add_mutually_exclusive_group()
    entry.add_argument("--loop", action="store_true")
    entry.add_argument("--reverse", action="store_true")
    parser.add_argument("--dismount", choices=("sneak", "release"), default="sneak")
    protocol = parser.add_mutually_exclusive_group()
    protocol.add_argument("--sustain", action="store_true")
    protocol.add_argument("--expire", action="store_true")
    args = parser.parse_args()
    if (args.sustain or args.expire or args.observe) and not args.lan:
        parser.error("ride protocol checks require --lan")
    if args.sustain and (args.loop or args.reverse):
        parser.error("--sustain uses the long straight span")
    run(args)


if __name__ == "__main__":
    main()
