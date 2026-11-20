#!/usr/bin/env python3
"""Replay pinned Java Vertical Gearbox survival placements."""

import argparse
import hashlib
import json
from math import floor
from pathlib import Path

from fixture_world import ROOT, fixture_world

PATCH = ROOT / "tools/java-vertical-gearbox-matrix-trace.patch"
REFERENCE = ROOT / "fixtures/vertical-gearbox-matrix-java.json"
METADATA = ROOT / "fixtures/vertical-gearbox-matrix-java.metadata.json"
PIN = "ac0c444d9828da3453ae8cc65338e8de063286fb"
GEARBOX = "create:gearbox"
POSITION = (8, 102, -10)
DIRECTIONS = {
    "north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0), "west": (-1, 0, 0),
    "up": (0, 1, 0), "down": (0, -1, 0),
}
AIMS = {
    "north": ((8.5, 101, -12.5), (8.5, 102.5, -9.001)),
    "south": ((8.5, 101, -6.5), (8.5, 102.5, -10.001)),
    "east": ((11.5, 101, -9.5), (7.999, 102.5, -9.5)),
    "west": ((5.5, 101, -9.5), (9.001, 102.5, -9.5)),
    "up": ((10.1, 104, -9.1), (8.875, 101.999, -9.1)),
    "down": ((6.5, 99, -9.5), (8.5, 103.001, -9.5)),
}
TARGETS = {"grass": "short_grass", "water": "water", "fence": "oak_fence"}


def reference():
    meta = json.loads(METADATA.read_text())
    assert meta["revision"] == PIN, meta
    for key, path in (("patch_sha256", PATCH), ("trace_sha256", REFERENCE)):
        assert meta[key] == hashlib.sha256(path.read_bytes()).hexdigest(), meta
    rows = json.loads(REFERENCE.read_text())
    assert len(rows) == len({row["case"] for row in rows}) == 20
    assert {row["face"] for row in rows} == set(DIRECTIONS)
    assert {row["player"] for row in rows} == {"south", "west", "north", "east"}
    return rows


def neighbor(face, sign=1):
    return tuple(value + sign * shift for value, shift in zip(POSITION, DIRECTIONS[face], strict=True))


def coords(pos):
    return " ".join(map(str, pos))


def state(control):
    block = control.call("block", *POSITION)
    observed = {"block": block["block"]}
    if block["block"] == GEARBOX:
        observed["axis"] = block["state"].split("[axis=")[1].rstrip("]")
    return observed


def place(control, case, hits):
    face = case["face"]
    target = case["target"]
    item = case["item"]
    support = neighbor(face, -1)
    clicked = POSITION if target == "grass" else support
    feet, aim = AIMS[face]
    if case["case"] == "axis_conflict":
        feet, aim = (8.9, 101, -12.5), (8.9, 102.5, -9.001)
    if case["case"] == "clicked_x_shaft":
        feet, aim = (9.45, 101, -12.5), (7.999, 102.5, -9.5)
    if target == "grass":
        aim = (8.5, 102.5, -9.5)

    x, y, z = map(floor, feet)
    support_state = "create:shaft[axis=x]" if case["support"] == "shaft_x" else "minecraft:stone"
    commands = [
        "/clear @s",
        "/fill 4 98 -15 13 105 -5 minecraft:air",
        f"/setblock {x} {y - 1} {z} minecraft:stone",
        f"/setblock {coords(support)} {support_state}",
    ]
    if target in TARGETS:
        commands.append(f"/setblock {coords(POSITION)} minecraft:{TARGETS[target]}")
    for entry in case["neighbors"]:
        side, block, axis = entry.split(":")
        nx, ny, nz = neighbor(side)
        if block == "shaft":
            commands.append(f"/setblock {nx} {ny} {nz} create:shaft[axis={axis}]")
        else:
            powered = "true" if block == "powered_clutch" else "false"
            commands.append(f"/setblock {nx} {ny} {nz} create:clutch[axis={axis},powered={powered}]")
            if powered == "true":
                commands.append(f"/setblock {nx} {ny + 1} {nz} minecraft:redstone_block")
    control.commands((
        *commands,
        f"/tp @s {coords(feet)}",
        f"/item replace entity @s hotbar.0 with {item}",
    ))
    control.call("wait", 3)
    control.call("select", item)
    if case["sneaking"]:
        control.call("key", "shift", "down")
    try:
        control.call("look-at", *aim)
        control.call("wait", 3)
        looking = control.call("looking-at")
        hit = looking.get("block")
        yaw = control.call("state")["player"]["yaw"]
        player = ("south", "west", "north", "east")[floor(yaw / 90 + 0.5) % 4]
        hits.append({"case": case["case"], "looking": looking, "yaw": yaw, "player": player})
        assert hit and hit["pos"] == list(clicked) and hit["face"] == face, (case["case"], clicked, face, hit)
        assert player == case["player"], (case["case"], case["player"], player, yaw)
        control.call("mouse", "right", "click")
        control.call("wait", 3)
    finally:
        if case["sneaking"]:
            control.call("key", "shift", "up")

    landed = state(control)
    reading = case | {
        "placed": landed["block"] == GEARBOX,
        "remaining": control.call("inventory")["counts"].get(item, 0),
        "landed": landed,
    }
    if case["remove_support"]:
        control.command(f"/setblock {coords(support)} minecraft:air")
        control.step_to(control.clock() + 1)
        reading["unsupported"] = state(control)
    return reading


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    expected = reference()
    observed, hits = [], []
    output = ROOT / ".local/vertical-gearbox-matrix-horizon.json"
    try:
        with fixture_world(args, "VerticalGearboxMatrix") as control:
            control.command("/gamemode survival")
            for case in expected:
                observed.append(place(control, case, hits))
    finally:
        output.write_text(json.dumps({"rows": observed, "hits": hits}, indent=2) + "\n")
    differences = [(want, got) for want, got in zip(expected, observed, strict=True) if want != got]
    assert not differences, f"{len(differences)} cases differ. First: {differences[0]}. See {output}."
    print(f"Matched all {len(expected)} pinned Java Gearbox placement cases.")


if __name__ == "__main__":
    main()
