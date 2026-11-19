#!/usr/bin/env python3
"""Compare mixed-cog chain drive RPM and survival across a redstone transition."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

CASES = ((6, 64), (12, 96))
REFERENCE = ROOT / "fixtures/adjustable-chain-speed-limit-java.csv"
HEADER = (
    "tick", "input_rpm", "shift_present", "modifier",
    "large_cog_rpm", "small_cog_rpm", "shift_rpm", "output_rpm",
)


def setup(control):
    control.commands((
        "/fill 4 100 -12 14 104 -8 minecraft:air",
        *(command for x, rpm in CASES for command in (
            f"/setblock {x} 102 -10 create:adjustable_chain_gearshift[axis=y,part=start,axis_along_first=true]",
            f"/setblock {x + 1} 102 -10 create:encased_chain_drive[axis=y,part=end,axis_along_first=true]",
            f"/setblock {x} 101 -10 create:cogwheel[axis=y]",
            f"/setblock {x - 1} 101 -11 create:large_cogwheel[axis=y]",
            f"/setblock {x + 1} 101 -10 create:shaft[axis=y]",
            f"/setblock {x - 1} 100 -11 create:creative_motor[facing=up]",
            f"/data merge block {x - 1} 100 -11 {{ScrollValue:{rpm}}}",
        )),
    ))


def run_transition(control, tick):
    for x, _ in CASES:
        if tick == 3:
            control.commands((
                f"/setblock {x + 1} 103 -10 create:creative_motor[facing=down]",
                f"/data merge block {x + 1} 103 -10 {{ScrollValue:32}}",
            ))
        elif tick == 6:
            control.command(f"/setblock {x} 102 -9 minecraft:redstone_block")
        elif tick == 11:
            control.command(f"/setblock {x - 1} 100 -11 minecraft:air")
        elif tick == 15:
            control.command(f"/setblock {x} 102 -9 minecraft:air")


def sample(control, tick, x, input_rpm):
    present = "create:adjustable_chain_gearshift" in control.call("block", x, 102, -10)["state"]
    positions = [
        (x - 1, 101, -11),
        (x, 101, -10),
        (x, 102, -10) if present else None,
        (x + 1, 101, -10),
    ]
    values = iter(control.commands(f"/data get block {a} {b} {c}" for a, b, c in filter(None, positions)))
    large, small, shift, output = (next(values) if pos is not None else "" for pos in positions)
    signal = re.search(r"\bSignal: (\d+)\b", shift)
    if present and signal is None:
        raise RuntimeError(f"Missing Signal: {shift}")
    strength = int(signal[1]) if signal else 0
    modifier = (1 + (strength + 1) / 16 if strength else 1.0) if present else 0.0

    def speed(value):
        if not value:
            return 0.0
        match = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)f\b", value)
        if match is None:
            raise RuntimeError(f"Missing Speed: {value}")
        return float(match[1])

    return (tick, input_rpm, str(present).lower(), modifier, *map(speed, (large, small, shift, output)))


def verify(args):
    with REFERENCE.open() as source:
        header, *rows = csv.reader(source)
    if tuple(header) != HEADER:
        raise RuntimeError(f"Unexpected Java trace header {header}")
    # Row zero is sampled in Java after setup and before Horizon publishes its first RPM.
    reference = [
        (int(tick), int(input_rpm), present, *map(float, values))
        for tick, input_rpm, present, *values in rows if int(tick) > 0
    ]
    jobs = [(tick, rpm) for tick in range(1, 20) for _, rpm in CASES]
    if [row[:2] for row in reference] != jobs:
        raise RuntimeError("Expected both motor speeds at every simulated tick")
    actual = []
    with fixture_world(args, "AdjustableChainSpeedLimit", pack=args.pack) as control:
        setup(control)
        start = control.clock()
        for tick in range(1, 20):
            control.step_to(start + tick)
            actual.extend(sample(control, tick, x, rpm) for x, rpm in CASES)
            run_transition(control, tick)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as target:
        writer = csv.writer(target)
        writer.writerow(HEADER)
        writer.writerows(actual)
    mismatches = [(wanted, got) for wanted, got in zip(reference, actual, strict=True) if wanted != got]
    if mismatches:
        raise RuntimeError(f"{len(mismatches)} chain speed mismatches (Java, Horizon): {mismatches[:10]}")
    print(f"Mixed-cog adjustable chain speed limit matched Java for {len(actual)} samples.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/adjustable-chain-speed-limit-horizon.csv")
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
