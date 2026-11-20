#!/usr/bin/env python3
"""Replay Java Chassis range boards, grouping, and moving capture."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

ROOT_BLOCK = (8, 201, 42)
BEARING = (8, 200, 42)
MOTOR = (8, 199, 42)
PRIMARY = "create:linear_chassis"
SECONDARY = "create:secondary_linear_chassis"
RADIAL = "create:radial_chassis"


def coordinates(pos):
    return " ".join(map(str, pos))


def property_value(state, key):
    match = re.search(rf"\b{key}=([a-z]+)", state)
    if match is None:
        raise RuntimeError(f"Missing {key} in block state {state!r}.")
    return match[1]


def initial_build(radial):
    if radial:
        sticky = f"{RADIAL}[axis=y,sticky_east=true]"
        peer, outside = (8, 202, 42), (8, 201, 41)
        unrelated = f"{RADIAL}[axis=y]"
    else:
        sticky = f"{PRIMARY}[axis=x,sticky_top=true]"
        peer, outside = (8, 201, 43), (8, 201, 44)
        unrelated = f"{SECONDARY}[axis=x]"
    build = {ROOT_BLOCK: sticky, peer: sticky, outside: unrelated}
    for n in range(1, 18):
        build[(8 + n, 201, 42)] = "minecraft:stone"
        build[(8 + n, peer[1], peer[2])] = "minecraft:bricks"
    if radial:
        build[(9, 201, 43)] = "minecraft:oak_planks"
        build[(9, 201, 44)] = "minecraft:smooth_stone"
    return build, peer, outside


def values(control, *positions):
    data = control.commands(f"/data get block {coordinates(pos)} ScrollValue" for pos in positions)
    values = [re.search(r"block data: (-?\d+)$", line) for line in data]
    if not all(values):
        raise RuntimeError(f"Could not read chassis range: {data}")
    return [entry[1] for entry in values]


def aim(control):
    control.call("look-at", 8.001, 201.5, 42.5)


def verify_short_and_no_wrench(control, normal):
    if normal != "8":
        raise RuntimeError(f"Expected the Java initial range of 8, got {normal}.")
    aim(control)
    control.call("script", script="mouse right down\nwait 8\nmouse right up\nwait 3\n")
    if control.call("state")["screen"] != "playing":
        raise RuntimeError("The chassis range board opened without a wrench.")
    control.command("/item replace entity @s hotbar.0 with create:wrench")
    control.call("select", "create:wrench")
    aim(control)
    control.call("script", script="mouse right down\nwait 3\nmouse right up\nwait 4\n")
    if control.call("state")["screen"] != "playing" or values(control, ROOT_BLOCK) != [normal]:
        raise RuntimeError("A short wrench press changed the range or opened the board.")


def settings(control, board, column, *, bulk=False, check_press=False):
    aim(control)
    control.call("mouse", "right", "down")
    control.call("wait", 7)
    screen = control.call("screen")
    label = board["row"]
    cell = next((button for button in screen["buttons"] if button["label"] == label), None)
    if cell is None:
        raise RuntimeError(f"Holding the wrench did not open the Distance board: {screen}")
    if column < 0:
        x = cell["x"] - 18.0
    elif column > int(board["last_column"]):
        x = cell["x"] + cell["w"] + 18.0
    else:
        x = cell["x"] + 3.5 + column * 6.0
    y = cell["y"] + cell["h"] / 2
    control.call("scroll-at", x, y, 0)
    if check_press:
        previous = values(control, ROOT_BLOCK)
        control.call("click-at", x, y)
        control.call("wait", 2)
        if control.call("state")["screen"] != "mod" or values(control, ROOT_BLOCK) != previous:
            raise RuntimeError("Clicking another mouse button committed the range.")
    if bulk:
        control.call("key", "ctrl", "down")
    try:
        control.call("click-at", x, y, "right")
        control.call("wait", 4)
    finally:
        if bulk:
            control.call("key", "ctrl", "up")
    if control.call("state")["screen"] != "playing":
        raise RuntimeError("Releasing use did not close the range board.")


def captured(control, expected):
    bearing = coordinates(BEARING)
    count = len(expected.split("|"))
    values = control.commands(f"/data get block {bearing} MovedBlocks[{index}].Pos"
                              for index in range(count + 1))
    if "no elements matching" not in values[-1].lower():
        raise RuntimeError(f"The assembly has additional blocks: {values}")
    positions = [re.search(r"\[I;\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\]", value)
                 for value in values[:-1]]
    if not all(positions):
        raise RuntimeError(f"The assembly did not capture all expected positions: {values}")
    return "|".join(sorted(":".join(match.groups()) for match in positions))


def verify_holds(output, warmup, expected):
    held = None
    opened = 0
    for row in output.read_text().splitlines():
        if not row.startswith("CREATE_CHASSIS_RANGE_INPUT "):
            continue
        _, tick, event, _ = row.split()
        if event == "hold":
            held = int(tick)
        if event == "open":
            if held is None or int(tick) - held + 1 != warmup:
                raise RuntimeError(f"The board warmup did not match Java: {row}")
            opened += 1
    if opened != expected:
        raise RuntimeError(f"Expected {expected} completed wrench holds, found {opened}: {output}")


def run(args):
    with (ROOT / "fixtures/chassis-range-java.csv").open() as file:
        reader = csv.reader(file)
        header, *expected = reader
    with (ROOT / "fixtures/chassis-range-ui-java.csv").open() as file:
        boards = {row["variant"]: row for row in csv.DictReader(file)}
    actual = []
    for before, moving, after in zip(expected[::3], expected[1::3], expected[2::3], strict=True):
        scenario = int(before[0])
        radial = scenario % 2 == 1
        board = boards["radial" if radial else "linear"]
        build, peer, outside = initial_build(radial)
        world = f"chassis-range-{scenario}"
        with fixture_world(args, world, render=True, pack=args.pack,
                           env={"CREATE_CHASSIS_RANGE_INPUT_TRACE": "1"}) as control:
            control.commands((
                "/fill 4 200 40 7 200 45 minecraft:smooth_stone",
                "/tp @s 5.5 201 42.5 -90 24",
                *(f"/setblock {coordinates(pos)} {state}" for pos, state in build.items()),
                f"/setblock {coordinates(BEARING)} create:mechanical_bearing[facing=up]",
                f"/setblock {coordinates(MOTOR)} create:creative_motor[facing=up]{{ScrollValue:0}}",
                "/gamemode survival",
            ))
            for _ in range(2):
                control.step_to(control.clock() + 1)
            default, = values(control, ROOT_BLOCK)
            verify_short_and_no_wrench(control, default)
            settings(control, board, -200, check_press=True)
            low, = values(control, ROOT_BLOCK)
            settings(control, board, 200)
            high, = values(control, ROOT_BLOCK)
            settings(control, board, (1, 2, 15, 15)[scenario], bulk=scenario > 1)
            actual.append([str(scenario), "0", default, low, high,
                           *values(control, ROOT_BLOCK, peer, outside), "-"])
            start = control.clock()
            control.command(f"/data merge block {coordinates(MOTOR)} {{ScrollValue:16}}")
            control.step_to(start + 1)
            actual.append([str(scenario), "1", "-", "-", "-", "-", "-", "-",
                           captured(control, moving[-1])])
            control.command(f"/data merge block {coordinates(MOTOR)} {{ScrollValue:0}}")
            control.step_to(start + 2)
            actual.append([str(scenario), "2", "-", "-", "-", *values(control, ROOT_BLOCK, peer, outside), "-"])
        verify_holds(ROOT / f".local/horizon-{world}.log", int(board["hold_ticks"]), 3)
    out = ROOT / ".local/chassis-range-horizon.csv"
    with out.open("w") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
    if differences:
        raise RuntimeError(f"Chassis range differed (Java, Horizon): {differences}.")
    print(f"Linear and Radial Chassis range controls, six-tick holds, and captures matched all {len(actual)} Java ticks.")


def persistence(args):
    """Keep a configured mixed linear group through a world restart and move it."""
    anchor = (8, 201, 42)
    east = (9, 201, 42)
    payload = (10, 201, 42)
    members = (anchor, east)
    bearing, motor = BEARING, MOTOR
    with (ROOT / "fixtures/secondary-linear-chassis-java.csv").open() as file:
        reference = next(row["payload"] for row in csv.DictReader(file)
                         if row["scenario"] == "2" and row["tick"] == "1")
    expected_payload = "|".join(sorted(
        position for position, _ in (entry.split("=", 1) for entry in reference.split("|"))
        if position.split(":")[2] == "0"
    ))
    with fixture_world(args, "chassis-range-reopen", render=True, pack=args.pack) as control:
        control.commands((
            "/tp @s 5.5 201 42.5 -90 24",
            f"/setblock {coordinates(anchor)} {PRIMARY}[axis=x,sticky_top=true]",
            f"/setblock {coordinates(east)} {SECONDARY}[axis=x,sticky_top=true]",
            f"/setblock {coordinates(payload)} minecraft:bricks",
            f"/setblock {coordinates(bearing)} create:mechanical_bearing[facing=up]",
            f"/setblock {coordinates(motor)} create:creative_motor[facing=up]{{ScrollValue:0}}",
            *(f"/data merge block {coordinates(member)} {{ScrollValue:2}}" for member in members),
            "/gamemode survival",
        ))
        for _ in range(2):
            control.step_to(control.clock() + 1)
        control.restart()
        observed = [control.call("block", *pos) for pos in (*members, payload)]
        if [block["block"] for block in observed] != [PRIMARY, SECONDARY, "minecraft:bricks"]:
            raise RuntimeError(f"Chassis assembly changed after reopen: {observed}.")
        if (property_value(observed[0]["state"], "sticky_top") != "true"
                or property_value(observed[1]["state"], "sticky_top") != "true"):
            raise RuntimeError(f"Mixed chassis sticky faces changed after reopen: {observed[:2]}.")
        ranges = values(control, *members)
        if ranges != ["2"] * len(members):
            raise RuntimeError(f"Chassis ranges changed after reopen: expected two 2s, got {ranges}.")
        control.command(f"/data merge block {coordinates(motor)} {{ScrollValue:16}}")
        control.step_to(control.clock() + 1)
        actual_payload = captured(control, expected_payload)
        if actual_payload != expected_payload:
            raise RuntimeError(f"Reopened mixed chassis group captured {actual_payload}; Java {expected_payload}.")
        control.restart()
        actual_payload = captured(control, expected_payload)
        if actual_payload != expected_payload:
            raise RuntimeError(f"Active mixed chassis payload changed across restart: {actual_payload}.")
    print("Mixed chassis membership and ranges survived idle restart; the active payload survived a second restart.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--persistence", action="store_true")
    args = parser.parse_args()
    if args.persistence:
        persistence(args)
    else:
        run(args)
