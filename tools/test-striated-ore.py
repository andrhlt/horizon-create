#!/usr/bin/env python3
"""Replay the original Java Striated Ore blocks against the patched Horizon library."""

import argparse
from collections import defaultdict
import csv
import gzip
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from create_worldgen import configured_feature

ROOT = Path(__file__).resolve().parents[1]


def compile_replay(args, target):
    if args.artifacts:
        report = args.artifacts.read_text()
    else:
        launcher = ROOT / ".local/patched-launcher"
        command = ["cargo", "build", "--manifest-path", args.horizon_stage / "Cargo.toml",
                   "--locked", "--offline", "--profile", "fast", "-p", "horizon-world", "--lib",
                   "--message-format=json-render-diagnostics"]
        report = subprocess.check_output(command, text=True, env=os.environ | {
            "CARGO_HOME": str(launcher / "cargo"),
            "CARGO_TARGET_DIR": str(launcher / "native/target"),
        })
    artifacts = [event for line in report.splitlines() if (event := json.loads(line))["reason"] == "compiler-artifact"]
    libraries = {}
    for name in ("horizon_world", "horizon_core"):
        libraries[name] = next(path for event in artifacts if event["target"]["name"] == name
                               for path in event["filenames"] if path.endswith(".rlib"))
    dependencies = sorted({Path(path).parent for event in artifacts for path in event["filenames"]})
    executable = target / "replay"
    subprocess.run([
        "rustc", "--edition", "2024", "-C", "opt-level=2", ROOT / "tools/test-striated-ore.rs",
        *(flag for dependency in dependencies for flag in ("-L", f"dependency={dependency}")),
        *(flag for name, library in libraries.items() for flag in ("--extern", f"{name}={library}")),
        "-o", executable,
    ], check=True)
    return executable


def verify(args, scratch):
    executable = compile_replay(args, scratch)
    with (ROOT / "fixtures/striated-ore-origins-java.csv").open(newline="") as source:
        origins = list(csv.DictReader(source))
    reference = defaultdict(set)
    with gzip.open(ROOT / "fixtures/striated-ore-blocks-java.csv.gz", "rt", newline="") as source:
        for row in csv.DictReader(source):
            reference[row["feature"], row["seed"]].add(tuple(row[key] for key in ("dx", "dy", "dz", "block")))
    for row in origins:
        name, seed = row["feature"], row["seed"]
        expected = reference[name, seed]
        config = scratch / f"{name}.json"
        source = args.create_source / f'src/generated/resources/data/create/worldgen/configured_feature/{name}.json'
        config.write_text(json.dumps(configured_feature(json.loads(source.read_text()))))
        output = subprocess.check_output([
            executable, config, name.rsplit("_", 1)[-1], seed,
            *(row[f"origin_{axis}"] for axis in "xyz"),
        ], text=True)
        actual = {tuple(values) for values in csv.reader(output.splitlines())}
        if actual != expected:
            raise RuntimeError(f"{name} seed {seed}: {len(actual - expected)} Horizon-only, "
                               f"{len(expected - actual)} Java-only. "
                               f"First differences {sorted(actual ^ expected)[:8]}.")
        print(f"{name} seed {seed} matched all {len(actual)} original Java block changes.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("create_source", type=Path)
    parser.add_argument("--horizon-stage", type=Path, default=ROOT / ".local/patched-launcher/native/stage")
    parser.add_argument("--artifacts", type=Path, help="reuse a matching cargo build's JSON artifact log")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-striated-replay-") as scratch:
        verify(args, Path(scratch))


if __name__ == "__main__":
    main()
