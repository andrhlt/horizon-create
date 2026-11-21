#!/usr/bin/env python3
"""Compare both Hose Pulley buffers and the full liquid volumes every tick."""

import argparse
import csv
from contextlib import ExitStack
import importlib
from pathlib import Path
import re
import tempfile

from fixture_world import ROOT, fixture_world

multiplayer = importlib.import_module("test-multiplayer")

STRUCTURE = Path("gametest/fluids/hose_pulley_transfer.nbt")
REGIONS = tuple(
    tuple((x, y, z) for z in range(-10, -7) for y in range(98, 101)
          for x in range(start, start + 3))
    for start in (5, 11)
)
BLOCK_QUERIES = "".join(
    "blocks " + " ".join(map(str, region[0] + region[-1])) + "\n"
    for region in REGIONS
)


def value(nbt, name):
    match = re.search(rf'\b{name}: (-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)', nbt)
    return float(match[1]) if match else 0.0


def water(state):
    if not state.startswith("minecraft:water"):
        return "-"
    level = re.search(r"level=(\d+)", state)
    level = int(level[1]) if level else 0
    return str(8 if level == 0 or level >= 8 else 8 - level)


def sample(control, tick):
    fill, drain, pump = control.commands((
        "/data get block 7 102 -9",
        "/data get block 11 102 -9",
        "/data get block 9 102 -9",
    ))
    regions = control.call("script", script=BLOCK_QUERIES)
    cells = []
    for region, reply in zip(REGIONS, regions, strict=True):
        by_position = {(x, y, z): state for x, y, z, state in reply["blocks"]}
        cells.append("".join(water(by_position.get(pos, "minecraft:air")) for pos in region))
    return [
        str(tick), f"{value(fill, 'Value'):.4f}", f"{value(drain, 'Value'):.4f}",
        *(f"{value(part, 'Speed'):.4f}" for part in (fill, drain, pump)),
        str(int(value(fill, "amount"))), str(int(value(drain, "amount"))),
        *cells,
    ]


def verify_finite_reference(rows):
    """Keep the original fixture honest about its finite 27-source body."""
    if len(rows) != 301:
        raise ValueError("Finite-body and lifecycle assertions require the full 301-tick reference")
    by_tick = {int(row[0]): dict(zip(
        ("tick", "fill_offset", "drain_offset", "fill_rpm", "drain_rpm", "pump_rpm",
         "fill_buffer", "drain_buffer", "destination", "source"), row, strict=True))
               for row in rows}
    assert by_tick[0]["source"] == "8" * 27 and by_tick[0]["destination"] == "-" * 27
    assert by_tick[11]["source"].count("-") == 1
    assert by_tick[18]["destination"].count("8") == 1
    assert by_tick[221]["source"] == "-" * 27 and by_tick[221]["destination"] == "8" * 27
    assert by_tick[221]["fill_buffer"] == by_tick[221]["drain_buffer"] == "0"


def total_water(state):
    cells = state[8] + state[9]
    return sum(int(level) for level in cells if level != "-") * 125 + int(state[6]) + int(state[7])


def verify_lifecycle(args, expected):
    by_tick = {int(row[0]): row for row in expected}
    with fixture_world(args, "Hose-pulley-reopen", STRUCTURE) as control:
        control.command("/place template create:gametest/fluids/hose_pulley_transfer 3 96 -12 none none 1 0 strict")
        control.command("/setblock 10 102 -7 minecraft:lever[face=wall,facing=south,powered=true]")
        control.call("wait", 3)
        idle = sample(control, 0)
        if value(control.command("/data get block 9 102 -9"), "Speed") != 0:
            raise SystemExit(f"Idle lifecycle fixture unexpectedly has a running pump: {idle}")
        control.command("/save-all")
        control.restart()
        reopened_idle = sample(control, 0)
        if idle[1:] != reopened_idle[1:] or total_water(reopened_idle) != 27000:
            raise SystemExit(f"Idle save/reopen changed Hose Pulley state: {idle} -> {reopened_idle}")

        control.command("/setblock 10 102 -7 minecraft:lever[face=wall,facing=south,powered=false]")
        start = control.clock()
        for tick in range(1, 101):
            control.step_to(start + tick)
        active = sample(control, 100)
        if total_water(active) != 27000:
            raise SystemExit(f"Active lifecycle fixture lost water before save: {active}")
        control.command("/save-all")
        control.restart()
        reopened_active = sample(control, 100)
        matching_ticks = [
            tick for tick, expected_state in by_tick.items()
            if tick >= 100 and expected_state[1:] == reopened_active[1:]
        ]
        if not matching_ticks:
            raise SystemExit(f"Active reopen state does not match the Java trace: {active} -> {reopened_active}")
        reopened_tick = matching_ticks[0]
        if value(control.command("/data get block 9 102 -9"), "Speed") == 0:
            raise SystemExit("The pump did not resume after active save/reopen")
        if total_water(reopened_active) != 27000:
            raise SystemExit(f"Active save/reopen duplicated or lost water: {reopened_active}")

        current = control.clock()
        for tick in range(1, 11):
            control.step_to(current + tick)
            continued = sample(control, reopened_tick + tick)
            if continued[1:] != by_tick[reopened_tick + tick][1:]:
                raise SystemExit(
                    f"Pumping after reopen differs from Java at tick {reopened_tick + tick}: {continued}")


