#!/usr/bin/env python3
"""Record powered Chain Conveyor handoff after a full pinned Java server restart."""

import argparse
from contextlib import ExitStack
import csv
import importlib
import os
from pathlib import Path
import re
from shutil import copy2


capture = importlib.import_module("capture-java-elevator-standing")
finish = importlib.import_module("capture-java-large-wheel-restart").finish


def record(args, scenario):
    output = args.output / scenario
    output.mkdir()
    server_dir = output / "server"
    server_dir.mkdir()
    (server_dir / "eula.txt").write_text("eula=true\n")
    (server_dir / "server.properties").write_text(
        "level-type=minecraft:flat\nonline-mode=false\nserver-ip=127.0.0.1\n"
        "server-port=0\nspawn-protection=0\nview-distance=5\nsimulation-distance=5\n"
        "generate-structures=false\nspawn-monsters=false\n"
    )
    java_home = os.getenv("JAVA_HOME")
    java = str(Path(java_home) / "bin/java") if java_home else "java"
    rising = "-Dcreate.chain.rising=" + str(scenario == "rising_reversal").lower()
    with ExitStack() as stack:
        server, log = capture.launch(
            stack, args.checkout, args.output, java, "server", server_dir, (),
            ("-Dcreate.chain.restart=save", rising),
        )
        capture.wait_for(server, log, r"Done \([.0-9]+s\)!", timeout=90)
        capture.send(server, "gamerule randomTickSpeed 0", "forceload add 8 -10")
        capture.wait_for(server, log, r"(?i)marked.*force.?load", timeout=30)
        capture.send(server, "setblock 8 98 -10 minecraft:gold_block")
        capture.wait_for(server, log, r"CREATE_CHAIN_RESTART_SAVED", timeout=30)
        capture.send(server, "save-all flush")
        capture.wait_for(server, log, r"Saved the game", timeout=30)
        finish(server)
        copy2(log, output / "before-restart.log")
    with ExitStack() as stack:
        server, log = capture.launch(
            stack, args.checkout, args.output, java, "server", server_dir, (),
            ("-Dcreate.chain.restart=observe", rising),
        )
        capture.wait_for(server, log, r"CREATE_CHAIN_RESTART_PACKAGE 14,", timeout=90)
        finish(server)
        copy2(log, output / "after-restart.log")

    raw = "\n".join((output / name).read_text() for name in ("before-restart.log", "after-restart.log"))
    world = list(csv.reader(re.findall(r"CREATE_CHAIN_RESTART_TICK ([^\r\n]+)", raw)))
    boxes = list(csv.reader(re.findall(r"CREATE_CHAIN_RESTART_PACKAGE ([^\r\n]+)", raw)))
    expected = list(range(-1, 15))
    assert [int(row[0]) for row in world] == expected, world
    assert [int(row[0]) for row in boxes] == expected, boxes
    assert all(len(row) == 6 for row in world) and all(len(row) == 4 for row in boxes)
    origin = int(world[0][1])
    for row in world:
        row[1] = int(row[1]) - origin
    with (output / "chain-conveyor-restart-java.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("tick", "clock", "rpm_a", "rpm_b", "reverse_a", "reverse_b",
                         "owner", "path", "position"))
        writer.writerows((*state, *package[1:]) for state, package in zip(world, boxes, strict=True))
    print(f"{scenario}: {len(world)} observations including the saved snapshot", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--output", required=True, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    capture.prepare(args.checkout, args.output, args.offline)
    for scenario in ("straight", "rising_reversal"):
        record(args, scenario)


if __name__ == "__main__":
    main()
