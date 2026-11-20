#!/usr/bin/env python3
"""Replay Java's mechanical piston push and retraction of gearbox payloads."""

import argparse
from contextlib import ExitStack
import hashlib
from importlib import import_module
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
piston_fixture = import_module("test-mechanical-piston-sticker")
PISTON = piston_fixture.PISTON
TEMPLATE = piston_fixture.TEMPLATE
PIN = "ac0c444d9828da3453ae8cc65338e8de063286fb"
CASES = ("x", "y", "z", "regular", "stone")
REFERENCE = ROOT / "fixtures/gearbox-mechanical-piston-java.jsonl"
METADATA = ROOT / "fixtures/gearbox-mechanical-piston-java.metadata.json"
PATCH = ROOT / "tools/java-gearbox-mechanical-piston-trace.patch"
CELLS = range(-2, 5)


def payload_block(case):
    if case == "stone":
        return "minecraft:stone"
    axis = "y" if case == "regular" else case
    return f"create:gearbox[axis={axis}]"


def reference():
    metadata = json.loads(METADATA.read_text())
    assert metadata["revision"] == PIN, metadata
    assert metadata["patch_sha256"] == hashlib.sha256(PATCH.read_bytes()).hexdigest(), metadata
    template = ROOT / ".local/fixtures/data/create/structure" / TEMPLATE
    assert metadata["template_sha256"] == hashlib.sha256(template.read_bytes()).hexdigest(), template
    cases = {case: [] for case in CASES}
    for line in REFERENCE.read_text().splitlines():
        row = json.loads(line)
        cases[row["case"]].append(row)
    for case, rows in cases.items():
        assert [row["tick"] for row in rows] == list(range(24)), case
        block = payload_block(case)
        assert any(row["offset"] > 0 and block in row["payload"] for row in rows[:10]), case
        assert rows[10]["cells"][4] == block, (case, rows[10])
        assert rows[-1]["state"] == "retracted" and rows[-1]["offset"] == 0, (case, rows[-1])
        assert rows[-1]["cells"][3 if case == "stone" else 4] == block, (case, rows[-1])
        retracting = [row for row in rows[10:] if row["state"] == "moving"]
        assert retracting and all((block in row["payload"]) == (case == "stone")
                                 for row in retracting), (case, retracting)
    return cases


def setup(host, case):
    host.command("/gamerule random_tick_speed 0")
    while (tick := host.clock()) % 20 != 2:
        host.step_to(tick + 1)
    commands = (
        "/place template create:gametest/contraptions/ploughing 25 96 -12",
        "/setblock 28 98 -10 minecraft:lever[face=floor,facing=west,powered=false]",
        f"/setblock 28 98 -11 {payload_block(case)}",
        *(f"/setblock {27 + distance} 98 -11 minecraft:air" for distance in range(2, 5)),
    )
    replies = host.commands(commands)
    assert replies[0].startswith("Loaded template"), replies
    assert all(reply.startswith(("Changed the block", "Could not set the block"))
               for reply in replies[1:]), replies
    if case == "regular":
        axis = "axis_along_first=true" in host.call("block", *PISTON)["state"]
        host.command(f"/setblock 27 98 -11 create:mechanical_piston[facing=east,axis_along_first={str(axis).lower()}]")
    host.command("/data merge block 27 98 -11 {ScrollValue:0}")
    assert block_at(host, 1) == payload_block(case), case
    for _ in range(2):
        host.step_to(host.clock() + 1)


def block_at(control, distance):
    cell = control.call("block", *piston_fixture.pos(distance))
    if cell["block"] == "create:gearbox":
        return cell["state"]
    return cell["block"]


def cells_at(control):
    return [block_at(control, distance) for distance in CELLS]


def piston_state(control):
    state = control.call("block", *PISTON).get("state", "")
    match = re.search(r"\bstate=(\w+)", state)
    return match[1] if match else None


def read_state(control):
    position = piston_fixture.xyz(PISTON)
    tag = control.command(f"/data get block {position}")
    state = piston_state(control)
    payload = []
    if state == "moving":
        blocks = control.command(f"/data get block {position} Blocks")
        payload = piston_fixture.ids_from_payload(blocks)
        if "create:gearbox" in payload:
            axis = re.search(r'\baxis:\s*"([xyz])"', blocks)
            assert axis is not None, blocks
            payload[payload.index("create:gearbox")] = f"create:gearbox[axis={axis[1]}]"
    return {
        "state": state,
        "offset": piston_fixture.field(tag, "Offset"),
        "speed": piston_fixture.field(tag, "Speed"),
        "cells": cells_at(control),
        "payload": sorted(payload),
    }


def replay(args, case, expected, results, mismatches):
    role = "Lan" if args.lan else "Solo"
    label = f"GearboxMechanicalPiston{role}{case.capitalize()}"
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, label, TEMPLATE, pack=args.pack))
        guest = None
        if args.lan:
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-gearbox-piston-")))
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            name = "GearboxPiston"
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, scenario=label.lower(), pack=args.pack,
            ))
            multiplayer.until("guest to join", lambda: any(
                player["name"] == name and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.command(f"/tp {name} 28.5 100 -8.5")
            multiplayer.until("guest to load the piston area", lambda: guest.call("block", *PISTON).get("loaded"))
        setup(host, case)
        start = host.clock()
        for want in expected:
            tick = want["tick"]
            if tick:
                host.step_to(start + tick)
            if tick == 10:
                host.command("/data merge block 29 97 -10 {ScrollValue:-64}")
            actual = read_state(host)
            results.append({"case": case, "tick": tick, **actual})
            for field, value in actual.items():
                if value != want[field]:
                    mismatches.append({"case": case, "tick": tick, "field": field,
                                       "horizon": value, "java": want[field]})
            if guest is not None:
                def replicated():
                    cells = cells_at(guest)
                    state = piston_state(guest)
                    return cells == actual["cells"] and state == actual["state"]

                try:
                    multiplayer.until(f"{case} piston and gearbox to replicate on tick {tick}",
                                      replicated, seconds=5)
                except RuntimeError as error:
                    mismatches.append({"case": case, "tick": tick, "field": "guest_replication",
                                       "error": str(error)})
                results[-1]["guest"] = {"cells": cells_at(guest), "state": piston_state(guest)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--case", action="append", choices=CASES)
    args = parser.parse_args()

    refs = reference()
    results, mismatches = [], []
    output_root = ROOT / ".local"
    output_root.mkdir(exist_ok=True)
    artifact = output_root / f"gearbox-mechanical-piston-{'lan' if args.lan else 'solo'}.json"
    try:
        for case in args.case or CASES:
            replay(args, case, refs[case], results, mismatches)
    finally:
        artifact.write_text(json.dumps({"rows": results, "mismatches": mismatches}, indent=2) + "\n")
    assert not mismatches, f"{len(mismatches)} mismatches. First: {mismatches[0]}. See {artifact}."
    print(f"Matched {len(results)} Java mechanical piston tick samples ({'LAN' if args.lan else 'solo'}).")


if __name__ == "__main__":
    main()
