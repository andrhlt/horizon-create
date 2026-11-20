#!/usr/bin/env python3
"""Replay Java-captured Hand Crank and motor transitions across all crank axes."""

import argparse
import csv
from importlib import import_module
from math import isclose
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

crank = import_module("test-hand-crank")
creative_motor = import_module("test-creative-motor")
CASES = {
    "stopped": ("south", 0, {}, {4: False, 9: True, 16: True}),
    "below": ("south", 31, {}, {4: False, 9: True, 16: True}),
    "above": ("south", 33, {}, {4: False, 9: True, 16: True}),
    "equal": ("south", 32, {}, {4: False, 9: False, 16: True}),
    "faster": ("south", 64, {}, {4: False, 9: True, 16: True}),
    "opposite": ("south", -32, {}, {4: False, 9: False, 16: True}),
    "change_before": ("south", 16, {2: 64}, {4: False, 9: True, 16: True}),
    "sign_before": ("south", 16, {2: -16}, {4: False, 9: True, 16: True}),
    "wrench": ("south", 0, {}, {4: False, 9: True, 16: True}),
    "change_during": ("south", 16, {7: 64}, {4: False, 9: True, 16: True}),
    "sign_during": ("south", 16, {7: -16}, {4: False, 9: True, 16: True}),
    "north": ("north", 32, {}, {4: False, 9: True, 16: True}),
    "east": ("east", 32, {}, {4: False, 9: True, 16: True}),
    "west": ("west", 32, {}, {4: False, 9: True, 16: True}),
    "up": ("up", 32, {}, {4: False, 9: True, 16: True}),
    "down": ("down", 32, {}, {4: True, 9: False, 16: True}),
}
NORMAL = {
    "north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0),
    "west": (-1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0),
}
AXIS = {"north": "z", "south": "z", "east": "x", "west": "x", "up": "y", "down": "y"}


def value(tag, key, integer=False):
    number = r"(-?\d+)" if integer else r"(-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)f"
    match = re.search(rf"\b{key}: {number}", tag)
    if match is None:
        raise RuntimeError(f"Missing {key} in {tag}")
    return int(match[1]) if integer else float(match[1])


def offset(pos, delta, amount=1):
    return tuple(a + amount * b for a, b in zip(pos, delta, strict=True))


def click(control, pos, sneaking, face=None):
    if sneaking:
        control.call("key", "shift", "down")
        control.call("wait", 3)
    try:
        control.call("interact", *pos, *((face,) if face else ()))
    finally:
        if sneaking:
            control.call("key", "shift", "up")


def setup(control, face, motor_setting):
    crank_pos = (crank.CRANK[0], crank.CRANK[1] + 1, crank.CRANK[2]) if AXIS[face] == "y" else crank.CRANK
    rear_delta = tuple(-value for value in NORMAL[face])
    rear = offset(crank_pos, rear_delta)
    gauge = offset(rear, rear_delta)
    motor = offset(gauge, rear_delta)
    axis = AXIS[face]
    gauge_facing, first = ("north", "false") if axis == "y" else ("up", str(axis == "x").lower())
    control.commands((
        f"/fill 1 {crank_pos[1] - 1} -15 10 {crank_pos[1] - 1} -5 minecraft:smooth_stone",
        f"/fill 1 {crank_pos[1]} -15 10 {crank_pos[1] + 3} -5 minecraft:air",
        f"/setblock {' '.join(map(str, rear))} create:shaft[axis={axis}]",
        f"/setblock {' '.join(map(str, gauge))} create:stressometer[facing={gauge_facing},axis_along_first={first}]",
        f"/setblock {' '.join(map(str, motor))} create:creative_motor[facing={face}]",
        f"/data merge block {' '.join(map(str, motor))} {{ScrollValue:{motor_setting}}}",
        f"/setblock {' '.join(map(str, crank_pos))} create:hand_crank[facing={face}]",
    ))
    player_x = crank_pos[0] + 1.5 if face == "east" else crank_pos[0] - 1.5
    control.call("tp", player_x, crank_pos[1], crank_pos[2] + 0.5)
    control.call("look-at", crank_pos[0] + 0.5, crank_pos[1] + 0.4, crank_pos[2] + 0.5)
    return crank_pos, rear, gauge, motor


