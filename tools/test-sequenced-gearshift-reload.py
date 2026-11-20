#!/usr/bin/env python3
"""Check sequencer idle and active saves with deterministic harness clocks."""
import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
from math import isclose
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, install_pack, last_command_message, run_command_harness

spec = spec_from_file_location("sequencer_fixture", ROOT / "tools/test-sequenced-gearshift-editor.py")
sequencer = module_from_spec(spec)
spec.loader.exec_module(sequencer)


def command(value, record=True):
    return {"op": "cmd", "cmd": value, "record": record}


def value(nbt, key, *, default=None):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", nbt)
    if not match:
        if default is not None:
            return float(default)
        raise RuntimeError(f"Missing {key} from sequencer data: {nbt}")
    return float(match[1])


def boolean(nbt, key):
    match = re.search(rf"\b{key}: (true|false|[01]b)\b", nbt)
    if not match:
        # Java defaults PrevPowered to false; the native adapter may omit it
        # until the first authoritative sequencer tick writes the field.
        return False
    return match[1] in ("true", "1b")


def reference_rows():
    with (ROOT / "fixtures/sequenced-gearshift-editor-java.csv").open() as source:
        return {int(row["tick"]): row for row in csv.DictReader(source)}


def sample_ops(state):
    pos = sequencer.coords(sequencer.SEQUENCER)
    out = sequencer.coords(sequencer.OUTPUT)
    return [command(query) for query in (
        "/time query gametime",
        f"/data get block {pos}",
        f"/data get block {out}",
        f"/execute if block {pos} create:sequenced_gearshift[state={state}]",
    )]


def check_sample(records, expected, tick, *, expected_clock=None):
    messages = [last_command_message(record) for record in records]
    clock = int(messages[0].split()[-2])
    if expected_clock is not None and clock != expected_clock:
        raise RuntimeError(f"Java tick {tick}: harness clock {clock}, expected {expected_clock}.")
    nbt, output, state = messages[1:]
    if not state.startswith("Test passed"):
        raise RuntimeError(f"Java tick {tick}: block state differs from state={expected['state']}: {state}")
    fields = (("InstructionIndex", "instruction"), ("InstructionDuration", "duration"),
              ("Timer", "timer"), ("InstructionProgress", "progress"), ("Speed", "input_rpm"))
    for key, column in fields:
        actual = value(nbt, key, default=0 if key in ("Timer", "InstructionProgress", "Speed") else None)
        if not isclose(actual, float(expected[column]), abs_tol=0.00001):
            raise RuntimeError(f"Java tick {tick} mismatch for {key}: {nbt}")
    if boolean(nbt, "PrevPowered") != (expected["powered"] == "true"):
        raise RuntimeError(f"Java tick {tick} mismatch for PrevPowered: {nbt}")
    if not isclose(sequencer.sample(output, "Speed"), float(expected["output_rpm"]), abs_tol=0.00001):
        raise RuntimeError(f"Java tick {tick} mismatch for output RPM: {output}")
    return clock, nbt


def sample_diagnostic(records):
    messages = [last_command_message(record) for record in records]
    return {
        "clock": messages[0].split()[-2],
        "sequencer": messages[1],
        "output": messages[2],
        "state_check": messages[3],
    }


def setup_ops(program=None, *, idle=False):
    operations = []
    operations.extend(command(cmd, False) for cmd in (
        "/fill 4 100 -16 14 100 -5 minecraft:smooth_stone",
        "/fill 4 101 -16 14 104 -5 minecraft:air",
        "/setblock 7 101 -10 create:creative_motor[facing=east]",
        "/setblock 8 101 -10 create:sequenced_gearshift[axis=x,state=0,vertical=false]",
        "/setblock 9 101 -10 create:shaft[axis=x]",
        "/tp @s 8.5 101.0 -6.5",
        "/gamemode survival",
    ))
    if program is not None:
        operations.append(command(
            f"/data merge block {sequencer.coords(sequencer.SEQUENCER)} {{Instructions:{program}}}", False,
        ))
    if idle:
        operations.extend((command("/save-all"),))
    return operations


def run_harness(args, game, world, operations):
    return run_command_harness(args, game, world, operations)


