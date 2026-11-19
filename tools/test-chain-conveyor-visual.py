#!/usr/bin/env python3
"""Compare offscreen conveyor and Frogport model submission with the Java renderer inputs."""

import argparse
from contextlib import ExitStack, contextmanager
import csv
import importlib
from math import dist
from pathlib import Path
import re
from struct import pack, unpack
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


chain = importlib.import_module("test-chain-conveyor-packages")
multiplayer = importlib.import_module("test-multiplayer")
A = (8, 102, -10)
WHEEL = re.compile(r"CREATE_CHAIN_WHEEL \[([^]]+)\],([^\r\n]+)")
SPAN = re.compile(r"CREATE_CHAIN_SPAN \[([^]]+)\],\[([^]]+)\],([^\r\n]+)")
SPAN_LIGHT = re.compile(r"CREATE_CHAIN_SPAN_LIGHT \[([^]]+)\],([^\r\n]+)")
MIP = re.compile(r"CREATE_CHAIN_MIP \[([^]]+)\],([^\r\n]+)")
FROG = re.compile(r"CREATE_FROGPORT_MODEL \[([^]]+)\],([^\r\n]+)")


def rows(file):
    with (ROOT / "fixtures" / file).open() as stream:
        return list(csv.DictReader(stream))


def vector(raw):
    return tuple(map(int, raw.split(",")))


def f32(value):
    return unpack("f", pack("f", value))[0]


def close(actual, expected, message, epsilon=3e-5):
    assert abs(float(actual) - float(expected)) < epsilon, (message, actual, expected)


def verify(args):
    delta = chain.WHEELS[args.scenario]
    b = tuple(x + d for x, d in zip(A, delta))
    port = (b[0] + 2, b[1] - 2, b[2])
    motor = (8, 101, -10)
    rising = args.scenario == "rising_reversal"
    reference = {r["wheel"]: r for r in rows("chain-conveyor-visual-span-java.csv")
                 if r["scenario"] == args.scenario}
    receive = rows("chain-conveyor-visual-port-java.csv")[0]

    with fixture_world(args, "ChainVisual-" + args.scenario, render=True, pack=args.pack,
                       env={"CREATE_CHAIN_RENDER": "1", "HORIZON_NO_AUDIO": "1"}) as world:
        chain.setup(world, A, b, motor, port, delta, rising)
        world.command("/gamemode spectator")
        world.command("/tp @s 12.0 106.0 -3.0")
        world.call("look-at", 12.0, 102.0, -9.0)
        world.call("key", "f1", "tap")
        if not rising:
            chain.merge(world, port, '{AddressFilter:"Lab-In",Target:{RelativePos:[I;-2,2,0],ChainPosition:150f}}')
            chain.merge(world, b, "{PackagePorts:[{Port:[I;2,-2,0],ChainPosition:150f}]}")
            start = world.clock()
            world.step_to(start + 1)
            world.step_to(start + 2)
            cargo = chain.stack("Lab-In", "paper", 3)
            chain.merge(world, A, f"{{Packages:[{{Item:{cargo},Position:40f}}]}}")
            start = world.clock()
            for step in range(1, 33):
                world.step_to(start + step)
                if 21 <= step <= 31:
                    world.call("wait", 2)
                if args.capture and step == 22:
                    world.call("screenshot", args.capture)
        else:
            world.call("wait", 5)
        if args.capture and rising:
            world.call("screenshot", args.capture)
        log = (world.socket.parent / "ctl.log").read_text()

    wheels, meshes, frames = set(), set(), []
    for position, data in WHEEL.findall(log):
        pos = vector(position)
        if pos not in (A, b):
            continue
        time, partial, rpm, angle, wheel, shaft = map(float, data.split(","))
        if rpm != 128:
            continue
        phase = 22.5 if (pos[0] + pos[2]) % 2 == 0 else 0
        render_time = f32(time + partial)
        value = f32(f32(f32(f32(render_time * rpm) * 3) / 10) + phase) % 360
        close(angle, value, data, epsilon=2.5e-4)
        assert wheel > 0 and shaft > 0, data
        wheels.add(pos)
    for position, edge, data in SPAN.findall(log):
        pos = vector(position)
        wheel = "A" if pos == A else "B"
        wanted = reference[wheel]
        time, partial, yaw, pitch, phase, length, quads = map(float, data.split(","))
        for actual, key in ((yaw, "yaw"), (pitch, "pitch"), (length, "length")):
            close(actual, wanted[key], data)
        assert quads > 0 and quads % 4 == 0, data
        assert vector(edge) == (delta if wheel == "A" else tuple(-n for n in delta)), edge
        if phase != -0.5:
            expected_phase = f32(f32(time + partial) / f32(360 / 128)) % 1 - 0.5
            close(phase, expected_phase, data)
            meshes.add(wheel)
    assert wheels == {A, b} and meshes == {"A", "B"}, (wheels, meshes)

    if not rising:
        for position, data in FROG.findall(log):
            if vector(position) != port:
                continue
            time, _, yaw, progress, head, pitch, tongue, scale, vertices = map(float, data.split(","))
            if progress == 0 and abs(yaw) < 0.01:
                continue
            close(yaw, receive["yaw"], data)
            close(pitch, receive["pitch"], data)
            assert vertices > 0, data
            if 0 < progress < 1:
                base_head = float(receive["base_head"])
                base_length = float(receive["base_length"])
                close(head, base_head * (1 - min(1, max(0, ((1.5 * progress)**2 - 0.5) * 2))), data)
                close(tongue, base_length * max(0, 1 - 1.25 * progress)**5, data)
                close(scale, max(0.5, 1 - progress * 1.25), data)
                frames.append((time, progress, head, tongue))
        assert len({frame[0] for frame in frames}) >= 6, frames
        assert max(frame[3] for frame in frames) > 0.2, frames
    print(f"{args.scenario}: original wheel and shaft models, both moving spans, {len(frames)} sampled Frogport poses")


