#!/usr/bin/env python3
"""Capture signed and zero controller targets across a cold Java server reopen."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
import os
from pathlib import Path
import re
from shutil import copy2

capture = import_module("capture-java-elevator-standing")
finish = import_module("capture-java-large-wheel-restart").finish
COLUMNS = ("tick", "case", "setting", "controller_rpm", "cog_rpm", "shaft_rpm", "cog_shaft_rpm", "motor_rpm")
TRACE = re.compile(r"CREATE_CONTROLLER_RESTART ([-0-9,.]+)\n")


def record(checkout, output, java):
    server_dir = output / "server"
    server_dir.mkdir()
    (server_dir / "eula.txt").write_text("eula=true\n")
    (server_dir / "server.properties").write_text(
        "level-type=minecraft:flat\nonline-mode=false\nserver-ip=127.0.0.1\n"
        "server-port=0\nspawn-protection=0\nview-distance=5\nsimulation-distance=5\n"
        "generate-structures=false\nspawn-monsters=false\n"
    )
    rows = []
    for phase, last in (("save", -1), ("observe", 6)):
        with ExitStack() as stack:
            server, log = capture.launch(
                stack, checkout, output, java, "server", server_dir, (),
                (f"-Dcreate.controller.restart={phase}",),
            )
            capture.wait_for(server, log, r"Done \([.0-9]+s\)!", timeout=90)
            if phase == "save":
                capture.send(server, "forceload add 0 -16 31 -1", "setblock 4 98 -10 minecraft:gold_block")
            capture.wait_for(server, log, rf"CREATE_CONTROLLER_RESTART {last},3,", timeout=90)
            if phase == "save":
                capture.send(server, "save-all flush")
                capture.wait_for(server, log, r"Saved the game", timeout=30)
            finish(server)
            copy2(log, output / f"{phase}.log")
            rows.extend(TRACE.findall(log.read_text(errors="replace")))

    expected = [(tick, case) for tick in range(-1, 7) for case in range(4)]
    parsed = [row.split(",") for row in rows]
    assert [tuple(map(int, row[:2])) for row in parsed] == expected, parsed
    with (output / "rotation-speed-controller-reopen-java.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(COLUMNS)
        writer.writerows(parsed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--output", required=True, type=lambda path: Path(path).resolve())
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    java_home = os.environ.get("JAVA_HOME")
    java = str(Path(java_home) / "bin/java") if java_home else "java"
    capture.prepare(args.checkout, args.output, args.offline)
    record(args.checkout, args.output, java)


if __name__ == "__main__":
    main()
