#!/usr/bin/env python3
"""Run the pinned Java Creative Motor render and competition traces headlessly.

Clones the shared pinned Java checkout, applies the family trace patch and runs
the real Java GameTest server with JDK 21. The render trace records the intended
`SHAFT_HALF` rotation for all six facings; the competition trace records the
speeds and existence of two motors sharing one shaft across a setting flip, a
source removal and a source re-add.
"""

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


def main():
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
        shutil.rmtree(checkout / "run/world", ignore_errors=True)
        env = {**os.environ, "JAVA_HOME": "/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home"}
        start = time.monotonic()
        result = subprocess.run(
            ["./gradlew", "--offline", "runGameTestServer"], cwd=checkout, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        elapsed = time.monotonic() - start
    (out / "java-family.log").write_bytes(result.stdout)
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
    assert result.returncode == 0 and render and compete, (result.returncode, len(render), len(compete), str(out / "java-family.log"))

    render.sort(key=lambda row: (int(row["index"]), int(row["tick"])))
    compete.sort(key=lambda row: (int(row["tick"]), int(row["case"]), int(row["offset"])))
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
