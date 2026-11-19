#!/usr/bin/env python3
"""Compare actual Horizon player motion with the Java standing collision oracle."""

import argparse
from math import isclose
from pathlib import Path
import runpy

solve = runpy.run_path(Path(__file__).with_name("trace-java-elevator-standing.py"))["solve"]


def read_samples(log):
    trace = {}
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if "CREATE_STANDING_CONTACT " in line:
            tick, world, deck, motion, *_ = line.split("CREATE_STANDING_CONTACT ", 1)[1].split(",")
            trace.setdefault(int(tick), {})["contact"] = (int(world), float(deck), float(motion))
        elif "CREATE_STANDING_RESULT " in line:
            tick, _, _, _, _, deck, feet, velocity, grounded, mounted, *_ = (
                line.split("CREATE_STANDING_RESULT ", 1)[1].split(",")
            )
            trace.setdefault(int(tick), {})["result"] = (
                float(deck), float(feet), float(velocity), grounded == "true", mounted == "true"
            )
    return trace


def verify(log):
    previous = None
    checked = upward = downward = 0
    for tick, sample in read_samples(log).items():
        contact = sample.get("contact")
        result = sample.get("result")
        if contact is None or result is None:
            if result and previous and previous[0] + 1 == tick and result[3] and result[0] != previous[1]:
                raise ValueError(f"{log.name} tick {tick}: the moving deck bypassed the contact solver.")
            previous = None
            continue
        world, deck, motion = contact
        actual_deck, actual_feet, actual_velocity, grounded, mounted = result
        if not (grounded and not mounted and isclose(actual_deck, deck, rel_tol=0, abs_tol=1e-12)):
            raise ValueError(f"{log.name} tick {tick}: incorrect standing state {result}.")
        if previous and previous[0] + 1 == tick:
            _, prior_deck, prior_feet, prior_velocity = previous
            prediction = solve((prior_deck - 1, prior_feet, prior_velocity), deck - 1, deck - 1 - motion)
            expected_feet, expected_velocity = prediction[2:4]
            if not all(isclose(a, b, rel_tol=0, abs_tol=2e-10)
                       for a, b in ((actual_feet, expected_feet), (actual_velocity, expected_velocity))):
                raise ValueError(
                    f"{log.name} client tick {tick}, world tick {world}: "
                    f"Horizon {actual_feet, actual_velocity}, Java {expected_feet, expected_velocity}."
                )
            checked += 1
            upward += motion > 0
            downward += motion < 0
            previous = (tick, deck, expected_feet, expected_velocity)
        else:
            previous = (tick, deck, actual_feet, actual_velocity)
    if not (upward and downward):
        raise ValueError(f"{log.name} needs continuous ascent and descent contact samples.")
    print(f"{log.name} matched Java at {checked} contact samples ({upward} rising, {downward} falling).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs=2, type=Path, metavar="CLIENT_LOG")
    for log in parser.parse_args().logs:
        verify(log)
