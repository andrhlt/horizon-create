#!/usr/bin/env python3
"""Check Rope Pulley obstruction, save/reopen, and standing host/guest movement."""

import argparse
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

mp_spec = importlib.util.spec_from_file_location("multiplayer", Path(__file__).with_name("test-multiplayer.py"))
multiplayer = importlib.util.module_from_spec(mp_spec)
mp_spec.loader.exec_module(multiplayer)
spec = importlib.util.spec_from_file_location("rope_payload", Path(__file__).with_name("test-rope-payload.py"))
rope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rope)

PULLEY = (rope.X, rope.Y, rope.Z)
MOTOR = (rope.X + 1, rope.Y, rope.Z)
GUEST = "RopeGuest"


def coords(pos):
    return " ".join(map(str, pos))


def pulley_data(control):
    return control.command(f"/data get block {coords(PULLEY)}")


def assert_restored(control):
    data = pulley_data(control)
    offset = rope.scalar(data, "Offset")
    y = rope.Y - int(offset + 0.5) - 1
    casing, planks, chest, marker = control.commands((
        f"/execute if block {rope.X} {y} {rope.Z} create:andesite_casing",
        f"/execute if block {rope.X + 1} {y} {rope.Z} minecraft:oak_planks",
        f"/data get block {rope.X + 2} {y} {rope.Z} Items",
        "/execute if entity @e[type=minecraft:marker,tag=create_rope_load]",
    ))
    if "Test passed" not in casing or "Test passed" not in planks or "Test failed" not in marker:
        raise RuntimeError(f"Pulley did not restore the glued platform: {casing}, {planks}, {marker}")
    if "count: 7" not in chest or "minecraft:copper_ingot" not in chest:
        raise RuntimeError(f"Restored chest lost its seven copper ingots: {chest}")


def blocked(args):
    with fixture_world(args, "Rope-payload-blocked", rope.STRUCTURE, pack=args.pack) as control:
        rope.setup(control)
        control.command(f"/setblock {rope.X} {rope.Y - 2} {rope.Z} minecraft:bedrock")
        control.command(f"/data merge block {coords(MOTOR)} {{ScrollValue:-128}}")
        start = control.clock()
        for tick in range(1, 5):
            control.step_to(start + tick)
        casing = control.command(f"/execute if block {rope.X} {rope.Y - 1} {rope.Z} create:andesite_casing")
        planks = control.command(f"/execute if block {rope.X + 1} {rope.Y - 1} {rope.Z} minecraft:oak_planks")
        chest = control.command(f"/data get block {rope.X + 2} {rope.Y - 1} {rope.Z} Items")
        marker = control.command("/execute if entity @e[type=minecraft:marker,tag=create_rope_load]")
        data = pulley_data(control)
        if rope.scalar(data, "Speed") <= 0:
            raise RuntimeError(f"Blocked fixture failed to drive the pulley downward: {data}")
        if "Test passed" not in casing or "Test passed" not in planks or "Test failed" not in marker:
            raise RuntimeError(f"Blocked assembly moved or removed its source blocks: {casing}, {planks}, {marker}; {data}")
        if "count: 7" not in chest or "minecraft:copper_ingot" not in chest:
            raise RuntimeError(f"Blocked assembly changed cargo: {chest}")
        if rope.scalar(data, "Offset") != 0 or rope.scalar(data, "Running") != 0:
            raise RuntimeError(f"Blocked assembly advanced pulley state: {data}")
    print("Bedrock blocked pulley assembly without moving the glued blocks or losing cargo.")


def lifecycle(args):
    with fixture_world(args, "Rope-payload-reopen", rope.STRUCTURE, pack=args.pack) as control:
        rope.setup(control)
        control.call("save")
        control.restart()
        assert_restored(control)
        idle = pulley_data(control)
        if rope.scalar(idle, "Running") != 0:
            raise RuntimeError(f"Idle pulley resumed unexpectedly after reopen: {idle}")

        control.command(f"/data merge block {coords(MOTOR)} {{ScrollValue:-128}}")
        start = control.clock()
        for tick in range(1, 9):
            control.step_to(start + tick)
            data = pulley_data(control)
            marker = control.command("/execute if entity @e[type=minecraft:marker,tag=create_rope_load]")
            if "Test passed" in marker and rope.scalar(data, "Offset") > 0:
                break
        else:
            raise RuntimeError(f"Pulley did not start a moving payload: {data}")

        before = pulley_data(control)
        marker_before = control.command("/data get entity @e[type=minecraft:marker,tag=create_rope_load,limit=1]")
        if "minecraft:copper_ingot" not in marker_before or "count: 7" not in marker_before:
            raise RuntimeError(f"Moving payload did not own all chest contents before save: {marker_before}")
        control.call("save")
        control.restart()
        after = pulley_data(control)
        marker_after = control.command("/data get entity @e[type=minecraft:marker,tag=create_rope_load,limit=1]")
        if rope.scalar(after, "Running") != 1 or rope.scalar(after, "Offset") < rope.scalar(before, "Offset"):
            raise RuntimeError(f"Pulley stopped or regressed across active save/reopen: {before} -> {after}")
        if "minecraft:copper_ingot" not in marker_after or "count: 7" not in marker_after:
            raise RuntimeError(f"Active payload lost its chest across save/reopen: {marker_after}")
        resumed_offset = rope.scalar(after, "Offset")
        for _ in range(3):
            control.step_to(control.clock() + 1)
        resumed = pulley_data(control)
        if rope.scalar(resumed, "Running") != 1 or rope.scalar(resumed, "Offset") <= resumed_offset:
            raise RuntimeError(f"Active pulley did not resume motion after reopen: {after} -> {resumed}")

        control.command(f"/data merge block {coords(MOTOR)} {{ScrollValue:0}}")
        for _ in range(1, 5):
            control.step_to(control.clock() + 1)
            if rope.scalar(pulley_data(control), "Running") == 0:
                break
        assert_restored(control)
    print("Idle and moving glued payloads retained their blocks and cargo across save/reopen; active motion resumed.")


