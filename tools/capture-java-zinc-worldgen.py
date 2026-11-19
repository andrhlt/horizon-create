#!/usr/bin/env python3
"""Capture real seed-based Create Zinc ore placement in a disposable Java world."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
import os
from pathlib import Path
import re
from tempfile import mkdtemp

capture = import_module("capture-java-elevator-standing")
BLOCK = re.compile(r"^CREATE_ZINC_WORLD_BLOCK (-?\d+),(-?\d+),(-?\d+),([a-z:_]+)$", re.MULTILINE)


def record(checkout, output, java, args, disabled):
    server_dir = output / ("disabled" if disabled else "enabled")
    server_dir.mkdir()
    (server_dir / "eula.txt").write_text("eula=true\n")
    (server_dir / "server.properties").write_text(
        f"level-seed={args.seed}\nlevel-type=minecraft:normal\nonline-mode=false\n"
        "server-ip=127.0.0.1\nserver-port=0\nspawn-protection=0\n"
        "view-distance=3\nsimulation-distance=3\n"
    )
    if disabled:
        config = server_dir / "config"
        config.mkdir()
        (config / "create-common.toml").write_text("[worldgen]\ndisableWorldGen = true\n")
    marker = server_dir / "force-loaded"
    jvm = ["-Dparity.zinc.worldgen=true", f"-Dparity.zinc.chunks={args.chunks}",
           f"-Dparity.zinc.nether={str(args.nether).lower()}",
           f"-Dparity.zinc.settled={str(args.settled).lower()}",
           f"-Dparity.zinc.halo={args.halo}",
           f"-Dparity.zinc.striated={str(args.include_striated or args.nether).lower()}"]
    if args.forced:
        jvm.append(f"-Dparity.zinc.forced={marker}")
    with ExitStack() as stack:
        server, log = capture.launch(stack, checkout, output, java, "server", server_dir, (), jvm)
        if args.forced:
            capture.wait_for(server, log, r"Done \([.0-9]+s\)!", timeout=120)
            lo = -16 * args.halo
            hi = 16 * (args.chunks + args.halo) - 1
            prefix = "execute in minecraft:the_nether run " if args.nether else ""
            capture.send(server, f"{prefix}forceload add {lo} {lo} {hi} {hi}")
            capture.wait_for(server, log, r"(?i)marked.*force.?load", timeout=60)
            marker.touch()
        capture.wait_for(server, log, "CREATE_ZINC_WORLD_DONE", timeout=120)
        content = log.read_text(errors="replace")
        if f"CREATE_ZINC_WORLD seed={args.seed} disabled={str(disabled).lower()}" not in content:
            raise RuntimeError(f"The world did not use the requested seed or Zinc setting: {log}.")
        rows = sorted((int(x), int(y), int(z), item) for x, y, z, item in BLOCK.findall(content))
        ores = [item for *_, item in rows if item.startswith("create:")]
        if bool(ores) == disabled:
            raise RuntimeError(f"Unexpected Create material count {len(ores)} with disabled={disabled}.")
        with (output / f"zinc-worldgen-{'disabled' if disabled else 'enabled'}.csv").open("w", newline="") as target:
            writer = csv.writer(target, lineterminator="\n")
            writer.writerow(("x", "y", "z", "block"))
            writer.writerows(rows)
        capture.send(server, "stop")
        if server.wait(timeout=25):
            raise RuntimeError(f"The Java server did not shut down cleanly: {log}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--seed", type=int, default=810102)
    parser.add_argument("--chunks", type=int, default=2)
    parser.add_argument("--include-striated", action="store_true")
    parser.add_argument("--nether", action="store_true")
    parser.add_argument("--forced", action="store_true", help="capture after the original forceload command")
    parser.add_argument("--settled", action="store_true", help="generate the full sample before reading any blocks")
    parser.add_argument("--halo", type=int, default=0, help="generate surrounding chunks when settling")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    output = Path(mkdtemp(prefix="hc-java-zinc-worldgen-"))
    java_home = os.environ.get("JAVA_HOME")
    java = str(Path(java_home) / "bin/java") if java_home else "java"
    print(output, flush=True)
    capture.prepare(args.checkout, output, args.offline)
    for disabled in (False, True):
        record(args.checkout, output, java, args, disabled)


if __name__ == "__main__":
    main()
