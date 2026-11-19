#!/usr/bin/env python3
"""Compare Wrench preview geometry, hover, expiry, and renderer fade to Java."""

import argparse
import csv
from pathlib import Path
import time

from fixture_world import ROOT, fixture_world

PROBE = "CREATE_CHASSIS_PREVIEW_HORIZON "
RENDERED = "CREATE_CHASSIS_PREVIEW_DRAW "
CHASSIS = (8, 96, 40)
WRENCH_TRACE = {"CREATE_CHASSIS_PREVIEW_TRACE": "1"}


def observations(log):
    rows = log.read_text().splitlines()
    states = [line.removeprefix(PROBE).split(",") for line in rows if line.startswith(PROBE)]
    draws = [line.removeprefix(RENDERED).split(",") for line in rows if line.startswith(RENDERED)]
    return states, draws


def until(check, description):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        observed = check()
        if observed:
            return observed
        time.sleep(0.05)
    raise RuntimeError(f"Timed out waiting for {description}.")


def phase(java, action):
    return [row[3:] for row in java if row[1] == action]


def snapshot(log, expected, *, rendered=False):
    def find():
        states, draws = observations(log)
        for state in reversed(states[-20:]):
            if state[1:7] + state[8:] != expected:
                continue
            # The faces must have reached the actual atlas submission API.
            if rendered and not any(
                frame[0] == state[0] and frame[1:] == expected[2:4] for frame in draws
            ):
                continue
            return state
        return None

    return until(find, f"Chassis preview fields {expected}")


def validate_decay(log, java, commit_tick):
    expected = phase(java, "away") + phase(java, "stowed") + phase(java, "fade")[:-1]
    rows, rendered = observations(log)
    after = [state for state in rows if int(state[0]) > commit_tick]
    away = next((i for i, state in enumerate(after) if state[1] == "199"), None)
    if away is None:
        raise RuntimeError("The held Wrench preview never began expiring after looking away.")
    stowed = next((i for i, state in enumerate(after[away:], start=away) if state[1] == "20"), None)
    if stowed is None:
        raise RuntimeError("Putting away the Wrench did not clamp the preview lifetime.")
    samples = after[away:away + 3] + after[stowed:stowed + len(expected) - 3]
    actual = [row[1:7] + row[8:] for row in samples]
    if actual != expected:
        mismatches = [(a, b) for a, b in zip(expected, actual) if a != b]
        raise RuntimeError(f"Chassis preview expiry differed from Java: {mismatches[:3]}, "
                           f"observed {len(actual)} of {len(expected)} ticks.")
    if samples[-1] != after[-1]:
        raise RuntimeError("The Chassis preview outlived the Java renderer fade.")
    fade = [row for row in samples if row[2] in ("-1", "-2", "-3")]
    if not any(frame[0] in {row[0] for row in fade} and frame[1] != "0" for frame in rendered):
        raise RuntimeError("The fading checker faces were never sent to the renderer.")
    return actual


def run_variant(args, variant, java):
    radial = variant == "radial"
    state = "radial_chassis[axis=y,sticky_east=true]" if radial else "linear_chassis[axis=x,sticky_top=true]"
    with fixture_world(args, f"Chassis-Preview-{variant}", render=True, pack=args.pack, env=WRENCH_TRACE) as control:
        control.commands((
            "/fill 6 95 37 11 95 45 minecraft:smooth_stone",
            f"/setblock 8 96 40 create:{state}",
            "/fill 9 96 40 16 96 40 minecraft:stone",
            *(("/setblock 9 96 41 minecraft:bricks", "/setblock 9 96 42 minecraft:bricks") if radial else ()),
            "/tp @s 8.5 96 43.5 180 24",
            "/item replace entity @s hotbar.0 with create:wrench",
            "/gamemode survival",
        ))
        control.call("select", "create:wrench")
        control.call("look-at", 8.5, 96.5, 41)
        log = control.socket.parent / "ctl.log"
        initial = snapshot(log, phase(java, "wrench")[0], rendered=True)
        if args.visual:
            control.call("key", "f1", "tap")
            control.call("wait", 2)
            control.call("screenshot", ROOT / f".local/chassis-preview-{variant}.png")
            control.call("key", "f1", "tap")

        control.call("mouse", "right", "down")
        control.call("wait", 7)
        buttons = control.call("screen")["buttons"]
        slider = next((item for item in buttons if item["label"] == "Distance"), None)
        if slider is None:
            raise RuntimeError(f"The Distance board did not open: {buttons}.")
        x, y = slider["x"] + 9.5, slider["y"] + slider["h"] / 2
        control.call("scroll-at", x, y, 0)
        hovered = snapshot(log, phase(java, "hover")[0], rendered=True)

        control.call("click-at", x, y, "right")
        until(lambda: control.command("/data get block 8 96 40 ScrollValue").endswith("block data: 2"),
              "the authoritative chassis range commit")
        # The Java world runs freely. Step this frozen fixture once so the
        # server can publish its block entity update to the rendering client.
        control.step_to(control.clock() + 1)
        committed = snapshot(log, phase(java, "commit")[0], rendered=True)
        control.call("script", script="look 0 20\nwait 4\n")
        control.call("select", 2)
        control.call("wait", 33)
        decay = validate_decay(log, java, int(committed[0]))

    return [row[1:7] + row[8:] for row in (initial, hovered, committed)] + decay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--visual", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/chassis-preview-java.csv").open() as file:
        reader = csv.reader(file)
        header, *reference = reader

    actual = []
    for variant in ("linear", "radial"):
        java = [row for row in reference if row[0] == variant]
        samples = run_variant(args, variant, java)
        for row, sample in zip(java[:-1], samples, strict=True):
            actual.append([*row[:3], *sample])
    out = ROOT / ".local/chassis-preview-horizon.csv"
    with out.open("w") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    print(f"Linear and Radial Chassis preview matched {len(actual)} Java rows, including rendered checker faces and outline fade.")


if __name__ == "__main__":
    main()
