#!/usr/bin/env python3
"""Capture submitted controller parts from a hidden pinned Java client."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
import os
from pathlib import Path
import socket

from controller_render_fixture import CAMERA, FIELDS, STAGES, frames, setup, stage_commands

capture = import_module("capture-java-elevator-standing")
finish = import_module("capture-java-large-wheel-restart").finish


def record(checkout, output, java):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server_dir, client_dir = (output / name for name in ("server", "client"))
    for directory in (server_dir, client_dir):
        directory.mkdir()
    (server_dir / "eula.txt").write_text("eula=true\n")
    (server_dir / "server.properties").write_text(
        "level-type=minecraft:flat\nonline-mode=false\nserver-ip=127.0.0.1\n"
        f"server-port={port}\nspawn-protection=0\nview-distance=5\nsimulation-distance=5\n"
        "generate-structures=false\nspawn-monsters=false\n"
    )
    (client_dir / "config").mkdir()
    (client_dir / "config/fml.toml").write_text("earlyWindowControl = false\n")
    (client_dir / "config/flywheel-client.toml").write_text('backend = "flywheel:off"\n')
    (client_dir / "options.txt").write_text(
        "version:3955\nrenderDistance:4\nsimulationDistance:5\n"
        "maxFps:30\nonboardAccessibility:false\nskipMultiplayerWarning:true\npauseOnLostFocus:false\nsoundCategory_master:0.0\n"
    )
    rows = []
    with ExitStack() as stack:
        server, log = capture.launch(stack, checkout, output, java, "server", server_dir, ())
        capture.wait_for(server, log, r"Done \([.0-9]+s\)!", timeout=90)
        client, client_log = capture.launch(stack, checkout, output, java, "client", client_dir, (
            "--username", "ControllerRender", "--width", "640", "--height", "360",
            "--quickPlayMultiplayer", f"127.0.0.1:{port}",
        ), ("-Dparity.controllerRender=true",))
        capture.wait_for(server, log, "ControllerRender joined the game", timeout=90)
        capture.send(server, "forceload add 0 -16 15 -1", "time set midnight",
                     "gamemode spectator ControllerRender", f"tp ControllerRender {CAMERA}", *setup())
        for stage in STAGES:
            offset = client_log.stat().st_size
            capture.send(server, *stage_commands(stage))
            rows.extend({"stage": stage, **frame} for frame in
                        frames(client_log, "JAVA_CONTROLLER_FRAME ", offset, stage, wait_for_bracket=True))
        finish(server)
    with (output / "rotation-speed-controller-render-java.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, ("stage", *FIELDS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Captured {len(rows)} Java controller frames.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument("--output", required=True, type=lambda p: Path(p).resolve())
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    java_home = os.environ.get("JAVA_HOME")
    java = str(Path(java_home) / "bin/java") if java_home else "java"
    capture.prepare(args.checkout, args.output, args.offline)
    record(args.checkout, args.output, java)


if __name__ == "__main__":
    main()
