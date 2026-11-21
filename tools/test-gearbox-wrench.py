#!/usr/bin/env python3
"""Compare Gearbox wrench rotation, survival recovery and powered transitions."""

import argparse
import hashlib
from importlib import import_module
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

wrench = import_module("test-wrench")
multiplayer = import_module("test-multiplayer")
PIN = "ac0c444d9828da3453ae8cc65338e8de063286fb"
PATCH = ROOT / "tools/java-gearbox-wrench-trace.patch"
REFERENCE = ROOT / "fixtures/gearbox-wrench-java.json"
METADATA = ROOT / "fixtures/gearbox-wrench-java.metadata.json"
POSITION = wrench.POSITION
DIRECTIONS = dict(enumerate(("down", "up", "north", "south", "west", "east"))) | {-1: "none"}
SUPPORTS = (
    (8, 176, 23), (9, 181, 23), (8, 178, 21),
    (8, 178, 25), (6, 178, 23), (10, 178, 23),
)
NETWORK = {
    "gearbox": POSITION,
    "south": (8, 180, 24),
    "east": (9, 180, 23),
    "up": (8, 181, 23),
}


def xyz(pos):
    return " ".join(map(str, pos))


def reference():
    metadata = json.loads(METADATA.read_text())
    assert metadata["revision"] == PIN, metadata
    for key, path in (("patch_sha256", PATCH), ("trace_sha256", REFERENCE)):
        assert metadata[key] == hashlib.sha256(path.read_bytes()).hexdigest(), metadata
    trace = json.loads(REFERENCE.read_text())
    rotations, powered = trace["rotations"], trace["powered"]
    assert len(rotations) == 18 and {(row["initial_axis"], row["face"]) for row in rotations} == {
        (axis, face) for axis in "xyz" for face in wrench.APPROACH
    }
    assert all(row["block_after_pickup"] == "minecraft:air" for row in rotations)
    assert len(powered) == 11
    assert [(row["tick"], row["phase"]) for row in powered] == [
        (0, "end_tick"), (0, "after_use"), (1, "end_tick"), (2, "end_tick"),
        (3, "end_tick"), (4, "end_tick"), (4, "after_use"), (5, "end_tick"),
        (6, "end_tick"), (7, "end_tick"), (8, "end_tick"),
    ]
    assert [(row["axis"], row["input"], row["south_rpm"], row["east_rpm"])
            for row in (powered[0], powered[1], powered[-1])] == [
        ("y", "north", -32, 32), ("z", "none", 0, 0), ("y", "north", -32, 32),
    ]
    return rotations, powered


def equip(control):
    control.commands(("/clear @s", "/item replace entity @s hotbar.0 with create:wrench"))
    control.call("wait", 3)
    control.call("select", "create:wrench")


def use(control, face):
    control.call("interact", *POSITION, face)


def rotation_matrix(control, expected, rows):
    for want in expected:
        face, axis = want["face"], want["initial_axis"]
        control.commands((
            f"/setblock {xyz(POSITION)} create:gearbox[axis={axis}]",
            f"/tp @s {xyz(wrench.APPROACH[face])}",
        ))
        equip(control)
        use(control, face)
        rotated_block = control.call("block", *POSITION)
        ident, properties = wrench.state(rotated_block["state"])
        assert ident == "create:gearbox", (want, rotated_block)
        # The pickup item depends on the post-rotation casing axis. Use a clear approach for pickup.
        control.command(f"/tp @s {xyz(wrench.APPROACH['west'])}")
        wrench.sneak_click(control, tuple(coord + 0.5 for coord in POSITION))
        rows.append({
            "initial_axis": axis,
            "face": face,
            "axis": properties["axis"],
            "block_after_pickup": control.call("block", *POSITION)["block"],
            "inventory": control.call("inventory")["counts"],
        })


def read_power(control, tick, phase):
    _, properties = wrench.state(control.call("block", *POSITION)["state"])
    replies = control.commands(f"/data get block {xyz(pos)}" for pos in NETWORK.values())
    row = {"tick": tick, "phase": phase, "axis": properties["axis"]}
    source = re.search(r"\bShaftInputDirection: (-?\d+)", replies[0])
    assert source is not None, replies[0]
    row["input"] = DIRECTIONS[int(source[1])]
    for name, reply in zip(NETWORK, replies, strict=True):
        rpm = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)", reply)
        assert rpm is not None, (name, reply)
        row[f"{name}_rpm"] = float(rpm[1])
    return row


