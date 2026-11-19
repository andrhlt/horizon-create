#!/usr/bin/env python3
"""Replay Java’s suspended box model and spring motion in the offscreen client."""

import argparse
from contextlib import ExitStack
import csv
import importlib
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


outbound = importlib.import_module("test-chain-conveyor-outbound")
chain = outbound.chain
multiplayer = importlib.import_module("test-multiplayer")
A, PORT = outbound.A, outbound.PORT
MOTOR = (8, 101, -10)
ID = 902
BOX = re.compile(r"CREATE_CHAIN_BOX \[([^]]+)\],([^\r\n]+)")
LIGHT = re.compile(r"CREATE_CHAIN_BOX_LIGHT ([^\r\n]+)")
WHEEL_SKY = re.compile(r"CREATE_CHAIN_WHEEL_SKY \[([^]]+)\],([^\r\n]+)")


def cases(rising):
    suffix = "-rising" if rising else ""
    with (ROOT / f"fixtures/chain-conveyor-suspended{suffix}-java.csv").open() as stream:
        return {int(row["tick"]): row for row in csv.DictReader(stream)}


def rendered_poses(log):
    for position, fields in BOX.findall(log):
        data = fields.split(",")
        if int(data[0]) == ID and float(data[2]) >= 0.99999:
            owner = tuple(map(int, position.split(",")))
            pose = [float(value) for value in data[3:]]
            yield int(data[1]), owner, pose


def check_pose(tick, row, b, owner, pose):
    assert owner == (A if row["wheel"] == "A" else b), (tick, owner, row)
    local = [value - base for value, base in zip(pose[:6], (*A, *A), strict=True)]
    for actual, key in zip(local + pose[6:9], (
        "target_x", "target_y", "target_z", "physical_x", "physical_y", "physical_z", "yaw", "roll", "pitch",
    ), strict=True):
        tolerance = 1e-6 if key.startswith(("target_", "physical_")) else 5e-4
        assert abs(actual - float(row[key])) < tolerance, (tick, key, actual, row[key])
    assert all(count > 0 for count in pose[9:]), (tick, pose)


def inspect(log, start, expected, b):
    samples = {clock - start: (owner, pose) for clock, owner, pose in rendered_poses(log)}
    assert set(samples) == set(expected), (set(samples), set(expected))
    for tick, row in expected.items():
        check_pose(tick, row, b, *samples[tick])
    print(f"{len(expected)} Java suspended poses, continuous identity through the wheel handoff, both meshes")


def inspect_guest(log, start, expected, b):
    poses = iter(rendered_poses(log))
    for tick, row in expected.items():
        wanted = [float(row[f"target_{axis}"]) + base for axis, base in zip("xyz", A, strict=True)]
        owner = A if row["wheel"] == "A" else b
        # Use the first complete frame at each received target. The host's
        # frozen-step clock and the guest's display clock can differ.
        for sampled_tick, observed_owner, pose in poses:
            assert sampled_tick <= start + tick, (tick, sampled_tick, start)
            if (sampled_tick == start + tick and observed_owner == owner
                    and all(abs(a - expected) < 1e-6 for a, expected in zip(pose[:3], wanted))):
                check_pose(tick, row, b, observed_owner, pose)
                break
        else:
            raise AssertionError(f"LAN guest missed the Java cargo snapshot at tick {tick}")
    print(f"LAN guest matched all {len(expected)} Java poses and authoritative sample ticks")


def inspect_lighting(log, start):
    filename = ROOT / "fixtures/chain-conveyor-suspended-light-java.csv"
    with filename.open() as stream:
        rows = list(csv.DictReader(stream))
    samples = {}
    for fields in LIGHT.findall(log):
        identity, tick, fraction, x, y, z, wheel, box, rig = fields.split(",")
        if int(identity) == ID and float(fraction) >= 0.99999:
            cell = tuple(a - b for a, b in zip(map(int, (x, y, z)), A, strict=True))
            samples.setdefault(int(tick) - start, (cell, int(wheel), int(box), int(rig)))
    assert set(samples) == {int(row["tick"]) for row in rows}, samples
    differences = []
    for row in rows:
        tick = int(row["tick"])
        sampled_cell, wheel, box, rig = samples[tick]
        cell = tuple(int(row[f"cell_{axis}"]) for axis in "xyz")
        # Horizon stores sky on the low byte and block light on the high byte.
        package = (int(row["block"]) << 12) | (int(row["sky"]) << 4)
        wheel_light = (int(row["wheel_block"]) << 12) | (int(row["wheel_sky"]) << 4)
        expected = (cell, wheel_light, package, package)
        actual = (sampled_cell, wheel, box, rig)
        if actual != expected:
            differences.append((tick, actual, expected))
    assert not differences, f"{len(differences)} Java lighting mismatches, first {differences[:3]}"
    print(f"{len(rows)} Java lighting samples on package and rigging vertices")


