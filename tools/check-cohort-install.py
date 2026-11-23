#!/usr/bin/env python3
"""Validate and stage the APP-2137 compatible install inputs.

This is deliberately a packaging check. It does not launch a game or certify
the unfinished Create/Naturalist combined candidate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()


def fail(message: str) -> None:
    raise SystemExit(f"cohort check failed: {message}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "cohort/APP-2137-cohort.json")
    parser.add_argument("--carry-on", type=Path)
    parser.add_argument("--wildlife-tuning", type=Path)
    parser.add_argument("--huge-trees", type=Path)
    parser.add_argument("--stage", type=Path, help="write isolated client/server install inputs")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    cohort = manifest["cohort"]
    print(f"cohort: {manifest['ticket']} ({manifest['status']})")
    print(f"engine: {cohort['horizon_revision']}  game: {cohort['minecraft']}")
    print(f"sdk: {cohort['sdk']}  mixins: {cohort['mixins']}")
    print(f"launcher: {cohort['launcher']['version']} ({cohort['launcher']['sha256']})")
    print(f"rust: {cohort['rust']['version']} ({cohort['rust']['sha256']})")

    for name, option in (("carry_on", args.carry_on), ("wildlife_tuning", args.wildlife_tuning), ("huge_trees", args.huge_trees)):
        if option is None:
            continue
        expected = manifest["sources"][name]
        actual = git_commit(option)
        expected_commit = expected["commit"]
        if not (actual == expected_commit or actual.startswith(expected_commit)):
            fail(f"{name} is {actual}, expected {expected_commit}")
        package = option / expected["package"]
        if not package.is_file():
            fail(f"missing {name} package: {package}")
        actual_hash = sha256(package)
        if actual_hash != expected["package_sha256"]:
            fail(f"{name} package hash {actual_hash}, expected {expected['package_sha256']}")
        parsed = tomllib.loads((option / expected["manifest"]).read_text())
        native = parsed.get("native", {})
        if expected.get("content_only"):
            print(f"{name}: content-only package; native pin is not applicable")
        else:
            for key, expected_value in (("game", cohort["minecraft"]), ("horizon", cohort["horizon_revision"]), ("mixins", cohort["mixins"])):
                if native.get(key) != expected_value:
                    fail(f"{name} manifest {key}={native.get(key)!r}, expected {expected_value!r}")
        print(f"{name}: commit {actual} package {actual_hash}")

    if args.stage:
        stage = args.stage.resolve()
        if stage.exists():
            fail(f"stage already exists; choose an isolated new path: {stage}")
        packages = []
        for name, option in (("carry_on", args.carry_on), ("wildlife_tuning", args.wildlife_tuning), ("huge_trees", args.huge_trees)):
            if option is not None:
                packages.append(option / manifest["sources"][name]["package"])
        if not packages:
            fail("--stage needs at least one companion repository")
        for side in ("client", "server"):
            target = stage / side / "horizon-native-mods"
            target.mkdir(parents=True)
            for package in packages:
                shutil.copy2(package, target / package.name)
        records = [{"name": p.name, "sha256": sha256(p)} for p in packages]
        (stage / "INSTALL-MANIFEST.json").write_text(json.dumps({
            "ticket": manifest["ticket"],
            "engine": cohort["horizon_revision"],
            "minecraft": cohort["minecraft"],
            "client_server_packages": records,
            "matching_bytes": all(sha256(stage / side / "horizon-native-mods" / p.name) == sha256(p) for side in ("client", "server") for p in packages),
        }, indent=2) + "\n")
        print(f"staged matching client/server inputs: {stage}")
    print("compatible-install check: passed (manifest/package scope only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
