#!/usr/bin/env python3
"""Compare the original Creative Motor rotating half-shaft in all six facings.

The pinned Java probe records, for every facing, the rotation axis, the
half-shaft side and the network speed at +32 and -48 RPM. Horizon renders the
real block entity offscreen and each frame is compared to the Java row: the
axis, half-shaft side and RPM come from Java, while the 22.5 degree parity phase
and the kinetic angle are validated against the pinned formula at the rendered
position and tick.
"""

import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
from math import fmod, isclose
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep

from fixture_world import ROOT, fixture_world

TRACE = "CREATE_MOTOR_FRAME "
FACINGS = ("down", "up", "north", "south", "west", "east")
BASE = (8, 101, -10)
SPACING = 4
OFFSETS = {
    "down": (0, -1, 0),
    "up": (0, 1, 0),
    "north": (0, 0, -1),
    "south": (0, 0, 1),
    "west": (-1, 0, 0),
    "east": (1, 0, 0),
}
AXIS = {"x": 0, "y": 1, "z": 2}
# Java set the signed setting to +32 at its tick 0 and -48 at its tick 8.
LOW_TICK = 7
HIGH_TICK = 11


def position(case):
    return (BASE[0] + SPACING * case, BASE[1], BASE[2])


def facing_axis(facing):
    return next(i for i, value in enumerate(OFFSETS[facing]) if value)


def shaft_position(case):
    return tuple(a + b for a, b in zip(position(case), OFFSETS[FACINGS[case]], strict=True))


def reference():
    result = {}
    with (ROOT / "fixtures/creative-motor-render-java.csv").open(newline="") as source:
        for row in csv.DictReader(source):
            result[(int(row["tick"]), int(row["index"]))] = row
    return result


def expected_phase(case):
    x, y, z = position(case)
    index = facing_axis(FACINGS[case])
    parity = sum((x, y, z)[i] for i in range(3) if i != index)
    return 22.5 if parity % 2 == 0 else 0.0


def place(control, value, *, break_first=False):
    """Place all six facings with an inline signed `ScrollValue`.

    Java's `ScrollValue` is written with the block, so a fresh placement sends
    the motor's update tag and the offscreen client draws the new speed without
    waiting for a view change.
    """
    commands = []
    for case, facing in enumerate(FACINGS):
        mx, my, mz = position(case)
        sx, sy, sz = shaft_position(case)
        axis = "xyz"[facing_axis(facing)]
        if break_first:
            commands.append(f"/setblock {mx} {my} {mz} minecraft:air")
        commands.append(f"/setblock {mx} {my} {mz} create:creative_motor[facing={facing}]{{ScrollValue:{value}}}")
        commands.append(f"/setblock {sx} {sy} {sz} create:shaft[axis={axis}]")
    control.commands(commands)


def refresh_view(control, target):
    control.command(f"/tp @s {BASE[0] + 10.5} 108.0 {-2.5}")
    control.command(f"/tp @s {BASE[0] + 10.5} 108.0 -2.0")
    control.call("look-at", *target)


def setup(control):
    control.commands(("/fill 4 98 -13 32 105 -6 minecraft:air",))
    place(control, 32)
    control.commands(("/tp @s 18.5 108 -2.0",))
    control.call("look-at", 18.5, 101.0, -10.0)


def await_frame(log, case, want, *, label):
    """Wait until the latest rendered frame for the case shows Java's speed."""
    x, y, z = position(case)
    facing = FACINGS[case]
    index = facing_axis(facing)
    sign_want = 1 if OFFSETS[facing][index] > 0 else -1
    deadline = monotonic() + 10
    while monotonic() < deadline:
        for line in reversed(log.read_text().splitlines()):
            if not line.startswith(TRACE):
                continue
            fields = line[len(TRACE):].split(",")
            if len(fields) != 12 or (int(fields[0]), int(fields[1]), int(fields[2])) != (x, y, z):
                continue
            if int(fields[4]) == AXIS[want["axis"]] and int(fields[5]) == sign_want \
                    and float(fields[9]) == float(want["speed"]):
                return fields
            break
        sleep(0.06)
    seen = sorted({
        (line.split(",")[0].split()[-1], line.split(",")[1], line.split(",")[2],
         line.split(",")[4], line.split(",")[5], line.split(",")[9])
        for line in log.read_text().splitlines() if line.startswith(TRACE)
    })
    raise RuntimeError(f"{label}: no rendered Creative Motor frame for {facing} with Java speed {want['speed']}. Seen {seen}.")


