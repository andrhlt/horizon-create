#!/usr/bin/env python3
"""Place an original water-wheel fixture and compare its Java tick trace."""

import argparse
import csv
import json
from math import isclose
import os
import re
from pathlib import Path
from shutil import copy2
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = (3, 96, -12)


def run(args, scratch, header, expected, visual):
    socket = scratch / "ctl.sock"
    game = scratch / "game"
    log = scratch / "ctl.log"
    mods = game / "horizon-mods"
    mods.mkdir(parents=True)
    copy2(args.pack or ROOT / ".local/create.hmod", mods / "create.hmod")
    (game / "horizon-mods.txt").write_text("mod.create:true\n", encoding="utf-8")
    size = "large" if args.large else "small"
    fixture = f"{size}_waterwheel"
    wheel_block = f"{size}_water_wheel" if args.large else "water_wheel"
    template_id = f"gametest/fluids/{fixture}"
    template = Path(template_id + ".nbt")
    if args.large:
        open_lever, left_lever = (6, 103, -11), (8, 102, -11)
        lever_platform, lever_view = "/fill 5 100 -14 9 100 -14 minecraft:smooth_stone", (7.5, 101, -13.5)
        camera_platform, camera_view = "/fill 12 98 -16 15 98 -13 minecraft:smooth_stone", (13.5, 99, -14.5)
        look_at = (7.5, 98.5, -9.5)
    else:
        open_lever, left_lever = (5, 101, -11), (7, 100, -11)
        lever_platform, lever_view = "/fill 4 98 -14 8 98 -14 minecraft:smooth_stone", (6.5, 99, -13.5)
        camera_platform, camera_view = "/fill 10 97 -16 13 97 -13 minecraft:smooth_stone", (11.5, 98, -14.5)
        look_at = (6.5, 98, -9.5)
    saved = game / "saves/Wheel/generated/create/structures" / template
    saved.parent.mkdir(parents=True)
    copy2(ROOT / ".local/fixtures/data/create/structure" / template, saved)

    trace_origin = ",".join(map(str, ORIGIN))
    env = dict(os.environ, CREATE_WHEEL_TRACE_ORIGIN=trace_origin)
    if args.large:
        env["CREATE_WHEEL_TRACE_LARGE"] = "1"
    if visual:
        env["CREATE_WHEEL_RENDER_ORIGIN"] = trace_origin

    def ctl(*arguments):
        command = [str(args.ctl.resolve()), "--socket", str(socket), *map(str, arguments)]
        process = subprocess.run(command, text=True, env=env, capture_output=True, timeout=45)
        if process.returncode:
            raise RuntimeError(f"{arguments[0]} failed: {process.stdout} {process.stderr}")
        result = json.loads(process.stdout)
        if result.get("ok") is False:
            raise RuntimeError(f"{arguments[0]} failed: {result}")
        return result

    def rows():
        return [
            line.split("CREATE_WHEEL ", 1)[1].split()
            for line in log.read_text(encoding="utf-8").splitlines()
            if "CREATE_WHEEL " in line
        ]

    def wait_for(read, ready, message):
        deadline = time.monotonic() + 6
        while True:
            value = read()
            if ready(value):
                return value
            if time.monotonic() >= deadline:
                raise RuntimeError(f"{message}: {value}")
            time.sleep(0.05)

    def frames():
        time = ctl("command", "/time query gametime")["chat"][-1]
        game_time = int(re.findall(r"\d+", time)[-1])
        actual = {}
        for line in log.read_text(encoding="utf-8").splitlines():
            if "CREATE_WHEEL_FRAME " not in line:
                continue
            block, time, partial, a, b, angle, vertices, _target = line.split("CREATE_WHEEL_FRAME ", 1)[1].split()
            if int(time) == game_time:
                actual[block.removeprefix("create:")] = (float(partial), float(a), float(b), float(angle), int(vertices))
        return game_time, actual

    def check_frame(tick):
        java = visual[tick]
        required = {wheel_block, "speedometer", "stressometer"}

        def matches(sample):
            game_time, models = sample
            if models.keys() != required:
                return False
            wheel = models[wheel_block]
            speed = models["speedometer"]
            stress = models["stressometer"]
            if any(frame[-1] == 0 for frame in models.values()):
                return False
            # Java and Horizon read different world clocks and world positions.
            # Compare phase and the same elapsed rotation on the same clock.
            partial, rpm, phase, wheel_degrees, _ = wheel
            clock_delta = game_time - int(java["game_time"]) + partial - 0.5
            phase_delta = phase - float(java["phase"])
            expected = float(java["mid_wheel"]) + clock_delta * float(java["rpm"]) * 0.3 + phase_delta
            return (
                rpm == float(java["rpm"])
                and abs((wheel_degrees - expected + 180) % 360 - 180) < 0.00015
                and dial_matches(speed, float(java["speed_prev"]), float(java["speed_current"]))
                and dial_matches(stress, 0.0, float(java["stress_current"]))
            )

        game_time, models = wait_for(frames, matches, f"visual mismatch at fixture tick {tick}")
        wheel, speed, stress = (models[block] for block in (wheel_block, "speedometer", "stressometer"))
        return [tick, game_time, *wheel, *speed, *stress]

    def dial_matches(frame, previous, current):
        partial, a, b, angle, _ = frame
        reference = -90.0 * (previous + partial * (current - previous))
        return (isclose(a, previous, abs_tol=0.0000006)
                and isclose(b, current, abs_tol=0.0000006)
                and isclose(angle, reference, abs_tol=0.00006))

    visual_rows = []
    ctl("launch", "--offscreen" if visual else "--headless", "--game", args.client.resolve(), "--resources",
        args.resources.resolve(), "--world", "Wheel", "--creative", "--wait",
        "--game-dir", game, "--home", game, "--test-terrain", "--render-distance", 4)
    try:
        ctl("command", "/tick freeze")
        x, y, z = ORIGIN
        ctl("command", f"/place template create:{template_id} {x} {y} {z}")
        custom_blocks = {f"create:{wheel_block}": 1, "create:speedometer": 1, "create:stressometer": 1}
        if args.large:
            custom_blocks["create:water_wheel_structure"] = 8
        wait_for(lambda: ctl("blocks", x, y, z, x + 8, y + 7, z + 4)["counts"],
                 lambda counts: all(counts.get(block) == count for block, count in custom_blocks.items()),
                 "water-wheel template did not load")
        ctl("command", lever_platform)
        ctl("tp", *lever_view)
        ctl("wait", 3)
        interaction = ctl("interact", *open_lever, "north")
        wait_for(lambda: ctl("block", *open_lever),
                 lambda block: "powered=false" in block["state"],
                 f"opening lever did not toggle after {interaction}")
        wait_for(rows, lambda trace: len(trace) == 1, "Horizon did not sample tick zero")
        if visual:
            ctl("command", camera_platform)
            ctl("tp", *camera_view)
            ctl("look-at", *look_at)
            visual_rows.append(check_frame(0))
        for tick in range(1, len(visual or expected)):
            ctl("command", "/tick step 1")
            trace = wait_for(rows, lambda trace: len(trace) > tick, f"no sample for tick {tick}")
            # The upstream test closes one side as soon as both falling streams
            # reach the wheel and their opposing rotations have canceled out.
            row = trace[tick]
            both_streams = row[2:6] == ["8", "8", "false", "false"]
            stopped = row[8:10] == ["0.0", "0.0"]
            if row[1] == "false" and both_streams and stopped:
                if visual:
                    ctl("tp", *lever_view)
                    ctl("wait", 3)
                interaction = ctl("interact", *left_lever, "north")
                wait_for(lambda: ctl("block", *left_lever),
                         lambda block: "powered=true" in block["state"],
                         f"side lever did not toggle after {interaction}")
                if visual:
                    ctl("tp", *camera_view)
                    ctl("look-at", *look_at)
            if visual:
                visual_rows.append(check_frame(tick))
        if visual:
            ctl("screenshot", ROOT / f".local/{fixture}-animated.png")
    finally:
        ctl("quit")
        deadline = time.monotonic() + 10
        while socket.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        (ROOT / f".local/horizon-{fixture}.log").write_text(log.read_text(encoding="utf-8"), encoding="utf-8")

    actual = rows()[:len(expected)] if visual else rows()
    output = ROOT / f".local/{fixture}-horizon.csv"
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(java, horizon) for java, horizon in zip(expected, actual) if java != horizon]
    if len(expected) != len(actual) or differences:
        raise SystemExit(f"Water wheel mismatch: {len(differences)} differing rows, "
                         f"Java {len(expected)} rows, Horizon {len(actual)}. "
                         f"First differing rows (Java, Horizon): {differences[:4]}. See {output}")
    print(f"{size.capitalize()} water wheel matched Java for all {len(actual)} ticks. See {output}")
    if visual:
        output = ROOT / f".local/{fixture}-visual-horizon.csv"
        with output.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file, lineterminator="\n")
            writer.writerow(["tick", "time", "wheel_partial", "rpm", "phase", "wheel_degrees", "wheel_vertices",
                             "speed_partial", "speed_prev", "speed_current", "speed_degrees", "speed_vertices",
                             "stress_partial", "stress_prev", "stress_current", "stress_degrees", "stress_vertices"])
            writer.writerows(visual_rows)
        print(f"Wheel and gauge render transforms matched Java for {len(visual_rows)} ticks. See {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ctl", type=Path)
    parser.add_argument("client", type=Path)
    parser.add_argument("resources", type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--large", action="store_true")
    args = parser.parse_args()
    fixture = "large_waterwheel" if args.large else "small_waterwheel"
    with (ROOT / f"fixtures/{fixture}-java.csv").open(encoding="utf-8") as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)
    visual = []
    if args.visual:
        with (ROOT / f"fixtures/{fixture}-visual-java.csv").open(encoding="utf-8") as file:
            visual = list(csv.DictReader(file))
    with tempfile.TemporaryDirectory(prefix="hc-wheel-") as scratch:
        run(args, Path(scratch), header, expected, visual)


if __name__ == "__main__":
    main()
