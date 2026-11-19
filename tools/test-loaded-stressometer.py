#!/usr/bin/env python3
"""Build a water wheel and compare the loaded stressometer with Java Create."""

import argparse
import csv
from importlib import import_module
import json
from math import isclose
import os
from pathlib import Path
import re
from shutil import copy2
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
GAUGE = "6 102 -10"
LOAD_CHANGES = {
    0: (-6, "create:millstone"),
    12: (-6, "minecraft:air"),
    24: (-8, "create:millstone"),
    36: (-8, "minecraft:air"),
    48: (-1, "create:millstone"),
    96: (-1, "minecraft:air"),
}
WARMUP = 70


def run(args, scratch, expected):
    socket = scratch / "ctl.sock"
    game = scratch / "game"
    log = scratch / "ctl.log"
    mods = game / "horizon-mods"
    mods.mkdir(parents=True)
    copy2(ROOT / ".local/create.hmod", mods / "create.hmod")
    (game / "horizon-mods.txt").write_text("mod.create:true\n", encoding="utf-8")
    env = dict(os.environ, CREATE_WHEEL_RENDER_ORIGIN="3,101,-13", CREATE_STRESS_TRACE_SEED="2")
    goggles = None
    if args.goggles:
        env["CREATE_GOGGLES_TRACE"] = "1"
        program = import_module("test-goggles-gauges")
        fixture = json.loads((ROOT / "fixtures/goggles-stress-load-java.json").read_text())
        references = program.expected_readouts(fixture)
        goggles = [references[(scenario, "stress")] for scenario in fixture["ticks"]]
        render_samples = program.render_samples

    def ctl(*arguments):
        process = subprocess.run(
            [str(args.ctl), "--socket", str(socket), *map(str, arguments)],
            env=env, text=True, capture_output=True, timeout=45, check=True,
        )
        result = json.loads(process.stdout)
        if result.get("ok") is False:
            raise RuntimeError(f"{arguments[0]} failed: {result}")
        return result

    def command(string):
        return ctl("command", string)

    def clock():
        answer = command("/time query gametime")["chat"][-1]
        return int(re.search(r"\b(\d+) tick", answer)[1])

    def step(ticks):
        end = clock() + ticks
        command(f"/tick step {ticks}")
        deadline = time.monotonic() + 10
        while clock() < end:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"world did not step to {end}")
            time.sleep(0.03)

    def logfile_lines():
        return log.read_text(encoding="utf-8").splitlines()

    def sample(java):
        tick, capacity, stress, target, previous, current, midpoint = java
        time_now = clock()
        tag = command(f"/data get block {GAUGE}")["chat"][-1]
        readings = tuple(float(re.search(rf"\b{key}: ([\d.]+)f", tag)[1])
                         for key in ("Capacity", "Stress", "Value"))
        if readings != (capacity, stress, target):
            raise RuntimeError(f"tick {tick:g}: Java network {(capacity, stress, target)}, Horizon {readings}")

        prefix = f"CREATE_WHEEL_FRAME create:stressometer {time_now} "
        deadline = time.monotonic() + 4
        last = None
        while time.monotonic() < deadline:
            for line in reversed(logfile_lines()):
                if line.startswith(prefix):
                    last = tuple(map(float, line[len(prefix):].split()))
                    break
            if last is not None:
                partial, actual_prev, actual_current, angle, vertices, client_target = last
                # The renderer supplies its own partial tick. Translate the
                # Java midpoint angle to the same interpolation point.
                expected_angle = midpoint - 90.0 * (partial - 0.5) * (current - previous)
                if (vertices > 0
                        and client_target == target
                        and isclose(actual_prev, previous, abs_tol=2e-7)
                        and isclose(actual_current, current, abs_tol=2e-7)
                        and isclose(angle, expected_angle, abs_tol=0.00003)):
                    if goggles is not None:
                        samples = logfile_lines()
                        if not any(at == time_now and sample == goggles[int(tick)]
                                   for at, sample in render_samples(samples)):
                            time.sleep(0.04)
                            continue
                    actual_midpoint = angle + 90.0 * (partial - 0.5) * (actual_current - actual_prev)
                    return [int(tick), *readings, actual_prev, actual_current, actual_midpoint,
                            partial, angle, int(vertices)]
            time.sleep(0.04)
        raise RuntimeError(f"tick {tick:g}: Java needle {previous:.9f} → {current:.9f}, "
                           f"Horizon frame {last} (partial, previous, current, angle, vertices, target)")

    ctl("launch", "--offscreen", "--game", args.client, "--resources", args.resources,
        "--world", "LoadedGauge", "--creative", "--wait", "--game-dir", game,
        "--home", game, "--test-terrain", "--render-distance", 4)
    actual = []
    try:
        command("/tick freeze")
        for setup in (
            "/fill 9 100 -12 12 100 -8 minecraft:smooth_stone",
            "/fill 7 99 -13 7 99 -8 minecraft:smooth_stone",
            "/fill 6 100 -13 6 100 -8 minecraft:smooth_stone",
            "/fill 8 100 -13 8 100 -8 minecraft:smooth_stone",
            "/setblock 7 100 -13 minecraft:smooth_stone",
            "/setblock 7 100 -8 minecraft:smooth_stone",
            "/setblock 6 100 -10 create:water_wheel[facing=up]",
            "/setblock 6 101 -10 create:cogwheel[axis=y]",
            f"/setblock {GAUGE} create:stressometer[facing=east,axis_along_first=true]",
            "/setblock 7 100 -9 minecraft:water",
        ):
            command(setup)
        ctl("tp", 10.5, 101, -10.5)
        ctl("look-at", 6.5, 102.4, -9.5)
        if goggles is not None:
            command("/item replace entity @s armor.head with create:goggles")
        step(WARMUP)

        for java in expected:
            tick = int(java[0])
            if tick:
                step(1)
            actual.append(sample(java))
            if tick in LOAD_CHANGES:
                end_z, block = LOAD_CHANGES[tick]
                command(f"/fill 6 101 -9 6 101 {end_z} {block}")
    finally:
        ctl("quit")
        deadline = time.monotonic() + 10
        while socket.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        (ROOT / ".local/horizon-loaded-stressometer.log").write_text(
            log.read_text(encoding="utf-8"), encoding="utf-8",
        )

    output = ROOT / ".local/loaded_stressometer-horizon.csv"
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["tick", "capacity", "stress", "target", "previous", "current",
                         "midpoint_degrees", "partial", "needle_degrees", "needle_vertices"])
        writer.writerows(actual)
    print(f"Loaded stressometer matched Java for all {len(actual)} ticks. See {output}")
    if goggles is not None:
        print(f"The rendered Goggles reading matched the original Java text and styling at all {len(actual)} ticks.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--goggles", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/loaded_stressometer-java.csv").open(encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader)
        expected = [tuple(map(float, row)) for row in reader]
    if [row[0] for row in expected] != list(range(105)):
        parser.error("the Java reference must contain fixture ticks 0–104")
    with tempfile.TemporaryDirectory(prefix="hc-loaded-") as scratch:
        run(args, Path(scratch), expected)


if __name__ == "__main__":
    main()