def limit(args):
    with fixture_world(args, "Rope-payload-limit", rope.STRUCTURE, pack=args.pack) as control:
        rope.setup(control)
        control.command(f"/data merge block {coords(MOTOR)} {{ScrollValue:128}}")
        start = control.clock()
        control.step_to(start + 1)
        data = pulley_data(control)
        casing, planks, chest, marker = control.commands((
            f"/execute if block {rope.X} {rope.Y - 1} {rope.Z} create:andesite_casing",
            f"/execute if block {rope.X + 1} {rope.Y - 1} {rope.Z} minecraft:oak_planks",
            f"/data get block {rope.X + 2} {rope.Y - 1} {rope.Z} Items",
            "/execute if entity @e[type=minecraft:marker,tag=create_rope_load]",
        ))
        if "Test passed" not in casing or "Test passed" not in planks or "Test failed" not in marker:
            raise RuntimeError(f"Raising with zero rope moved the glued payload: {casing}, {planks}, {marker}; {data}")
        if "count: 7" not in chest or "minecraft:copper_ingot" not in chest:
            raise RuntimeError(f"Raising at the zero-rope limit lost cargo: {chest}")
        if rope.scalar(data, "Offset") != 0 or rope.scalar(data, "Running") != 0:
            raise RuntimeError(f"Raising with zero rope should remain stopped at the top limit: {data}")
    print("Rope Pulley stayed stopped at the zero-rope upper limit without moving its cargo.")


def player_state(client):
    state = client.call("state")
    return state["gamemode"], state["player"]["on_ground"], tuple(state["player"]["position"])


def close(a, b, tolerance=0.25):
    return all(abs(x - y) <= tolerance for x, y in zip(a, b, strict=True))


def multiplayer_riders(args, scratch):
    with fixture_world(args, "Rope-payload-lan", rope.STRUCTURE, render=True, pack=args.pack) as host:
        network = host.call("lan", "open", "0", "commands", "force")
        host_name = host.call("lan", "status")["host"]
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(args, scratch, address, GUEST, render=True,
                                       scenario="rope-payload-lan", pack=args.pack) as guest:
            multiplayer.until("Rope Pulley guest to join", lambda: any(
                item["name"] == GUEST and item["placed"]
                for item in host.call("lan", "status")["guests"]
            ))
            rope.setup(host)
            host.command(f"/data merge block {coords(MOTOR)} {{ScrollValue:-128}}")
            start = host.clock()
            for tick in range(1, 5):
                host.step_to(start + tick)
                data = pulley_data(host)
                if "Test passed" in host.command("/execute if entity @e[type=minecraft:marker,tag=create_rope_load]"):
                    break
            else:
                raise RuntimeError(f"Rope Pulley did not capture payload in LAN: {data}")
            for _ in range(2):
                host.step_to(host.clock() + 1)
            data = pulley_data(host)
            foot_y = rope.Y - rope.scalar(data, "Offset") + 0.0001
            initial = ((host_name, host, (9.5, foot_y, rope.Z + 0.5)),
                       (GUEST, guest, (8.5, foot_y, rope.Z + 0.5)))
            for name, _, position in initial:
                host.call("command", f"/gamemode survival {name}")
                host.command(f"/tp {name} {' '.join(map(str, position))}")
            for name, client, position in initial:
                multiplayer.until(f"{name} to stand on the moving load", lambda: (
                    player_state(client)[0] == "survival"
                    and player_state(client)[1]
                    and close(player_state(client)[2], position)
                ), 5)

            for _ in range(1, 7):
                host.step_to(host.clock() + 1)
                data = pulley_data(host)
                offset = rope.scalar(data, "Offset")
                expected_y = rope.Y - offset
                for name, client, start_position in initial:
                    def following():
                        mode, grounded, position = player_state(client)
                        return mode == "survival" and grounded and close(
                            position, (start_position[0], expected_y, start_position[2])
                        )
                    try:
                        multiplayer.until(f"{name} to follow the pulley payload", following, 4)
                    except RuntimeError as error:
                        states = {rider: player_state(viewer) for rider, viewer, _ in initial}
                        payload = host.command("/data get entity @e[type=minecraft:marker,tag=create_rope_load,limit=1]")
                        raise RuntimeError(
                            f"{error}; riders={states}; pulley={data}; payload collision captured="
                            f"{'CreateElevatorCollision' in payload}; payload={payload}"
                        ) from error
            host.command(f"/data merge block {coords(MOTOR)} {{ScrollValue:0}}")
            for _ in range(1, 5):
                host.step_to(host.clock() + 1)
                if rope.scalar(pulley_data(host), "Running") == 0:
                    break
            assert_restored(host)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--blocked", action="store_true")
    parser.add_argument("--lifecycle", action="store_true")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--limit", action="store_true")
    args = parser.parse_args()
    if args.blocked:
        blocked(args)
    elif args.lifecycle:
        lifecycle(args)
    elif args.limit:
        limit(args)
    elif args.lan:
        with TemporaryDirectory(prefix="rope-payload-lan-") as scratch:
            multiplayer_riders(args, Path(scratch))
    else:
        parser.error("choose --blocked, --lifecycle, --limit, or --lan")


if __name__ == "__main__":
    main()
