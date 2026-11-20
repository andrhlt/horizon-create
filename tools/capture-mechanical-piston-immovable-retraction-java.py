#!/usr/bin/env python3
"""Capture the pinned Java immovable-target regression using an isolated cache."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
PIN = "ac0c444d9828da3453ae8cc65338e8de063286fb"
NAME = "mechanical-piston-immovable-retraction"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java-source", type=Path, default=ROOT / ".local/java-reference")
    parser.add_argument("--gradle-home", type=Path, required=True,
                        help="Populated, worker-private Gradle cache; never supply a shared cache")
    parser.add_argument("--java-home", type=Path, default=Path("/opt/homebrew/opt/openjdk@21"))
    args = parser.parse_args()
    out = ROOT / ".local/mechanical-piston"
    out.mkdir(parents=True, exist_ok=True)
    patch = ROOT / f"tools/java-{NAME}.patch"
    with tempfile.TemporaryDirectory(prefix="piston-immovable-java-") as scratch:
        checkout = Path(scratch) / "create"
        subprocess.run(["git", "clone", "--shared", "--no-checkout", str(args.java_source.resolve()), str(checkout)], check=True)
        subprocess.run(["git", "checkout", "--detach", PIN], cwd=checkout, check=True)
        subprocess.run(["git", "apply", str(patch)], cwd=checkout, check=True)
        started = time.monotonic()
        result = subprocess.run(["./gradlew", "--offline", "--no-daemon", "--max-workers", "2", "runGameTestServer"],
                                cwd=checkout, env=os.environ | {"JAVA_HOME": str(args.java_home.resolve()),
                                    "GRADLE_USER_HOME": str(args.gradle_home.resolve())},
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        elapsed = time.monotonic() - started
    log = out / f"java-immovable-retraction-{time.time_ns()}.log"
    log.write_bytes(result.stdout)
    rows = [json.loads(line.split("CREATE_PISTON_IMMOVABLE ", 1)[1])
            for line in result.stdout.decode(errors="replace").splitlines() if "CREATE_PISTON_IMMOVABLE {" in line]
    assert result.returncode == 0 and len(rows) == 24, (result.returncode, len(rows), str(log))
    rows.sort(key=lambda row: row["tick"])
    assert [row["tick"] for row in rows] == list(range(24))
    assert rows[10]["state"] == "extended" and rows[-1]["state"] == "retracted"
    assert rows[-1]["cells"][3] == "minecraft:bedrock"
    trace = ROOT / f"fixtures/{NAME}-java.jsonl"
    trace.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
    metadata = {"revision": PIN, "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
                "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest(), "records": len(rows),
                "capture_seconds": elapsed, "tick_origin": "GameTest tick 2 after the one-pole rig setup; place bedrock and reverse before sampling tick 10.",
                "scope": "Sticky east piston extends, then retracts with immovable bedrock touching the head; apparatus must return without moving bedrock."}
    (ROOT / f"fixtures/{NAME}-java.metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata))


if __name__ == "__main__":
    main()
