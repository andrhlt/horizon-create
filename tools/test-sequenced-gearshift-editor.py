#!/usr/bin/env python3
"""Program a Sequenced Gearshift through its actual editor and compare Java ticks."""
import argparse
import hashlib
from math import isclose
from pathlib import Path
import re
import time
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world

SEQUENCER = (8, 101, -10)
OUTPUT = (9, 101, -10)
PASS_THROUGH = (8, 101, -14)
ATLAS_HASH = "746a91b765dba277625d8fd9061af073704f2d691ecbb178edfcd33432469b34"
KINETIC_ITEM = "create:shaft"

def coords(pos):
    return " ".join(map(str, pos))

def sample(nbt, key):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", nbt)
    return float(match[1]) if match else 0.0

def wait_until(control, reason, predicate):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if predicate():
            return
        control.call("wait", 1)
    raise RuntimeError(f"Timed out waiting for {reason}.")

def setup(control):
    control.commands((
        "/fill 4 100 -16 14 100 -5 minecraft:smooth_stone",
        "/fill 4 101 -16 14 104 -5 minecraft:air",
        "/setblock 7 101 -10 create:creative_motor[facing=east]",
        "/setblock 8 101 -10 create:sequenced_gearshift[axis=x,state=0,vertical=false]",
        "/setblock 9 101 -10 create:shaft[axis=x]",
        "/tp @s 8.5 101.0 -6.5",
        "/gamemode survival",
    ))
    control.call("wait", 3)

def open_editor(control, pos=SEQUENCER, face="south"):
    control.call("interact", *pos, face)
    wait_until(control, "the Sequenced Gearshift editor", lambda: control.call("state")["screen"] == "mod")
    wait_until(control, "the editor's first row", lambda: len(control.call("screen")["buttons"]) >= 4)

def buttons(control):
    return control.call("screen")["buttons"]

def widget(control, label, index=0):
    hits = [button for button in buttons(control) if button["label"].startswith(label)]
    if index >= len(hits):
        raise RuntimeError(f"Expected the {index}th editor field starting with {label!r}: {buttons(control)}.")
    hit = hits[index]
    return hit["x"] + hit["w"] / 2, hit["y"] + hit["h"] / 2

def roll(control, label, direction, count=1, *, index=0):
    x, y = widget(control, label, index)
    control.call("script", script=f"scroll-at {x} {y} {direction}\n" * count)
    control.call("wait", 2)

def configure(control, *, frames=None):
    open_editor(control)
    if frames:
        control.call("screenshot", str(frames / "SequencerDefault.png"))
    roll(control, "Angle: ", -1, 45)
    roll(control, "Speed, Direction: ", -1)
    roll(control, "2: ", -1, 2)
    roll(control, "Duration: ", -1, 6)
    roll(control, "3: ", -1)
    roll(control, "4: ", -1, 3)
    roll(control, "Distance: ", -1, 4)
    roll(control, "Speed, Direction: ", 1, 2, index=1)
    labels = [entry["label"] for entry in buttons(control)]
    expected = ["1: Turn", "Angle: 45°", "Speed, Direction: >>", "2: Delay", "Duration: 4t",
                "3: Await", "4: Piston", "Distance: 1m", "Speed, Direction: <<", "5: End", "Confirm"]
    if labels != expected:
        raise RuntimeError(f"The editor's final program differs: {labels}.")
    if frames:
        control.call("screenshot", str(frames / "SequencerProgram.png"))
    control.call("click-at", *widget(control, "Confirm"))
    wait_until(control, "confirmation to close the sequencer", lambda: control.call("state")["screen"] == "playing")

def program_matches(control, expected, pos=SEQUENCER):
    nbt = control.command(f"/data get block {coords(pos)} Instructions")
    saved = re.findall(r"\{([^{}]+)\}", nbt)
    wanted = re.findall(r"\{([^{}]+)\}", expected)
    normalize = lambda entries: [sorted(part.replace(" ", "") for part in row.split(",")) for row in entries]
    return normalize(saved) == normalize(wanted)

