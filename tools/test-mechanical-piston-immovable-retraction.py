#!/usr/bin/env python3
"""Replay Java's sticky piston retracting away from an immovable pull target."""

import argparse
import hashlib
from importlib import import_module
import json
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

piston = import_module("test-mechanical-piston-sticker")
NAME = "mechanical-piston-immovable-retraction"
PIN = "ac0c444d9828da3453ae8cc65338e8de063286fb"
BASE = (8, 104, 10)
MOTOR = (8, 104, 9)


def read_state(control, tick):
    data = control.command(f"/data get block {piston.xyz(BASE)}")
    state = control.call("block", *BASE)["state"]
    return {
        "tick": tick,
        "offset": piston.field(data, "Offset"),
        "speed": piston.field(data, "Speed"),
        "state": re.search(r"\bstate=(\w+)", state)[1],
        "cells": [control.call("block", BASE[0] + d, BASE[1], BASE[2])["block"]
                  for d in range(-1, 4)],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    reference = ROOT / f"fixtures/{NAME}-java.jsonl"
    metadata = json.loads((ROOT / f"fixtures/{NAME}-java.metadata.json").read_text())
    assert metadata["revision"] == PIN
    assert metadata["patch_sha256"] == hashlib.sha256((ROOT / f"tools/java-{NAME}.patch").read_bytes()).hexdigest()
    assert metadata["trace_sha256"] == hashlib.sha256(reference.read_bytes()).hexdigest()
    expected = [json.loads(line) for line in reference.read_text().splitlines()]
    assert [row["tick"] for row in expected] == list(range(24))
    assert expected[10]["state"] == "extended" and expected[-1]["state"] == "retracted"
    observed = []
    artifact = ROOT / f".local/mechanical-piston/{NAME}-horizon.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    try:
        with fixture_world(args, "PistonImmovableRetraction", pack=args.pack) as control:
            control.commands((
                "/setblock 8 104 10 create:sticky_mechanical_piston[facing=east,axis_along_first=false]",
                "/setblock 7 104 10 create:piston_extension_pole[facing=east]",
                "/setblock 8 104 9 create:creative_motor[facing=south]",
                "/data merge block 8 104 9 {ScrollValue:-64}",
            ))
            for _ in range(2):
                control.step_to(control.clock() + 1)
            start = control.clock()
            for tick in range(24):
                if tick:
                    control.step_to(start + tick)
                if tick == 10:
                    assert read_state(control, tick)["state"] == "extended", "rig did not extend"
                    control.commands((
                        "/setblock 10 104 10 minecraft:bedrock",
                        "/data merge block 8 104 9 {ScrollValue:64}",
                    ))
                observed.append(read_state(control, tick))
    finally:
        artifact.write_text(json.dumps(observed, indent=2) + "\n")
    differences = [(want, got) for want, got in zip(expected, observed, strict=True) if want != got]
    assert not differences, f"{len(differences)} mismatches; first={differences[0]}; see {artifact}"
    print("Matched 24 Java samples: sticky apparatus retracted and retained immovable bedrock.")


if __name__ == "__main__":
    main()