def check_idle(args, program):
    with TemporaryDirectory(prefix="hc-seq-idle-") as tmp:
        game = Path(tmp) / "game"
        install_pack(game, args.pack)
        world = "SequencerIdleReload"
        run_harness(args, game, world, setup_ops(program, idle=True))
        records = run_harness(args, game, world, (
            command(f"/data get block {sequencer.coords(sequencer.SEQUENCER)}"),
        ))
        nbt = last_command_message(records[0])
        if not program_matches_nbt(nbt, program):
            raise RuntimeError(f"Idle program changed across command-harness reopen: {nbt}")
        if (value(nbt, "InstructionIndex") != -1 or value(nbt, "InstructionDuration") != -1
                or value(nbt, "Timer", default=0) != 0
                or value(nbt, "InstructionProgress", default=0) != 0):
            raise RuntimeError(f"Sequencer was not idle after command-harness reopen: {nbt}")


def program_matches_nbt(nbt, expected):
    match = re.search(r"\bInstructions\s*:\s*\[", nbt)
    if not match:
        return False
    start = match.end() - 1
    depth, quoted, escaped, end = 0, False, False, None
    for index in range(start, len(nbt)):
        char = nbt[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end is None:
        return False

    def normalize(value):
        entries = re.findall(r"\{([^{}]+)\}", value)
        return [sorted(part.replace(" ", "") for part in row.split(",")) for row in entries]

    return normalize(nbt[start:end]) == normalize(expected)


def active_prefix(program):
    operations = setup_ops()
    operations.extend(sample_ops(0))  # Java tick 0 observation.
    operations.append(command("/data merge block 7 101 -10 {ScrollValue:32}", False))
    operations.extend(({"op": "tick", "n": 1}, *sample_ops(0)))  # tick 1
    operations.extend(({"op": "tick", "n": 1}, command(
        f"/data merge block {sequencer.coords(sequencer.SEQUENCER)} {{Instructions:{program}}}", False,
    ), *sample_ops(0)))  # Java config then tick 2 observation.
    operations.extend(({"op": "tick", "n": 1}, *sample_ops(0)))  # tick 3
    operations.extend(({"op": "tick", "n": 1}, *sample_ops(0)))  # tick 4
    operations.append(command("/setblock 8 102 -10 minecraft:redstone_block", False))
    operations.extend(({"op": "tick", "n": 1}, *sample_ops(1)))  # tick 5
    # Java's GameTest sets air immediately after recording tick 5.
    operations.extend((
        command("/setblock 8 102 -10 minecraft:air", False),
        command(f"/data get block {sequencer.coords(sequencer.SEQUENCER)}"),
        command("/save-all", False),
    ))
    return operations


def check_active(args, program, rows):
    with TemporaryDirectory(prefix="hc-seq-active-") as tmp:
        game = Path(tmp) / "game"
        install_pack(game, args.pack)
        world = "SequencerActiveReload"
        records = run_harness(args, game, world, active_prefix(program))
        # First operation's gametime query is the tick-0 sample; thereafter
        # each row contributes four command records. setup commands are quiet.
        base_clock, _ = check_sample(records[:4], rows[0], 0)
        for tick in range(1, 6):
            begin = tick * 4
            check_sample(records[begin:begin + 4], rows[tick], tick,
                         expected_clock=base_clock + tick)
        saved_clock = base_clock + 5
        pre_save_nbt = last_command_message(records[-1])
        if not program_matches_nbt(pre_save_nbt, program):
            raise RuntimeError(f"Active Instructions differ before save: {pre_save_nbt}")

        reopened = run_harness(args, game, world, (
            *sample_ops(1),
            {"op": "tick", "n": 1},
            *sample_ops(1),
            {"op": "tick", "n": 1},
            *sample_ops(1),
        ))
        loaded_clock, loaded_nbt = check_sample(reopened[:4], rows[5], 5,
                                                expected_clock=saved_clock)
        if not program_matches_nbt(loaded_nbt, program):
            raise RuntimeError(
                "Active instruction list differs after reopen. "
                f"Pre-save NBT: {pre_save_nbt}; loaded NBT: {loaded_nbt}"
            )
        try:
            check_sample(reopened[4:8], rows[6], 6, expected_clock=loaded_clock + 1)
        except RuntimeError as error:
            raise RuntimeError(
                f"{error}; explicit tick-7 diagnostic: {sample_diagnostic(reopened[8:12])}"
            ) from error
        check_sample(reopened[8:12], rows[7], 7, expected_clock=loaded_clock + 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    program = sequencer.original_program()
    rows = reference_rows()
    check_idle(args, program)
    check_active(args, program, rows)
    print("Idle program and active tick-5 state survived deterministic harness reopen; tick 6 matched Java.")


if __name__ == "__main__":
    main()
