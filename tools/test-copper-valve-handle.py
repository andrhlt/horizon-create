#!/usr/bin/env python3
"""Replay Java Copper Valve settings, mounting and activation with local player inputs."""
import argparse
import csv
import re
from pathlib import Path

from fixture_world import ROOT, fixture_world

HANDLE = (8, 101, -10)
SHAFT = (7, 101, -10)
ANGLES = ((1, 95), (0, 137), (1, 0))
LABELS = ("Negative rotation angle", "Positive rotation angle")
SIDES = {
    "down": (0, -1, 0), "up": (0, 1, 0), "north": (0, 0, -1),
    "south": (0, 0, 1), "west": (-1, 0, 0), "east": (1, 0, 0),
}


def coord(pos):
    return " ".join(map(str, pos))


def tag(text, key, default=0):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", text)
    return float(match[1]) if match else default


def sample(control):
    handle, shaft = control.commands(f"/data get block {coord(pos)}" for pos in (HANDLE, SHAFT))
    if 'id: "create:valve_handle"' not in handle or 'id: "create:simple_kinetic"' not in shaft:
        raise RuntimeError(f"Missing valve or shaft block entity: {handle}, {shaft}.")
    time_left = tag(handle, "InUse")
    return (tag(handle, "ScrollValue", 45), time_left, tag(handle, "TotalUseTicks"),
            tag(handle, "StartAngle"), tag(handle, "TargetAngle"), tag(handle, "Cooldown"),
            time_left == 0, tag(handle, "Speed"), tag(shaft, "Speed"))


def point_at(control, pos=HANDLE, face="east", offset=0.0):
    normal = SIDES[face]
    tangent = (1, 0, 0) if normal[0] == 0 else (0, 0, 1)
    point = [p + 0.5 - direction * 0.001 + along * offset
             for p, direction, along in zip(pos, normal, tangent, strict=True)]
    control.call("look-at", *point)
    control.call("wait", 1)
    hit = control.call("looking-at").get("block")
    if not hit or hit["pos"] != list(pos) or hit["face"] != face:
        raise RuntimeError(f"Expected controlled valve pick for {pos} {face} at {point}, got {hit}.")
    return hit


