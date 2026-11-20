#!/usr/bin/env python3
"""Check standing host/guest collision and active bearing save/reopen."""

import argparse
from importlib import import_module
import math
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

multiplayer = import_module("test-multiplayer")
BEARING = (8, 104, 10)
MOTOR = (8, 103, 10)
ANCHOR = (8.5, 105.5, 10.5)
GUEST = "BearingGuest"


def number(reply, name):
    match = re.search(rf"\b{re.escape(name)}: (-?\d+(?:\.\d+)?)(?:[fd])?", reply)
    return float(match[1]) if match else 0.0


def coordinates(pos):
    return " ".join(map(str, pos))


def setup(host):
    host.commands((
        f"/setblock {coordinates(BEARING)} create:mechanical_bearing[facing=up]",
        f"/fill 7 105 9 9 105 11 minecraft:smooth_stone",
        '/setblock 8 105 10 minecraft:chest{Items:[{Slot:0b,count:7,id:"minecraft:copper_ingot"}]}',
        "/summon minecraft:marker 7 105 9 {CreateSuperGlue:1b,From:[0d,0d,0d],To:[3d,1d,3d]}",
        f"/setblock {coordinates(MOTOR)} create:creative_motor[facing=up]{{ScrollValue:0}}",
        "/fill 5 100 5 11 100 13 minecraft:smooth_stone",
    ))


def bearing_data(host):
    return host.command(f"/data get block {coordinates(BEARING)}")


def player_state(client):
    state = client.call("state")
    player = state["player"]
    return state["gamemode"], player["on_ground"], tuple(player["position"])


def close(a, b, tolerance=0.2):
    return all(abs(x - y) <= tolerance for x, y in zip(a, b, strict=True))


def expected_after_turn(start, angle):
    dx, dz = start[0] - ANCHOR[0], start[2] - ANCHOR[2]
    radians = math.radians(angle)
    return (
        ANCHOR[0] + dx * math.cos(radians) + dz * math.sin(radians),
        start[1],
        ANCHOR[2] - dx * math.sin(radians) + dz * math.cos(radians),
    )


def active_reopen(args):
    with fixture_world(args, "Bearing-player-reopen", render=True, pack=args.pack) as host:
        setup(host)
        host.call("lan", "open", "0", "commands", "force")
        name = host.call("lan", "status")["host"]
        host.command(f"/gamemode survival {name}")
        host.command(f"/tp {name} 9.5 106 10.5")
        host.command(f"/data merge block {coordinates(MOTOR)} {{ScrollValue:20}}")
        start = host.clock()
        for tick in range(1, 3):
            host.step_to(start + tick)
        before = bearing_data(host)
        angle = number(before, "Angle")
        if "MovedBlocks" not in before or angle == 0:
            raise RuntimeError(f"Bearing did not save an active glued cargo payload: {before}")
        host.call("save")
        host.restart()
        reopened = bearing_data(host)
        if "MovedBlocks" not in reopened or number(reopened, "Angle") <= 0 or "count: 7" not in reopened:
            raise RuntimeError(f"Active bearing payload changed across reopen: {before} -> {reopened}")
        reopened_angle = number(reopened, "Angle")
        host.step_to(host.clock() + 1)
        resumed = bearing_data(host)
        if number(resumed, "Angle") == reopened_angle or "MovedBlocks" not in resumed:
            raise RuntimeError(f"Active bearing did not resume after reopen: {resumed}")
        host.command(f"/data merge block {coordinates(MOTOR)} {{ScrollValue:0}}")
        host.step_to(host.clock() + 1)
        restored = host.command("/data get block 8 105 10 Items")
        if "count: 7" not in restored or "minecraft:copper_ingot" not in restored:
            raise RuntimeError(f"Bearing disassembly did not restore its chest cargo: {restored}")
    print("Active glued bearing cargo and motion survived save/reopen and disassembled with seven copper ingots.")


def multiplayer_collision(args, scratch):
    with fixture_world(args, "Bearing-player-lan", render=True, pack=args.pack) as host:
        network = host.call("lan", "open", "0", "commands", "force")
        host_name = host.call("lan", "status")["host"]
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(args, scratch, address, GUEST, render=True,
                                       scenario="bearing-player-lan", pack=args.pack) as guest:
            multiplayer.until("bearing guest to join", lambda: any(
                item["name"] == GUEST and item["placed"]
                for item in host.call("lan", "status")["guests"]
            ))
            setup(host)
            riders = ((host_name, host, (9.5, 106.0, 10.5)),
                      (GUEST, guest, (8.5, 106.0, 9.5)))
            for name, client, initial in riders:
                host.command(f"/gamemode survival {name}")
                host.command(f"/tp {name} {' '.join(map(str, initial))}")
                multiplayer.until(f"{name} to stand on the payload", lambda: (
                    player_state(client)[0] == "survival" and player_state(client)[1]
                ), 5)
            host.command(f"/data merge block {coordinates(MOTOR)} {{ScrollValue:60}}")
            start = host.clock()
            for tick in range(1, 4):
                host.step_to(start + tick)
                data = bearing_data(host)
                if "MovedBlocks" in data:
                    break
            else:
                raise RuntimeError(f"Bearing did not assemble its glued payload after motor power: {data}")
            start_angle = number(data, "Angle")
            for name, _, initial in riders:
                start_position = expected_after_turn(initial, start_angle)
                host.command(
                    f"/tp {name} {start_position[0]} {start_position[1] + 0.0001} {start_position[2]}"
                )
            start = host.clock()
            for tick in range(1, 7):
                host.step_to(start + tick)
                data = bearing_data(host)
                angle = number(data, "Angle")
                if "MovedBlocks" not in data:
                    raise RuntimeError(f"Bearing payload disappeared during tick {tick}: {data}")
                for name, client, initial in riders:
                    def converged():
                        mode, on_ground, position = player_state(client)
                        expected = expected_after_turn(initial, angle)
                        return mode == "survival" and on_ground and close(position, expected)
                    try:
                        multiplayer.until(f"{name} to ride bearing turn {angle:g}", converged, 4)
                    except RuntimeError as error:
                        states = {rider: player_state(viewer) for rider, viewer, _ in riders}
                        raise RuntimeError(
                            f"{error}; rider states={states}; bearing={data}"
                        ) from error
            host.command(f"/data merge block {coordinates(MOTOR)} {{ScrollValue:0}}")
            host.step_to(host.clock() + 1)
            restored = host.command("/data get block 8 105 10 Items")
            if "count: 7" not in restored or "minecraft:copper_ingot" not in restored:
                raise RuntimeError(f"Bearing disassembly lost the chest contents: {restored}")
    print("The host and LAN guest stayed grounded and followed the rotating glued payload; chest cargo restored.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    active_reopen(args)
    with TemporaryDirectory(prefix="bearing-player-") as scratch:
        multiplayer_collision(args, Path(scratch))


if __name__ == "__main__":
    main()