def pass_through(control, placements):
    if len(placements) != 2:
        raise RuntimeError(f"Expected original horizontal and vertical shaft placements, got {placements}.")
    for row in placements:
        face, axis = row.split(",")
        vertical = str(face == "up").lower()
        neighbor = (8, 102, -14) if face == "up" else (9, 101, -14)
        control.commands((
            f"/setblock {coords(PASS_THROUGH)} create:sequenced_gearshift[axis=x,state=0,vertical={vertical}]",
            "/tp @s 11.5 101.0 -13.5",
            f"/item replace entity @s hotbar.0 with {KINETIC_ITEM}",
        ))
        wait_until(control, "the kinetic item to reach the player", lambda: (
            control.call("inventory")["counts"].get(KINETIC_ITEM) == 1
        ))
        control.call("select", KINETIC_ITEM)
        used = control.call("interact", *PASS_THROUGH, face)
        control.call("wait", 3)
        got = control.call("block", *neighbor)["state"]
        screen = control.call("state")["screen"]
        if got != f"create:shaft[axis={axis},waterlogged=false]" or screen != "playing" or (
            used.get("inventory_change", {}).get(KINETIC_ITEM) != -1
        ):
            raise RuntimeError(f"The {face} shaft should place on the {axis} axis without opening the editor: {got}, {screen}, {used}.")

def original_program():
    return (ROOT / "fixtures/sequenced-gearshift-program-java.snbt").read_text().strip()

def compare(args):
    with ZipFile(args.pack or ROOT / ".local/create.hmod") as archive:
        data = archive.read("assets/create/textures/gui/sequencer.png")
        if hashlib.sha256(data).hexdigest() != ATLAS_HASH:
            raise RuntimeError("The packaged Sequenced Gearshift atlas differs from Java.")
    tick_header, *rows = (ROOT / "fixtures/sequenced-gearshift-editor-java.csv").read_text().splitlines()
    placement_header, *placements = (ROOT / "fixtures/sequenced-gearshift-placement-java.csv").read_text().splitlines()
    program = original_program()
    if len(rows) != 44:
        raise RuntimeError(f"Expected 44 Java tick rows, got {len(rows)}.")
    if args.frames:
        args.frames.mkdir(parents=True, exist_ok=True)
    with fixture_world(args, "SequencerEditor", render=True, pack=args.pack) as control:
        setup(control)
        start = control.clock()
        diffs = []
        for raw in rows:
            fields = raw.split(",")
            tick = int(fields[0])
            if tick:
                control.step_to(start + tick)
            if tick == 2:
                configure(control, frames=args.frames)
                wait_until(control, "the program to arrive on the server", lambda: program_matches(control, program))
                if control.clock() != start + 2:
                    raise RuntimeError("Configuring the sequencer advanced world time.")
            nbt, out = control.commands((
                f"/data get block {coords(SEQUENCER)}", f"/data get block {coords(OUTPUT)}",
            ))
            analog_state = int(re.search(r"\bstate=(\d)", control.call("block", *SEQUENCER)["state"])[1])
            actual = (analog_state, *(sample(nbt, name) for name in (
                "InstructionIndex", "InstructionDuration", "Timer", "InstructionProgress", "Speed",
            )), sample(out, "Speed"), sample(nbt, "PrevPowered"))
            expected = tuple(float(item == "true") if item in ("true", "false") else float(item)
                             for item in fields[1:])
            for name, want, got in zip(("analog state", "program row", "duration", "timer", "progress",
                                        "input RPM", "output RPM", "redstone"),
                                       expected, actual, strict=True):
                if not isclose(want, got, abs_tol=0.00006):
                    diffs.append((tick, name, want, got))
            if tick == 0:
                control.command("/data merge block 7 101 -10 {ScrollValue:32}")
            if tick in (4, 20):
                control.command("/setblock 8 102 -10 minecraft:redstone_block")
            if tick in (5, 21):
                control.command("/setblock 8 102 -10 minecraft:air")
        if diffs:
            raise RuntimeError(f"{len(diffs)} program tick differences: {diffs[:12]}.")
        pass_through(control, placements)
    print("The real editor, saved five-row program, 44 Java tick samples and kinetic placement bypass matched.")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--frames", type=Path)
    compare(parser.parse_args())

if __name__ == "__main__":
    main()
