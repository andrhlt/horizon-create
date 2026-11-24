#!/usr/bin/env python3
"""Capture real pinned-Java Item Drain interactions in a disposable checkout.

Use a private populated GRADLE_USER_HOME to keep shared compilation caches intact.
On macOS an APFS copy can be made with `cp -cR ~/.gradle /path/to/private-cache`.
Gradle/GameTest require local socket access even when --offline is selected.
"""

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
PIN = "ac0c444d9828da3453ae8cc65338e8de063286fb"
PREFIX = "CREATE_DRAIN_COLLECTION "


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / ".local/java-reference")
    parser.add_argument("--gradle-home", type=Path, required=True)
    parser.add_argument("--java-home", type=Path, default=Path("/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home"))
    parser.add_argument("--output", type=Path, default=ROOT / ".local/java-drain-collection")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    patch = ROOT / "tools/java-item-drain-collection.patch"
    with tempfile.TemporaryDirectory(prefix="checkout-", dir=args.output) as temporary:
        checkout = Path(temporary) / "create"
        subprocess.run(("git", "clone", "--shared", "--no-checkout", str(args.source.resolve()), str(checkout)), check=True)
        subprocess.run(("git", "checkout", "--detach", PIN), cwd=checkout, check=True)
        subprocess.run(("git", "apply", "--unidiff-zero", str(patch)), cwd=checkout, check=True)
        env = os.environ | {"JAVA_HOME": str(args.java_home.resolve()), "GRADLE_USER_HOME": str(args.gradle_home.resolve())}
        start = time.monotonic()
        result = subprocess.run(("./gradlew", "--offline", "runGameTestServer"), cwd=checkout, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        elapsed = time.monotonic() - start
        log = args.output / f"capture-{time.time_ns()}.log"
        log.write_bytes(result.stdout)
        records = [next(csv.reader([line.split(PREFIX, 1)[1]]))
                   for line in result.stdout.decode(errors="replace").splitlines() if PREFIX in line]
        if result.returncode or len(records) != 5:
            raise RuntimeError(f"Java capture failed: exit={result.returncode}, records={len(records)}, log={log}")
        with (ROOT / "fixtures/item-drain-collection-java.csv").open("w", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(("case", "result", "cargo", "inventory_iron", "held_tool"))
            writer.writerows(records)
        (ROOT / "fixtures/item-drain-collection-java.metadata.json").write_text(json.dumps({
            "revision": PIN, "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
            "records": len(records), "seconds": elapsed,
            "scope": "Actual BlockState.useItemOn with FakePlayer; block-item pass-through, stick and empty-hand collection/repeat. No Java reload or network timing claim.",
        }, indent=2) + "\n")
        print(json.dumps({"records": len(records), "seconds": elapsed, "log": str(log)}))


if __name__ == "__main__":
    main()