def verify_bottomless(args, world, fluid, blocks, expected):
    with fixture_world(args, world, STRUCTURE) as control:
        control.command("/place template create:gametest/fluids/hose_pulley_transfer 3 96 -12 none none 1 0 strict")
        control.command("/fill 8 98 -10 13 100 -8 minecraft:air")
        x1, z1 = 10, -59
        if blocks == 10000:
            x2, z2 = 109, 40
        else:
            x2, z2 = 108, 41
        left_wall, right_wall = x1 - 1, x2 + 1
        south_wall = z2 + 1
        control.commands((
            f"/forceload add {x1} {z1} {x2} {z2}",
            f"/fill {x1} 97 {z1} {x2} 97 {z2} minecraft:stone",
            f"/fill {x1} 99 {z1} {x2} 99 {z2} minecraft:stone",
            f"/fill {x1} 98 {z1} {x2} 98 {z2} {fluid}",
            f"/fill {left_wall} 97 {z1 - 1} {left_wall} 99 {south_wall} minecraft:stone",
            f"/fill {right_wall} 97 -60 {right_wall} 99 41 minecraft:stone",
            f"/fill {x1} 97 {z1 - 1} {x2} 99 {z1 - 1} minecraft:stone",
            f"/fill {x1} 97 {south_wall} {x2} 99 {south_wall} minecraft:stone",
            "/setblock 10 102 -7 minecraft:lever[face=wall,facing=south,powered=false]",
        ))
        start = control.clock()
        for tick in range(1, 21):
            control.step_to(start + tick)
        data = control.command("/data get block 11 102 -9")
        if "HoseInfinite" not in data:
            raise SystemExit(f"The pump never validated the {fluid} source body: {data}")
        observed = int(value(data, "HoseInfinite"))
        if observed != expected:
            raise SystemExit(
                f"Java default bottomless threshold mismatch for {fluid} with {blocks} source blocks: "
                f"HoseInfinite={observed}, expected {expected}; {data}")


def verify_movement(args):
    def offset(control):
        return value(control.command("/data get block 11 102 -9"), "Value")

    def step(control, start, count):
        for tick in range(1, count + 1):
            control.step_to(start + tick)

    with fixture_world(args, "Hose-pulley-movement", STRUCTURE) as control:
        control.command("/place template create:gametest/fluids/hose_pulley_transfer 3 96 -12 none none 1 0 strict")
        control.command("/setblock 10 102 -7 minecraft:lever[face=wall,facing=south,powered=true]")
        control.call("wait", 3)
        initial = offset(control)
        control.command("/fill 11 90 -9 11 101 -9 minecraft:air")
        control.command("/setblock 12 102 -9 create:creative_motor[facing=west]{ScrollValue:-128}")
        start = control.clock()
        step(control, start, 16)
        lowered = offset(control)
        if lowered <= initial:
            raise SystemExit(
                f"Powered Hose Pulley did not lower: {initial} -> {lowered}; "
                f"pulley={control.command('/data get block 11 102 -9')}; "
                f"motor={control.command('/data get block 12 102 -9')}")
        control.command("/save-all")
        control.restart()
        lowered_reopened = offset(control)
        if lowered_reopened < lowered:
            raise SystemExit(
                f"Lowered active Hose Pulley did not retain its position: {lowered} -> {lowered_reopened}")

        control.command("/setblock 12 102 -9 create:creative_motor[facing=west]{ScrollValue:128}")
        start = control.clock()
        step(control, start, 8)
        raised = offset(control)
        if not initial < raised < lowered_reopened:
            raise SystemExit(f"Reversed powered Hose Pulley did not raise: {lowered_reopened} -> {raised}")
        control.command("/save-all")
        control.restart()
        raised_reopened = offset(control)
        if not initial < raised_reopened < lowered_reopened:
            raise SystemExit(
                f"Raised active Hose Pulley did not retain its position: {lowered_reopened} -> {raised_reopened}")