def check(log, case, want, *, label):
    facing = FACINGS[case]
    _, _, _, face, axis, sign, tick, partial, phase, rpm, angle, vertices = await_frame(log, case, want, label=label)
    assert face == facing, (label, facing, face)
    assert int(vertices) > 0, (label, facing)
    phase_want = expected_phase(case)
    assert float(phase) == phase_want, (label, facing, phase_want, phase)
    expected = fmod((int(tick) + float(partial)) * float(rpm) * 3 / 10 + float(phase), 360.0)
    error = (float(angle) - expected + 180) % 360 - 180
    assert isclose(error, 0.0, abs_tol=0.0003), (label, facing, expected, angle)


def settle(control, ticks):
    for _ in range(ticks):
        control.step_to(control.clock() + 1)


def verify(args):
    rows = reference()
    with fixture_world(args, "CreativeMotorRender", render=True, pack=args.pack,
                       env={"CREATE_MOTOR_RENDER": "1"}) as control:
        setup(control)
        log = control.socket.parent / "ctl.log"
        settle(control, LOW_TICK)
        for case in range(len(FACINGS)):
            check(log, case, rows[LOW_TICK, case], label="low")
        place(control, -48, break_first=True)
        refresh_view(control, (18.5, 101.0, -10.0))
        settle(control, HIGH_TICK - LOW_TICK)
        for case in range(len(FACINGS)):
            check(log, case, rows[HIGH_TICK, case], label="high")
    print("All six Creative Motor facings rendered Java's half-shaft axis, side and RPM with matching phase and angle at both settings.")


def load(name):
    spec = spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_lan(args, scratch):
    guest_name = "MotorViewer"
    multiplayer = load("test-multiplayer")
    os.environ["CREATE_MOTOR_RENDER"] = "1"
    case = FACINGS.index("south")
    rows = reference()
    with fixture_world(args, "CreativeMotorRenderLAN", render=True, pack=args.pack) as host:
        mx, my, mz = position(case)
        sx, sy, sz = shaft_position(case)
        px, pz = mx + 4.5, mz + 4.5
        host.commands((
            f"/fill {mx - 4} {my - 3} {mz - 4} {mx + 5} {my + 5} {mz + 5} minecraft:air",
            f"/fill {mx - 4} {my + 1} {mz - 4} {mx + 5} {my + 1} {mz + 5} minecraft:smooth_stone",
            f"/setblock {mx} {my} {mz} create:creative_motor[facing=south]{{ScrollValue:32}}",
            f"/setblock {sx} {sy} {sz} create:shaft[axis=z]",
            f"/tp @s {px} {my + 2} {pz}",
        ))
        host.call("look-at", mx + 0.5, my, mz + 0.5)
        settle(host, LOW_TICK)
        address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
        with multiplayer.joined_client(args, scratch, address, guest_name, render=True,
                                       scenario="creative-motor-render", pack=args.pack) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                user["name"] == guest_name and user["placed"]
                for user in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {guest_name}",
                f"/tp {guest_name} {px} {my + 2} {pz}",
            ))
            guest.call("look-at", mx + 0.5, my, mz + 0.5)
            settle(host, 3)
            for peer, label in ((host, "host"), (guest, "guest")):
                check(peer.socket.parent / "ctl.log", case, rows[LOW_TICK, case], label=label)
            host.commands((
                f"/setblock {mx} {my} {mz} minecraft:air",
                f"/setblock {mx} {my} {mz} create:creative_motor[facing=south]{{ScrollValue:-48}}",
            ))
            host.call("look-at", mx + 0.5, my, mz + 0.5)
            guest.call("look-at", mx + 0.5, my, mz + 0.5)
            settle(host, 4)
            for peer, label in ((host, "host"), (guest, "guest")):
                check(peer.socket.parent / "ctl.log", case, rows[HIGH_TICK, case], label=label)
    print("The LAN host and guest rendered Java's Creative Motor half-shaft, phase and RPM at both settings.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-cmr-") as scratch:
            verify_lan(args, Path(scratch))
    else:
        verify(args)


if __name__ == "__main__":
    main()