def inspect_wheel_sky(log, b):
    filename = ROOT / "fixtures/chain-conveyor-wheel-sky-java.csv"
    with filename.open() as stream:
        expected = list(csv.reader(stream))[1:]
    samples = {tuple(map(int, position.split(","))): data.split(",")
               for position, data in WHEEL_SKY.findall(log)}
    for at, row in zip((A, b), expected, strict=True):
        # A has a motor below it. B checks propagation through the wheel
        # into air, independent of the motor's own lighting properties.
        fields = slice(None, -1) if at == A else slice(None)
        assert samples[at][fields] == row[1:][fields], (at, samples[at], row)
    print("Both wheels match Java skylight traits and levels, including the air beneath B")


def run(args):
    rising = args.scenario == "rising_reversal"
    delta = chain.WHEELS[args.scenario]
    b = tuple(origin + offset for origin, offset in zip(A, delta))
    expected = cases(rising)
    env = {"CREATE_CHAIN_RENDER": "1"}
    label = "ChainSuspendedLAN" if args.lan else "ChainSuspended"
    if rising:
        label += "Rising"
    if args.lighting:
        label += "Light"
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, label, pack=args.pack, render=not args.lan, env=env))
        observer, name = world, "@s"
        if args.lan:
            address = "127.0.0.1:" + str(world.call("lan", "open", "0", "commands", "force")["port"])
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-suspended-")))
            name = "SuspendedGuest"
            observer = stack.enter_context(multiplayer.joined_client(
                args, scratch, address, name, render=True, scenario=f"chain-suspended-{args.scenario}", pack=args.pack, env=env,
            ))
            multiplayer.until("guest to enter the package world", lambda: any(
                guest["name"] == name and guest["placed"] for guest in world.call("lan", "status")["guests"]
            ))
        chain.setup(world, A, b, MOTOR, PORT, delta, rising)
        if args.lighting:
            light = (A[0] + 5, A[1] - 1, A[2] + 1)
            world.command(f"/setblock {chain.coords(light)} minecraft:light[level=15]")
        if not rising:
            chain.merge(world, PORT, '{AddressFilter:"Lab-In",Target:{RelativePos:[I;-2,2,0],ChainPosition:150f}}')
            chain.merge(world, b, "{PackagePorts:[{Port:[I;2,-2,0],ChainPosition:150f}]}")
        world.command(f"/gamemode spectator {name}")
        world.command(f"/tp {name} 11.5 105 -4.5")
        if args.lan:
            multiplayer.until("guest to arrive at both chain wheels", lambda:
                              observer.call("state")["player"]["position"] == [11.5, 105, -4.5]
                              and observer.call("block", *b).get("state") == "create:chain_conveyor")
        observer.call("look-at", 12.0, 101.65, -8.5)
        observer.call("key", "f1", "tap")
        start = world.clock()
        log = observer.socket.parent / "ctl.log"
        stable_frames = []
        last = max(expected)
        end = last + 1 if rising else last + (5 if args.lan else 2)
        for tick in range(1, end):
            if rising and tick in (11, 41):
                chain.merge(world, MOTOR, f"{{ScrollValue:{-128 if tick == 11 else 128}}}")
            if rising and tick == 31:
                world.command(f"/setblock {chain.coords(MOTOR)} minecraft:air")
            if rising and tick == 63:
                chain.chain.set_link(world, A)
                chain.chain.set_link(world, b)
            world.step_to(start + tick)
            if rising and tick == 39:
                world.command(f"/setblock {chain.coords(MOTOR)} create:creative_motor[facing=up]")
            if tick == 2:
                cargo = chain.stack("Lab-In", "paper", 3)
                path = f"Position:0f,Connection:{chain.emit_vector(delta)}" if rising else "Position:40f"
                chain.merge(world, A, f"{{CargoSampleTime:{start + tick}L,"
                            f"Packages:[{{Item:{cargo},VisualId:{ID}L,{path}}}]}}")
            offset = log.stat().st_size
            observer.call("wait", 4 if args.lan else 3)
            if not args.lan:
                stable_frames.append(log.read_text()[offset:])
            if args.capture and tick == 13:
                observer.call("screenshot", args.capture)
        trace = log.read_text()
        if args.lan:
            inspect_guest(trace, start, expected, b)
            if not rising:
                assert not BOX.findall(trace[offset:]), "The suspended package stayed visible after the Frogport catch"
        else:
            trace = "\n".join(stable_frames)
            inspect(trace, start, expected, b)
        if args.lighting:
            inspect_lighting(trace, start)
            inspect_wheel_sky(trace, b)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--scenario", choices=chain.WHEELS, default="straight")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--lighting", action="store_true")
    args = parser.parse_args()
    if args.lighting and args.scenario != "straight":
        parser.error("the lighting reference uses the straight layout")
    run(args)
