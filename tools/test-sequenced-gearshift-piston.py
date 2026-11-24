#!/usr/bin/env python3
"""Check sequencer distance limits on a mechanical piston payload."""
import argparse
from math import isclose
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, install_pack, last_command_message, run_command_harness


def command(value, record=True):
    return {"op": "cmd", "cmd": value, "record": record}


def number(nbt, key):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)f?", nbt)
    if not match:
        raise RuntimeError(f"Missing {key} from block entity: {nbt}")
    return float(match[1])


def run(args):
    setup = (
        "/fill 4 100 -16 14 100 -5 minecraft:smooth_stone",
        "/fill 4 101 -16 14 104 -5 minecraft:air",
        "/setblock 7 101 -10 create:creative_motor[facing=east]",
        "/setblock 8 101 -10 create:sequenced_gearshift[axis=x,state=0,vertical=false]",
        "/setblock 9 101 -10 create:shaft[axis=x]",
        "/setblock 10 101 -10 create:mechanical_piston[facing=north,axis_along_first=true]",
        "/setblock 10 101 -9 create:piston_extension_pole[facing=north]",
        '/data merge block 8 101 -10 {Instructions:[{Type:"TURN_DISTANCE",Value:1,Modifier:"BACK"},{Type:"END",Value:1,Modifier:"FORWARD"}]}',
        "/setblock 8 102 -10 minecraft:redstone_block",
    )
    with TemporaryDirectory(prefix="hc-sequenced-piston-") as tmp:
        game = Path(tmp) / "game"
        install_pack(game)
        records = run_command_harness(args, game, "SequencedPistonDistance", (
            *(command(value, False) for value in setup),
            {"op": "tick", "n": 20},
            command("/data get block 10 101 -10"),
            command("/data get block 8 101 -10"),
            command("/execute if entity @e[type=minecraft:marker,tag=create_piston_payload,limit=1]"),
            {"op": "tick", "n": 20},
            command("/data get block 10 101 -10"),
            command("/data get block 8 101 -10"),
            command("/execute if entity @e[type=minecraft:marker,tag=create_piston_payload,limit=1]"),
        ))

    active_piston, active_sequencer, active_payload = map(
        last_command_message, records[-6:-3]
    )
    offset = number(active_piston, "Offset")
    remaining = number(active_piston, "SequencedOffsetLimit")
    if not isclose(offset + remaining, 1.0, abs_tol=1e-6) or not (0.0 < offset < 1.0):
        raise RuntimeError(
            f"Piston offset plus remaining sequenced distance should stay at 1 block: {active_piston}"
        )
    if "InstructionIndex: 0" not in active_sequencer or not active_payload.startswith("Test passed"):
        raise RuntimeError(f"Piston should still be moving during the active instruction: {records[-6:-3]}")

    final_piston, final_sequencer, final_payload = map(
        last_command_message, records[-3:]
    )
    if not isclose(number(final_piston, "Offset"), 1.0, abs_tol=1e-6):
        raise RuntimeError(f"Piston did not finish at the requested 1-block distance: {final_piston}")
    if "InstructionIndex: -1" not in final_sequencer or not final_payload.startswith("Test failed"):
        raise RuntimeError(f"Piston or sequencer payload did not settle after completion: {records[-3:]}")
    print("Sequenced piston stayed within the 1-block distance and settled at its endpoint.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
