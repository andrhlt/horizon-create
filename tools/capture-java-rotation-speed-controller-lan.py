import csv
from contextlib import ExitStack
from importlib import import_module
import os
from pathlib import Path
import re
from shutil import copytree
import socket
import sys
import time

capture = import_module("capture-java-elevator-standing")
finish = import_module("capture-java-large-wheel-restart").finish
checkout, output = map(lambda s: Path(s).resolve(), sys.argv[1:3])
java = str(Path(os.environ["JAVA_HOME"]) / "bin/java")
output.mkdir(parents=True)
capture.prepare(checkout, output, True)

def port():
    with socket.socket() as conn:
        conn.bind(("127.0.0.1", 0))
        return conn.getsockname()[1]

prepare = output / "prepare-world"
prepare.mkdir()
(prepare / "eula.txt").write_text("eula=true\n")
(prepare / "server.properties").write_text(
    f"level-type=minecraft:flat\nonline-mode=false\nserver-ip=127.0.0.1\nserver-port={port()}\n"
    "spawn-protection=0\nview-distance=5\nsimulation-distance=5\n"
    "generate-structures=false\nspawn-monsters=false\n"
)
with ExitStack() as stack:
    server, log = capture.launch(stack, checkout, output, java, "server", prepare, ())
    capture.wait_for(server, log, r"Done \([.0-9]+s\)!", timeout=90)
    capture.send(server, "forceload add 0 -16 15 -1",
                 "fill 3 100 -13 10 100 -7 minecraft:smooth_stone",
                 "setblock 6 101 -10 create:rotation_speed_controller[axis=z]",
                 "setblock 6 102 -10 create:large_cogwheel[axis=x]",
                 "setblock 6 101 -9 create:shaft[axis=z]",
                 "setblock 5 102 -10 create:creative_motor[facing=east]",
                 "gamerule spawnRadius 0", "setworldspawn 4 101 -10")
    capture.wait_for(server, log, r"Set the world spawn point", timeout=25)
    time.sleep(1)
    capture.send(server, "save-all flush")
    capture.wait_for(server, log, r"Saved the game", timeout=30)
    finish(server)

lan = port()
signals = {role: output / f"signal-{role}" for role in ("Host", "Guest")}
clients = {}
with ExitStack() as stack:
    for role in ("Host", "Guest"):
        home = output / role.lower()
        (home / "config").mkdir(parents=True)
        (home / "config/fml.toml").write_text("earlyWindowControl = false\n")
        (home / "config/flywheel-client.toml").write_text('backend = "flywheel:off"\n')
        (home / "options.txt").write_text(
            "version:3955\nrenderDistance:4\nsimulationDistance:5\n"
            "maxFps:30\nonboardAccessibility:false\nskipMultiplayerWarning:true\n"
            "pauseOnLostFocus:false\nsoundCategory_master:0.0\n"
        )
        if role == "Host":
            copytree(prepare / "world", home / "saves/ControllerLAN")
        mode = ("--quickPlaySingleplayer", "ControllerLAN") if role == "Host" else ("--quickPlayMultiplayer", f"127.0.0.1:{lan}")
        proc, log = capture.launch(
            stack, checkout, output, java, "client", home,
            ("--username", f"Controller{role}", "--width", "640", "--height", "360", *mode),
            ("-Dparity.controllerRender=true", f"-Dparity.controllerLanRole={role}", f"-Dparity.controllerLanPort={lan}",
             f"-Dparity.controllerLanSignal={signals[role]}", "-Dparity.controllerLanServer=true"),
        )
        clients[role] = (proc, log)
        if role == "Host":
            capture.wait_for(proc, log, rf"JAVA_CONTROLLER_LAN_PUBLISHED {lan} \d+", timeout=100)
        initial_rpm = "16" if role == "Host" else "0"
        capture.wait_for(proc, log, rf"JAVA_CONTROLLER_LAN_REPLICA {role} \d+ 16 {initial_rpm}\.0000", timeout=90)

    capture.wait_for(*clients["Host"], r"JAVA_CONTROLLER_LAN_FROZEN \d+", timeout=30)
    def match(role, expr, offset=0):
        proc, log = clients[role]
        capture.wait_for(proc, log, expr, offset=offset, timeout=30)
        return re.search(expr, log.read_text(errors="replace")[offset:])

    frozen = match("Host", r"JAVA_CONTROLLER_LAN_FROZEN (\d+)")[1]
    rows = []
    for turn, (role, setting) in enumerate((("Host", 64), ("Guest", -32)), 1):
        offsets = {name: len(pair[1].read_text(errors="replace")) for name, pair in clients.items()}
        temp = signals[role].with_suffix(".tmp")
        temp.write_text(f"{turn} {setting}")
        temp.rename(signals[role])
        release = match(role, rf"JAVA_CONTROLLER_LAN_RELEASE {role} (\d+) {setting}", offsets[role])
        accepted = match("Host", rf"JAVA_CONTROLLER_LAN_ACCEPT Controller{role} (\d+) {setting} (-?\d+\.\d+)", offsets["Host"])
        assert release[1] == accepted[1] == frozen and float(accepted[2]) == setting
        for recipient in ("Host", "Guest"):
            replica = match(recipient, rf"JAVA_CONTROLLER_LAN_REPLICA {recipient} (\d+) {setting} (-?\d+\.\d+)", offsets[recipient])
            rendered = match(recipient, r"JAVA_CONTROLLER_FRAME 6,z,[^,]+,[^,]+,(\d+),(\d+\.\d+),([^,]+),0\.000000,",
                             offsets[recipient] + replica.end())
            assert replica[1] == rendered[1] == frozen and float(replica[2]) == 0
            rows.append((role.lower(), recipient.lower(), setting, release[1], accepted[1], accepted[2],
                         replica[1], replica[2], rendered[1], rendered[2], rendered[3]))
    with (output / "controller-lan-java.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("actor", "recipient", "setting", "release_client_tick", "accept_server_tick", "server_output_rpm",
                         "replica_tick", "replica_rpm", "render_tick", "render_fraction", "render_time"))
        writer.writerows(rows)
    print(rows)