@contextmanager
def visual_pair(args, label):
    delta = chain.WHEELS[args.scenario]
    b = tuple(x + d for x, d in zip(A, delta, strict=True))
    mode = "LAN" if args.lan else "Solo"
    scenario = f"{label}-{args.scenario}-{mode}"
    env = {"CREATE_CHAIN_RENDER": "1", "HORIZON_NO_AUDIO": "1"}
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(
            args, scenario, render=not args.lan, pack=args.pack, env=env,
        ))
        chain.setup(world, A, b, (8, 101, -10), (17, 100, -10), delta, True)
        actor, name = world, "@s"
        if args.lan:
            port = world.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-chain-visual-")))
            name = "ChainVisualGuest"
            actor = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, render=True,
                scenario=scenario, pack=args.pack, env=env,
            ))
            multiplayer.until("guest to enter the visual fixture", lambda: any(
                guest["name"] == name and guest["placed"] for guest in world.call("lan", "status")["guests"]
            ))
        world.command(f"/gamemode spectator {name}")
        yield world, actor, name, mode, b


def verify_span_lights(trace, distance, b):
    reference_distance = 47 if distance < 48 else 48
    java = [row for row in rows("chain-conveyor-span-light-java.csv")
            if int(row["distance"]) == reference_distance]
    endpoints = []
    for fraction in (0, 1):
        matching = [row for row in java if int(row["fraction"]) == fraction]
        assert len(matching) == 8, matching
        levels = {(int(row["block"]) << 12) | (int(row["sky"]) << 4) for row in matching}
        assert len(levels) == 1, matching
        endpoints.append(levels.pop())

    seen = set()
    for position, data in SPAN_LIGHT.findall(trace):
        wheel = vector(position)
        far, start, end, first, last, middle, error, valid = data.split(",")
        expected = endpoints if wheel == A else endpoints[::-1]
        assert [int(start), int(end)] == expected, (distance, wheel, data, expected)
        assert valid == "true" and far == str(distance >= 48).lower(), (distance, wheel, data)
        assert [int(first), int(last)] == [8, 8], (distance, wheel, data)
        assert (int(middle) > 0) == (far == "false"), (distance, wheel, data)
        close(error, 0.0, (distance, wheel), epsilon=2e-6)
        seen.add(wheel)
    assert seen == {A, b}, (distance, seen)


