#!/usr/bin/env python3
"""Record the pinned Java large wheel after a full dedicated-server restart."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
import os
from pathlib import Path
import re
from shutil import copy2
from tempfile import mkdtemp

capture = import_module("capture-java-elevator-standing")
TRACE = re.compile(r"JAVA_RESTART_WHEEL (\d+);(-?\d+)")


def finish(server):
    capture.send(server, "stop")
    if server.wait(timeout=25):
        raise RuntimeError("The original Java server exited unsuccessfully.")


def run(checkout, output, java, warmup):
    server_dir = output / "server"
    server_dir.mkdir()
    (server_dir / "eula.txt").write_text("eula=true\n")
    (server_dir / "server.properties").write_text(
        "level-type=minecraft:flat\nonline-mode=false\nserver-ip=127.0.0.1\n"
        "server-port=0\nspawn-protection=0\nview-distance=5\nsimulation-distance=5\n"
        'generator-settings={"layers":[{"block":"minecraft:bedrock","height":1},'
        '{"block":"minecraft:stone","height":61}],"biome":"minecraft:plains"}\n'
    )
    with ExitStack() as first:
        server, log = capture.launch(first, checkout, output, java, "server", server_dir, ())
        capture.wait_for(server, log, r"Done \([.0-9]+s\)!", timeout=90)
        capture.send(server, "gamerule randomTickSpeed 0", "forceload add 0 -16")
        capture.wait_for(server, log, r"(?i)marked.*force.?load", timeout=30)
        capture.send(server, "place template create:gametest/fluids/large_waterwheel 3 96 -12", "save-all flush")
        capture.wait_for(server, log, r"Loaded template", timeout=30)
        capture.wait_for(server, log, r"Saved the game", timeout=30)
        finish(server)
        copy2(log, output / "before-restart.log")
    with ExitStack() as second:
        server, log = capture.launch(
            second, checkout, output, java, "server", server_dir, (),
            (f"-Dparity.largeWheel.restartWarmup={warmup}",),
        )
        capture.wait_for(server, log, r"JAVA_RESTART_WHEEL 61;", timeout=90)
        rows = TRACE.findall(log.read_text(errors="replace"))
        if [int(tick) for tick, _ in rows] != list(range(62)):
            raise RuntimeError("The Java restart did not record all 62 consecutive ticks.")
        with (output / "large-waterwheel-restart.csv").open("w", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(("tick", "flow"))
            writer.writerows(rows)
        finish(server)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    output = Path(mkdtemp(prefix="hc-java-wheel-restart-"))
    java_home = os.environ.get("JAVA_HOME")
    java = str(Path(java_home) / "bin/java") if java_home else "java"
    print(f"Capturing original Java server restart in {output}", flush=True)
    capture.prepare(args.checkout, output, args.offline)
    run(args.checkout, output, java, args.warmup)
    print(f"Saved the Java restart trace in {output / 'large-waterwheel-restart.csv'}.")


if __name__ == "__main__":
    main()