def run_case(args, case, rows):
    face, initial_speed, changes, actions = CASES[case]
    delta = NORMAL[face]
    crank_pos = (crank.CRANK[0], crank.CRANK[1] + 1, crank.CRANK[2]) if AXIS[face] == "y" else crank.CRANK
    env = {"CREATE_HAND_CRANK_TRACE": ",".join(map(str, crank_pos))}
    mismatches = []
    with fixture_world(args, f"HandCrankMatrix{case.title()}", env=env, render=bool(changes),
                       pack=args.pack) as control:
        crank_pos, rear, gauge, motor = setup(control, face, initial_speed)
        if case == "wrench":
            control.commands((
                "/gamemode survival",
                "/item replace entity @s weapon.mainhand with create:wrench",
            ))
        start = control.clock()
        log = control.socket.parent / "ctl.log"
        for row in rows:
            tick = int(row["tick"])
            if tick == 0:
                continue
            control.step_to(start + tick)
            crank_state = control.call("block", *crank_pos)["block"]
            mounted = crank_state == "create:hand_crank"
            crank_tag = control.command(f"/data get block {' '.join(map(str, crank_pos))}") if mounted else ""
            trace = crank.trace(log, "TICK", start + tick)
            if mounted and len(trace) != 1:
                raise RuntimeError(f"{case} tick {tick}: expected one native crank trace, got {trace}")
            in_use = int(trace[0][0]) if trace else 0
            backwards = trace[0][1] == "true" if trace else False
            motor_state = control.call("block", *motor)["state"]
            motor_mounted = motor_state.startswith("create:creative_motor")
            motor_tag = (control.command(f"/data get block {' '.join(map(str, motor))}")
                         if motor_mounted else "")
            shaft_tag = control.command(f"/data get block {' '.join(map(str, rear))}")
            gauge_tag = control.command(f"/data get block {' '.join(map(str, gauge))}")
            entities = control.call("entities", 64, "minecraft:item")["entities"]
            drops = sum(entity["item"]["count"] for entity in entities
                        if entity["item"]["item"] == "create:hand_crank")
            drops += control.call("inventory")["counts"].get("create:hand_crank", 0)
            speed = value(shaft_tag, "Speed")
            stress = value(gauge_tag, "Stress")
            capacity = value(gauge_tag, "Capacity")
            actual = {
                "motor_mounted": motor_mounted,
                "motor_drops": sum(entity["item"]["count"] for entity in entities
                                    if entity["item"]["item"] == "create:creative_motor"),
                "mounted": mounted,
                "in_use": in_use if mounted else 0,
                "backwards": backwards if mounted else False,
                "crank_rpm": float(trace[0][2]) if trace else 0.0,
                "shaft_rpm": speed,
                "shaft_network_rpm": speed,
                "capacity": capacity,
                "stress": stress,
                "overstressed": stress > capacity,
                "drops": drops,
            }
            if motor_mounted:
                actual["motor_setting"] = value(motor_tag, "ScrollValue", integer=True)
            for key, got in actual.items():
                expected = row[key]
                if isinstance(got, float):
                    matched = isclose(float(expected), got, abs_tol=0.00002, rel_tol=0.0)
                else:
                    matched = expected == str(got).lower()
                if not matched:
                    mismatches.append(f"{case} tick {tick} {key}: Java {expected}, Horizon {got}")
            if row["motor_mounted"] == "true" and f"facing={face}" not in motor_state:
                mismatches.append(f"{case} tick {tick} motor facing: Java {face}, Horizon {motor_state}")
            if tick in changes:
                changed_speed = changes[tick]
                creative_motor.configure(
                    control, motor, 1 if changed_speed > 0 else 0, abs(changed_speed),
                    facing=face,
                )
            if tick in actions and mounted:
                player_x = crank_pos[0] + 1.5 if face == "east" else crank_pos[0] - 1.5
                control.call("tp", player_x, crank_pos[1], crank_pos[2] + 0.5)
                control.call("look-at", crank_pos[0] + 0.5, crank_pos[1] + 0.4, crank_pos[2] + 0.5)
                try:
                    click(control, crank_pos, sneaking=actions[tick])
                except RuntimeError as error:
                    raise RuntimeError(f"{case} tick {tick}: player click failed: {error}") from error
                if control.call("block", *crank_pos)["state"] == "minecraft:air":
                    control.call("command", "/tp @s 2.5 101 -7.5")
    return mismatches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--case", choices=(*CASES, "all"), default="all")
    args = parser.parse_args()
    with (ROOT / "fixtures/hand-crank-matrix-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    selected = [args.case] if args.case != "all" else list(CASES)
    mismatches = []
    samples = 0
    for case in selected:
        print(f"Comparing {case}...", flush=True)
        case_rows = [row for row in rows if row["scenario"] == case]
        if not case_rows:
            raise RuntimeError(f"Missing Java rows for {case}")
        mismatches.extend(run_case(args, case, case_rows))
        samples += len(case_rows) - 1
    if mismatches:
        raise RuntimeError(f"{len(mismatches)} mismatches across {samples} Java rows:\n"
                           + "\n".join(mismatches[:30]))
    print(f"Hand Crank motor matrix matched {samples} Java ticks across {len(selected)} scenarios.")


if __name__ == "__main__":
    main()