def verify_mip(args):
    expected = rows("chain-conveyor-span-mip-java.csv")
    label = "ChainSpanLight" if args.span_light else "ChainSpanMip"
    with visual_pair(args, label) as (world, actor, name, mode, b):
        if args.span_light:
            # Keep sky light out of both wheel cells, then give the wheels
            # different block light within the original comparison range.
            x, y, z = A
            world.command(f"/fill {x-18} {y+4} {z-18} {b[0]+18} {y+4} {z+18} minecraft:stone")
            world.command(f"/setblock {x+5} {y-1} {z+1} minecraft:light[level=15]")
        midpoint = tuple((a + z + 1) / 2 for a, z in zip(A, b, strict=True))
        log = actor.socket.parent / "ctl.log"
        for row in expected:
            distance = int(row["distance"])
            feet = (midpoint[0], midpoint[1] - 1.62, midpoint[2] + distance)
            world.command(f"/tp {name} {chain.coords(feet)}")
            multiplayer.until(f"{mode} camera at {distance} blocks", lambda:
                              actor.call("state")["player"]["position"] == list(feet))
            actor.call("look-at", *midpoint)
            actor.call("wait", 6)
            offset = log.stat().st_size
            actor.call("wait", 4)
            trace = log.read_text()[offset:]
            spans = {}
            for wheel, _, data in SPAN.findall(trace):
                spans[vector(wheel)] = int(data.split(",")[-1])
            assert set(spans) == {A, b}, (distance, spans)
            mip = {vector(wheel): data.split(",") for wheel, data in MIP.findall(trace)}
            for wheel, quads in spans.items():
                if row["far"] == "true":
                    assert quads == int(row["quads"]), (distance, wheel, quads, row)
                else:
                    assert quads > int(row["quads"]), (distance, wheel, quads, row)
                actual_distance, far, *geometry = mip[wheel]
                close(actual_distance, distance, (wheel, row))
                assert far == row["far"], (wheel, row, far)
                # The near texture repeats across atlas strips. The distant
                # mesh uses the original single static texture rectangle.
                keys = ("width", "min_u", "max_u", "min_v", "max_v")
                for value, key in zip(geometry, keys, strict=True):
                    if row["far"] == "true" or key not in ("min_v", "max_v"):
                        close(value, row[key], (wheel, key, row))
            if args.span_light:
                verify_span_lights(trace, distance, b)
    distances = ", ".join(row["distance"] for row in expected)
    print(f"{mode} {args.scenario}: both spans match Java mesh and UVs at {distances} blocks")
    if args.span_light:
        print(f"{mode}: Java endpoint light at all {len(expected)} distances, verified gradient on tiled vertices")


def verify_visibility(args):
    expected = rows("chain-conveyor-span-visibility-java.csv")
    with visual_pair(args, "ChainSpanVisibility") as (world, actor, name, mode, b):
        port = (A[0], A[1], A[2] + 2)
        world.command(f"/setblock {chain.coords(port)} create:package_frogport")
        log = actor.socket.parent / "ctl.log"
        center = tuple(axis + 0.5 for axis in A)
        other_center = tuple(axis + 0.5 for axis in b)
        midpoint = tuple((x + y + 1) / 2 for x, y in zip(A, b, strict=True))
        # The camera smooths its f32 eye height and settles one f32 step
        # below 1.62. Use the rendered value to land exactly on the cutoff.
        camera_eye_height = 1.619999885559082
        for row in expected:
            distance = int(row["distance"])
            eye = (center[0], center[1] + distance, center[2])
            feet = (eye[0], eye[1] - camera_eye_height, eye[2])
            world.command(f"/tp {name} {chain.coords(feet)}")
            multiplayer.until(f"{mode} camera at {distance} blocks", lambda:
                              actor.call("state")["player"]["position"] == list(feet))
            # Java submits these block entities even facing away. Keep the
            # camera above the same chunk so view-distance and chunk loading
            # do not mask which renderer made the visibility decision.
            actor.call("look-at", center[0], center[1] if distance != 96 else feet[1] + 8, center[2])
            actor.call("wait", 32 if distance == 63 else 6)
            offset = log.stat().st_size
            actor.call("wait", 4)
            trace = log.read_text()[offset:]
            visible = {vector(position) for position, _ in WHEEL.findall(trace)}
            wanted = {A} if row["visible"] == "true" else set()
            if dist(eye, other_center) < int(row["range"]):
                wanted.add(b)
            assert visible == wanted, (distance, visible, wanted)
            spans = {vector(position) for position, _, _ in SPAN.findall(trace)}
            assert spans == wanted, (distance, spans, wanted)
            for wheel, data in MIP.findall(trace):
                if vector(wheel) == A:
                    close(data.split(",")[0], dist(eye, midpoint), (distance, wheel), epsilon=1e-8)
            ports = {vector(position) for position, _ in FROG.findall(trace)}
            assert ports == ({port} if distance == 63 else set()), (distance, ports)
    print(f"{mode} {args.scenario}: Java visibility at all {len(expected)} distances, including the offscreen sample")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--scenario", choices=chain.WHEELS, default="straight")
    parser.add_argument("--capture", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--mip", action="store_true")
    modes.add_argument("--visibility", action="store_true")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--span-light", action="store_true")
    args = parser.parse_args()
    if args.span_light and (not args.mip or args.scenario != "straight"):
        parser.error("--span-light requires --mip and the straight layout")
    if args.mip:
        verify_mip(args)
    elif args.visibility:
        verify_visibility(args)
    else:
        if args.lan:
            parser.error("the LAN option requires --mip or --visibility")
        verify(args)


if __name__ == "__main__":
    main()