def verify_multiplayer(args):
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(
            args, "Hose-pulley-lan", STRUCTURE))
        host.command("/place template create:gametest/fluids/hose_pulley_transfer 3 96 -12 none none 1 0 strict")
        host.command("/setblock 10 102 -7 minecraft:lever[face=wall,facing=south,powered=true]")
        host.call("wait", 2)
        port = host.call("lan", "open", 0, "commands", "force")["port"]
        directory = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="hose-pulley-lan-")))
        guest = stack.enter_context(multiplayer.joined_client(
            args, directory, f"127.0.0.1:{port}", "HosePulleyGuest", scenario="hose-pulley"))
        multiplayer.until("the Hose Pulley guest to join", lambda: any(
            player["name"] == "HosePulleyGuest" and player["placed"]
            for player in host.call("lan", "status")["guests"]))
        host.command("/tp HosePulleyGuest 10.5 102 -5.5")
        multiplayer.until("the guest to see the lever", lambda:
                          guest.call("block", 10, 102, -7)["state"].endswith("powered=true]"))
        guest.call("look-at", 10.5, 102.5, -7.5)
        interaction = guest.call("interact", 10, 102, -7, "up")
        if interaction.get("changed") is not True:
            raise SystemExit(f"Guest could not operate the Hose Pulley control: {interaction}")
        multiplayer.until("the host to receive the guest's lever action", lambda:
                          host.call("block", 10, 102, -7)["state"].endswith("powered=false]"))
        multiplayer.until("the guest to converge on the lever state", lambda:
                          guest.call("block", 10, 102, -7)["state"].endswith("powered=false]"))
        start = host.clock()
        for tick in range(1, 4):
            host.step_to(start + tick)
        pump = host.command("/data get block 9 102 -9")
        if value(pump, "Speed") == 0:
            raise SystemExit(f"Guest lever action replicated, but the host pump stayed idle: {pump}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--ticks", type=int)
    args = parser.parse_args()

    with (ROOT / "fixtures/hose_pulley_transfer-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)[:args.ticks]
    if args.ticks is None:
        verify_finite_reference(expected)
    actual = []
    with fixture_world(args, "Hose-pulley", STRUCTURE) as control:
        control.command("/place template create:gametest/fluids/hose_pulley_transfer 3 96 -12 none none 1 0 strict")
        control.command("/setblock 10 102 -7 minecraft:lever[face=wall,facing=south,powered=false]")
        control.call("wait", 3)
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            control.call("wait", 1)
            state = sample(control, tick)
            actual.append(state)
    output = ROOT / ".local/hose_pulley_transfer-horizon.csv"
    with output.open("w") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(left[0], {key: (a, b) for key, a, b in zip(header, left, right, strict=True)
                              if a != b})
                   for left, right in zip(expected, actual, strict=True) if left != right]
    if differences:
        raise SystemExit(f"Hose Pulley transfer differs on {len(differences)} ticks. "
                         f"First differences (Java, Horizon): {differences[:8]}. See {output}")
    if args.ticks is not None:
        print(f"Original Hose Pulley transfer matched all {len(expected)} requested Java samples.")
        return
    verify_lifecycle(args, expected)
    verify_bottomless(args, "Hose-water-9999", "minecraft:water", 9999, 0)
    verify_bottomless(args, "Hose-water-10000", "minecraft:water", 10000, 1)
    verify_bottomless(args, "Hose-lava-10000", "minecraft:lava", 10000, 1)
    verify_movement(args)
    verify_multiplayer(args)
    print(f"Original finite 27-source Hose Pulley transfer matched all {len(expected)} Java ticks; "
          "idle/active saves, the 9,999/10,000-block water threshold, default lava eligibility, "
          "powered lowering/raising, and LAN guest control with host/guest convergence passed.")


if __name__ == "__main__":
    main()
