#!/usr/bin/env python3
"""Run the pinned Java Creative Motor render and competition traces headlessly.

Clones the shared pinned Java checkout, applies the family trace patch and runs
the real Java GameTest server with JDK 21. The render trace records the intended
`SHAFT_HALF` rotation for all six facings; the competition trace records the
speeds and existence of two motors sharing one shaft across a setting flip, a
source removal and a source re-add.
"""

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "ac0c444d9828da3453ae8cc65338e8de063286fb"


def isolate_competition(checkout):
    registry = checkout / "src/main/java/com/simibubi/create/infrastructure/gametest/CreateGameTests.java"
    source = registry.read_text()
    render_clause = 'test.testName().equals("TestMisc.creativeMotorRenderFrames")\n\t\t\t\t|| '
    if source.count(render_clause) != 1:
        raise RuntimeError("Unable to isolate the Creative Motor competition GameTest.")
    registry.write_text(source.replace(render_clause, ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--competition-only", action="store_true", help="capture the competition GameTest in its own world")
    args = parser.parse_args()
    out = ROOT / ".local/creative-motor"
    out.mkdir(parents=True, exist_ok=True)
    patch = ROOT / "tools/java-creative-motor-family-trace.patch"
    with tempfile.TemporaryDirectory(prefix="motor-java-") as tmp:
        checkout = Path(tmp) / "create"
        subprocess.run(
            ["git", "clone", "--shared", "--no-checkout", str(ROOT / ".local/java-reference"), str(checkout)],
            check=True, stdout=subprocess.DEVNULL,
        )
        subprocess.run(["git", "checkout", "--detach", PIN], cwd=checkout, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "apply", str(patch)], cwd=checkout, check=True)
        if args.competition_only:
            isolate_competition(checkout)
        shutil.rmtree(checkout / "run/world", ignore_errors=True)
        env = {**os.environ, "JAVA_HOME": "/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home"}
        start = time.monotonic()
        result = subprocess.run(
            ["./gradlew", "--offline", "runGameTestServer"], cwd=checkout, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        elapsed = time.monotonic() - start
    log_name = "java-competition-isolated.log" if args.competition_only else "java-family.log"
    log = out / log_name
    log.write_bytes(result.stdout)
    text = result.stdout.decode(errors="replace")

    render = [
        line.split("CREATE_MOTOR_RENDER,", 1)[1].split(",")
        for line in text.splitlines() if "CREATE_MOTOR_RENDER," in line
    ]
    compete = [
        line.split("CREATE_MOTOR_COMPETE,", 1)[1].split(",")
        for line in text.splitlines() if "CREATE_MOTOR_COMPETE," in line
    ]
    render = [dict(zip(
        ["index", "tick", "facing", "axis", "axis_direction", "speed", "phase", "angle"], row, strict=True,
    )) for row in render]
    compete = [dict(zip(
        ["tick", "case", "offset", "present", "speed"], row, strict=True,
    )) for row in compete]
    if result.returncode or not compete or bool(render) == args.competition_only:
        raise RuntimeError(f"Unexpected Java capture result {result.returncode}, with {len(render)} render and {len(compete)} competition rows. See {log}.")

    compete.sort(key=lambda row: (int(row["tick"]), int(row["case"]), int(row["offset"])))
    competition_filename = "creative-motor-competition-isolated-java.csv" if args.competition_only else "creative-motor-competition-java.csv"
    with (ROOT / "fixtures" / competition_filename).open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=["tick", "case", "offset", "present", "speed"])
        writer.writeheader()
        writer.writerows(compete)
    if args.competition_only:
        metadata = {
            "revision": PIN,
            "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
            "csv_sha256": hashlib.sha256((ROOT / "fixtures" / competition_filename).read_bytes()).hexdigest(),
            "records": len(compete),
            "seconds": elapsed,
            "scope": "Isolated pinned Java creativeMotorCompetition GameTest; both lanes, ticks 0–23, samples before actions at ticks 5, 12 and 18",
        }
        metadata_path = ROOT / "fixtures/creative-motor-competition-isolated-java.metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
        print(json.dumps({**metadata, "log": str(log)}))
        return

    render.sort(key=lambda row: (int(row["index"]), int(row["tick"])))
    fields = ["index", "tick", "facing", "axis", "axis_direction", "speed", "phase", "angle"]
    with (ROOT / "fixtures/creative-motor-render-java.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: row[k] for k in fields} for row in render)
    with (ROOT / "fixtures/creative-motor-competition-java.csv").open("w") as stream:
        warp = ["tick", "case", "offset", "present", "speed"]
        writer = csv.DictWriter(stream, fieldnames=warp)
        writer.writeheader()
        writer.writerows({k: row[k] for k in warp} for row in compete)

    (ROOT / "fixtures/creative-motor-render-java.metadata.json").write_text(json.dumps({
        "revision": PIN,
        "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
        "render_records": len(render),
        "competition_records": len(compete),
        "seconds": elapsed,
        "scope": "Pinned Java CreativeMotorRenderer intent for all six facings at +32 and -48 RPM, and two motors sharing one shaft across a setting flip, source removal and re-add",
    }, indent=2) + "\n")
    print(json.dumps({"render": len(render), "competition": len(compete), "seconds": elapsed}))


if __name__ == "__main__":
    main()