def setup_power(control):
    control.commands((
        "/setblock 8 180 22 create:creative_motor[facing=south]",
        "/data merge block 8 180 22 {ScrollValue:32}",
        "/setblock 8 180 24 create:shaft[axis=z]",
        "/setblock 9 180 23 create:shaft[axis=x]",
        "/setblock 8 181 23 create:shaft[axis=y]",
        f"/setblock {xyz(POSITION)} create:gearbox[axis=y]",
        f"/tp @s {xyz(wrench.APPROACH['west'])}",
    ))
    start = control.clock()
    for tick in range(1, 9):
        control.step_to(start + tick)


def powered_test(control, rows, *, guest=None):
    actor = guest or control
    guest_axes = []
    start = control.clock()
    for tick in range(9):
        if tick:
            control.step_to(start + tick)
        rows.append(read_power(control, tick, "end_tick"))
        if tick in (0, 4):
            prior = rows[-1]["axis"]
            use(actor, "west")
            if guest:
                multiplayer.until("host to apply the guest's Wrench use", lambda: (
                    control.call("block", *POSITION)["state"] != f"create:gearbox[axis={prior}]"
                ))
            assert control.clock() == start + tick, "World tick advanced during Wrench use"
            rows.append(read_power(control, tick, "after_use"))
            if guest:
                axis = rows[-1]["axis"]
                multiplayer.until("guest to receive the resulting Gearbox state", lambda: (
                    guest.call("block", *POSITION)["state"] == f"create:gearbox[axis={axis}]"
                ))
                guest_axes.append({"tick": tick, "axis": axis})
    return guest_axes


def powered_lan(args, control, observed):
    name = "GearboxWrench"
    control.commands((
        "/setblock 14 178 26 minecraft:smooth_stone",
        "/tp @s 14.5 179 26.5",
    ))
    with TemporaryDirectory(prefix="gbwr-", dir="/tmp") as directory:
        port = control.call("lan", "open", "0", "commands", "force")["port"]
        with multiplayer.joined_client(
            args, Path(directory), f"127.0.0.1:{port}", name, scenario="gearbox-wrench-lan",
        ) as guest:
            multiplayer.until("Wrench guest to join", lambda: any(
                player["name"] == name and player["placed"] for player in control.call("lan", "status")["guests"]
            ))
            west = wrench.APPROACH["west"]
            control.commands((
                f"/gamemode survival {name}",
                f"/tp {name} {xyz(west)}",
                f"/item replace entity {name} hotbar.0 with create:wrench",
            ))
            multiplayer.until("guest to reach the Gearbox with the Wrench", lambda: (
                guest.call("state")["player"]["position"] == list(west)
                and multiplayer.count(guest, "create:wrench") == 1
                and guest.call("block", *POSITION)["state"] == "create:gearbox[axis=y]"
            ))
            guest.call("select", "create:wrench")
            observed["guest_axes"] = powered_test(control, observed["powered"], guest=guest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()

    rotations, powered = reference()
    observed = {"rotations": [], "powered": []}
    suffix = "-lan" if args.lan else ""
    output = ROOT / f".local/gearbox-wrench-horizon{suffix}.json"
    world = "GearboxWrenchLAN" if args.lan else "GearboxWrench"
    try:
        with fixture_world(args, world) as control:
            control.commands((
                *(f"/setblock {xyz(pos)} minecraft:smooth_stone" for pos in SUPPORTS),
                "/gamemode survival",
            ))
            if args.lan:
                rotations = []
                observed["guest_axes"] = []
                setup_power(control)
                powered_lan(args, control, observed)
            else:
                rotation_matrix(control, rotations, observed["rotations"])
                equip(control)
                setup_power(control)
                powered_test(control, observed["powered"])
    finally:
        output.write_text(json.dumps(observed, indent=2) + "\n")
    failures = [
        (section, want, actual)
        for section, expected in (("rotations", rotations), ("powered", powered))
        for want, actual in zip(expected, observed[section], strict=True)
        if want != actual
    ]
    assert not failures, f"{len(failures)} mismatches. First: {failures[0]}. See {output}."
    if args.lan:
        assert observed["guest_axes"] == [{"tick": 0, "axis": "z"}, {"tick": 4, "axis": "y"}]
        print(f"Guest Wrench use matched {len(powered)} Java host samples and replicated both axes.")
    else:
        print(f"Matched {len(rotations)} Wrench transforms and pickups plus {len(powered)} powered samples.")


if __name__ == "__main__":
    main()
