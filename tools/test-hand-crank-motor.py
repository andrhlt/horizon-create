#!/usr/bin/env python3
"""Replay the Java hand crank's interaction with a faster creative motor."""

import argparse
import csv
import importlib.util
from math import isclose
from pathlib import Path

from fixture_world import ROOT, fixture_world

spec = importlib.util.spec_from_file_location("crank", Path(__file__).with_name("test-hand-crank.py"))
crank = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crank)


def verify(args):
    with (ROOT / "fixtures/hand-crank-motor-java.csv").open() as reference:
        expected = list(csv.DictReader(reference))
    env = {"CREATE_HAND_CRANK_TRACE": ",".join(map(str, crank.CRANK))}
    with fixture_world(args, "HandCrankMotor", env=env, render=True) as control:
        crank.setup(control)
        control.commands((
            "/setblock 6 101 -13 create:creative_motor[facing=south]",
            "/data merge block 6 101 -13 {ScrollValue:64}",
        ))
        control.call("lan", "open", "0", "commands", "force")
        start = control.clock()
        log = control.socket.parent / "ctl.log"
        for row in expected[1:]:
            tick = int(row["tick"])
            control.step_to(start + tick)
            mounted = control.call("block", *crank.CRANK)["state"]
            removed = mounted == "minecraft:air"
            if removed != (row["removed"] == "true"):
                raise RuntimeError(f"Tick {tick}: Java removed={row['removed']}, Horizon {mounted}.")
            if removed:
                tag = control.command(f"/data get block {crank.REAR}")
                actual = {
                    "rear_rpm": crank.tag_value(tag, "Speed"),
                    "capacity": crank.tag_value(tag, "Capacity"),
                }
            else:
                keys = ("in_use", "backwards", "crank_rpm", "rear_rpm", "front_rpm",
                        "stressometer_rpm", "capacity", "angle", "angular_velocity", "exhaustion")
                actual = dict(zip(keys, crank.tick_sample(log, control, start + tick), strict=True))
            for key, value in actual.items():
                matched = row[key] == value if isinstance(value, str) else isclose(
                    float(row[key]), value, abs_tol=0.00002, rel_tol=0.0,
                )
                if not matched:
                    raise RuntimeError(f"Tick {tick}: {key} Java {row[key]}, Horizon {value}.")
            if tick == 16:
                control.call("key", "shift", "down")
                control.call("wait", 3)
            if tick in (4, 9, 16):
                try:
                    control.call("interact", *crank.CRANK)
                finally:
                    if tick == 16:
                        control.call("key", "shift", "up")
    print("Hand crank and faster motor matched Java for 24 consecutive simulated ticks.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