def configure(control, row, value, *, frame=None):
    point_at(control)
    control.call("script", script="mouse right down\nwait 7\n")
    buttons = control.call("screen")["buttons"]
    bar = next((button for button in buttons if button["label"] == LABELS[row]), None)
    if bar is None:
        raise RuntimeError(f"The rotation angle board did not open after six held input ticks: {buttons}.")
    if bar["w"] != 202 or [button["label"] for button in buttons if button["label"] in LABELS] != list(LABELS):
        raise RuntimeError(f"Expected both Java signed rows and a 180-degree bar, got {buttons}.")
    x = bar["x"] + ((max(1, value) - 1) // 45) * 4 + value + 1.5
    x += 2 if value % 45 == 0 else 0
    x += 4 if value > 0 else 0
    y = bar["y"] + bar["h"] / 2
    control.call("scroll-at", x, y, 0)
    if frame:
        control.call("screenshot", str(frame))
    if control.call("state")["screen"] != "mod":
        raise RuntimeError("The valve board closed before release.")
    control.call("click-at", x, y, "right")
    control.call("wait", 4)
    if control.call("state")["screen"] != "playing":
        raise RuntimeError("Releasing use failed to close the valve board.")


def activate(control, *, short=True, sneaking=False, check_press=None):
    if sneaking:
        control.call("key", "shift", "down")
        control.call("wait", 2)
    point_at(control)
    control.call("script", script="mouse right down\nwait 2\n")
    if check_press and sample(check_press)[1] != 0:
        raise RuntimeError("Short valve use activated before the player released the key.")
    control.call("script", script="mouse right up\nwait 3\n")
    if sneaking:
        control.call("key", "shift", "up")
    if short and control.call("state")["screen"] != "playing":
        raise RuntimeError("A short valve tap opened the angle board.")


def setup(control):
    control.commands((
        "/fill 4 100 -15 14 100 -5 minecraft:smooth_stone",
        "/fill 4 101 -15 14 105 -5 minecraft:air",
        f"/setblock {coord(HANDLE)} create:copper_valve_handle[facing=east]",
        f"/setblock {coord(SHAFT)} create:shaft[axis=x]",
        "/gamemode survival",
        "/tp @s 11.500 101.000 -9.500",
    ))
    control.call("wait", 3)


def placement(control, rows):
    control.command("/fill 4 100 -15 14 100 -3 minecraft:smooth_stone")
    control.command("/item replace entity @s hotbar.0 with create:copper_valve_handle 12")
    control.call("select", "create:copper_valve_handle")
    for case, clicked_face, placed_face, is_wet, survives in rows:
        normal = SIDES[clicked_face]
        pos = (8, 103, -8)
        support = tuple(p - d for p, d in zip(pos, normal, strict=True))
        west = (pos[0] - 1, pos[1], pos[2])
        platform = ("/setblock 10 104 -8 minecraft:stone",) if clicked_face == "up" else ()
        camera = (10.5, 105.0, -7.5) if clicked_face == "up" else (
            8.5 + 3.0 * normal[0], 101.0, -7.5 + 3.0 * normal[2]
        )
        control.commands((
            "/fill 6 102 -10 10 105 -6 minecraft:air",
            f"/setblock {coord(support)} minecraft:stone",
            f"/setblock {coord(pos)} {'minecraft:water' if is_wet == 'true' else 'minecraft:air'}",
            *((f"/setblock {coord(west)} create:shaft[axis=x]",) if int(case) in (7, 8) else ()),
            *platform,
            f"/tp @s {coord(camera)}",
        ))
        control.call("wait", 3)
        if int(case) == 8:
            control.call("key", "shift", "down")
            control.call("wait", 2)
        control.call("interact", *support, clicked_face)
        control.call("wait", 2)
        if int(case) == 8:
            control.call("key", "shift", "up")
            control.call("wait", 1)
        actual = control.call("block", *pos)["state"]
        wanted = f"create:copper_valve_handle[facing={placed_face},waterlogged={is_wet}]"
        if survives != "true" or actual != wanted:
            raise RuntimeError(f"Valve placement case {case} {clicked_face} gave {actual} expected {wanted}.")
        if int(case) < 6:
            face = SIDES[placed_face]
            if placed_face == "up":
                control.command("/setblock 10 104 -8 minecraft:stone")
                camera = (10.5, 105.0, -7.5)
            else:
                camera = (8.5 + 3.0 * face[0], 101.0, -7.5 + 3.0 * face[2])
            control.command(f"/tp @s {coord(camera)}")
            control.call("wait", 3)
            hit = point_at(control, pos, placed_face)
            axis = next(i for i, direction in enumerate(face) if direction)
            if abs(hit["point"][axis] - (pos[axis] + 0.5)) > 0.00001:
                raise RuntimeError(f"The valve outline face should meet the block center plane: {hit}.")
    print(f"Valve player placement matched {len(rows)} Java cases.", flush=True)


def verify_input_timing(log):
    opened = releases = submits = short_taps = 0
    hold_started = 0
    for line in log.read_text().splitlines():
        if not line.startswith("CREATE_SPEED_CONTROLLER_INPUT "):
            continue
        _, tick, event, _ = line.split()
        tick = int(tick)
        if event == "hold":
            hold_started = tick
        if event == "open":
            if tick - hold_started + 1 != 6:
                raise RuntimeError(f"The valve settings opened on held tick {tick - hold_started + 1}.")
            opened += 1
        if event == "release":
            releases += 1
        if event == "submit":
            if releases <= submits:
                raise RuntimeError("The valve configuration was submitted before releasing use.")
            submits += 1
        if event == "short":
            short_taps += 1
    if (opened, releases, submits, short_taps) != (3, 3, 3, 2):
        raise RuntimeError(f"Expected three six-tick selections and two short releases, got {(opened, releases, submits, short_taps)}.")


def reference(name):
    with (ROOT / f"fixtures/copper-valve-handle-{name}-java.csv").open() as source:
        _, *rows = csv.reader(source)
        return rows


def replay(args):
    differences = []
    rows = reference("angle")
    if len(rows) != 93:
        raise RuntimeError(f"Expected 93 Java samples, got {len(rows)}.")
    if args.frames:
        args.frames.mkdir(parents=True, exist_ok=True)
    if args.placement:
        cases = reference("placement")
        if len(cases) != 9:
            raise RuntimeError(f"Expected nine valve placement cases, got {len(cases)}.")
    world = "CopperValveMounting" if args.placement else "CopperValveReplay"
    with fixture_world(args, world, render=True, pack=args.pack,
                       env={"CREATE_SPEED_CONTROLLER_INPUT_TRACE": "1"}) as control:
        if args.placement:
            setup(control)
            placement(control, cases)
            return
        actual_rows = []
        for index, (row, angle) in enumerate(ANGLES):
            if index == 0:
                setup(control)
            else:
                control.commands((
                    f"/setblock {coord(HANDLE)} minecraft:air",
                    f"/setblock {coord(HANDLE)} create:copper_valve_handle[facing=east]",
                ))
            control.step_to(control.clock() + 1)
            start = control.clock()
            for raw in rows:
                tick, case, *values = raw
                if int(case) != index:
                    continue
                tick = int(tick)
                if tick > 0:
                    control.step_to(start + tick)
                actual = sample(control)
                expected = tuple(value == "true" if value in ("true", "false")
                                 else float(value) for value in values)
                actual_rows.append((tick, index, *actual))
                for field, goal, got in zip(("setting", "in use", "total use", "start", "target",
                                            "cooldown", "show value", "handle rpm", "shaft rpm"),
                                           expected, actual, strict=True):
                    if got != goal:
                        differences.append((index, tick, field, goal, got))
                if tick == 3:
                    configure(control, row, angle,
                              frame=(args.frames / f"valve-{index}.png") if args.frames else None)
                if tick == 5:
                    activate(control, sneaking=index == 2,
                             check_press=control if index != 2 else None)
                if tick == 7:
                    activate(control)
        if args.output:
            with args.output.open("w", newline="") as output:
                csv.writer(output).writerows(actual_rows)
        if differences:
            raise RuntimeError(f"{len(differences)} Java differences, first 25: {differences[:25]}")
        verify_input_timing(control.socket.parent / "ctl.log")
    print(f"Valve signed settings, activation, cooldown and output match {len(rows)} Java tick samples.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--frames", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--placement", action="store_true")
    replay(parser.parse_args())


if __name__ == "__main__":
    main()
