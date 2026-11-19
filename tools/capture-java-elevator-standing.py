#!/usr/bin/env python3
"""Record two real Java Create clients standing on the elevator at normal tick rate."""

import argparse
from contextlib import ExitStack
import csv
import os
from pathlib import Path
import re
import socket
import subprocess
from tempfile import mkdtemp
import time


ROLES = ("ParityHost", "ParityGuest")
TRACE = re.compile(r"LIVE_ELEVATOR (\d+,[^\r\n\x1b]+)")
COLUMNS = ("tick", "player", "cabin_y", "x", "y", "z", "grounded", "mounted", "flying",
           "indicator", "indicator_target", "height_above_deck")
GRADLE_EXPORT = """
gradle.projectsEvaluated {
    rootProject.tasks.register("elevatorRunClasspath") {
        doLast {
            ["client", "server"].each { name ->
                def task = rootProject.tasks.getByName("run" + name.capitalize())
                new File(System.getenv("CREATE_ELEVATOR_RUN_FILES"), name + ".classpath").text =
                    task.classpathProvider.files.collect { it.absolutePath }.join(File.pathSeparator)
            }
        }
    }
}
"""


def prepare(checkout, output, offline):
    init = output / "classpath.gradle"
    init.write_text(GRADLE_EXPORT)
    args = [str(checkout / "gradlew"), "--console=plain"]
    if offline:
        args.append("--offline")
    args.extend(("-I", str(init), "classes", "prepareClientRun", "prepareServerRun", "elevatorRunClasspath"))
    with (output / "prepare.log").open("w") as log:
        subprocess.run(args, cwd=checkout, check=True, stdout=log, stderr=subprocess.STDOUT,
                       env=os.environ | {"CREATE_ELEVATOR_RUN_FILES": str(output)})


def launch(stack, checkout, output, java, mode, directory, args, jvm=()):
    moddev = checkout / "build/moddev"
    prefix = directory / "program.args"
    prefix.write_text((moddev / f"{mode}RunProgramArgs.txt").read_text() + "\n" + "\n".join(args) + "\n")
    mod_paths = os.pathsep.join(f"create%%{checkout / 'build' / subdir}"
                                for subdir in ("classes/java/main", "resources/main"))
    log_path = directory / "capture.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [java, f"@{moddev / (mode + 'RunVmArgs.txt')}", "-Xmx2G", "-Dmixin.debug.export=false",
             f"-Dfml.modFolders={mod_paths}", *jvm, "-cp", (output / f"{mode}.classpath").read_text(),
             "net.neoforged.devlaunch.Main", f"@{prefix}"],
            cwd=directory, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, text=True,
        )
    stack.callback(stop, process)
    return process, log_path


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    process.stdin.close()


def wait_for(process, log, pattern, offset=0, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if re.search(pattern, log.read_text(errors="replace")[offset:]):
            return
        if process.poll() is not None:
            raise RuntimeError(f"{log} exited {process.returncode} while waiting for {pattern!r}.")
        time.sleep(0.15)
    raise RuntimeError(f"Timed out waiting for {pattern!r} in {log}.")


def send(server, *commands):
    server.stdin.write("\n".join(commands) + "\n")
    server.stdin.flush()


def record(checkout, output, java):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    server_dir = output / "server"
    server_dir.mkdir()
    (server_dir / "eula.txt").write_text("eula=true\n")
    (server_dir / "server.properties").write_text(
        "level-type=minecraft:flat\nonline-mode=false\nserver-ip=127.0.0.1\n"
        f"server-port={port}\nspawn-protection=0\nview-distance=5\nsimulation-distance=5\n"
        'generator-settings={"layers":[{"block":"minecraft:bedrock","height":1},'
        '{"block":"minecraft:stone","height":61}],"biome":"minecraft:plains"}\n'
    )
    signal = output / "assemble"
    with ExitStack() as stack:
        server, server_log = launch(stack, checkout, output, java, "server", server_dir, (),
                                    (f"-Dparity.elevator.assemble={signal}",))
        wait_for(server, server_log, r"Done \([.0-9]+s\)!", timeout=90)
        clients = []
        for name in ROLES:
            folder = output / name
            folder.mkdir()
            (folder / "options.txt").write_text(
                "version:3955\nrenderDistance:4\nsimulationDistance:5\nmaxFps:30\n"
                "graphicsMode:0\nviewBobbing:false\nonboardAccessibility:false\n"
            )
            clients.append(launch(stack, checkout, output, java, "client", folder, (
                "--username", name, "--width", "640", "--height", "360", "--quickPlayMultiplayer",
                f"127.0.0.1:{port}",
            ), ("-Dparity.elevator.standing=true",)))
        for name in ROLES:
            wait_for(server, server_log, rf"{name} joined the game", timeout=90)
        send(server, "gamerule randomTickSpeed 0", "gamerule fallDamage false", "tick rate 20",
             "gamemode creative @a", "tp @a 11.5 98 -8.5", "forceload add 0 -16",
             "place template create:gametest/contraptions/elevator 3 96 -12", "setblock 7 98 -10 air")
        wait_for(server, server_log, "Loaded template")
        signal.touch()
        wait_for(server, server_log, "LIVE_ELEVATOR clicked")
        for process, log in clients:
            wait_for(process, log, TRACE.pattern)
        send(server, "tp ParityHost 8.5 98 -9.5", "tp ParityGuest 7.5 98 -10.5", "gamemode survival @a")
        for process, log in clients:
            wait_for(process, log, r"LIVE_ELEVATOR \d+,\w+,1\.000000000,[^,]+,2\.000100100,[^,]+,true,false,false")
        for lever, destination in ((106, "10"), (97, "1")):
            offsets = [len(log.read_text(errors="replace")) for _, log in clients]
            send(server, f"setblock 4 {lever} -10 lever[face=floor,facing=west,powered=true]")
            for (process, log), offset in zip(clients, offsets, strict=True):
                wait_for(process, log, rf"LIVE_ELEVATOR \d+,\w+,{destination}\.000000000,", offset=offset)
        send(server, "stop")
        server.wait(timeout=20)


def write_csv(output):
    with (output / "standing.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(COLUMNS)
        for role in ROLES:
            log = (output / role / "capture.log").read_text(errors="replace")
            for row in csv.reader(TRACE.findall(log)):
                height = float(row[4]) - float(row[2]) - 1
                writer.writerow((*row, f"{height:.9f}"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path, help="Pinned Java Create checkout with the live probe patch")
    parser.add_argument("--offline", action="store_true", help="Use cached Gradle dependencies")
    args = parser.parse_args()
    checkout = args.checkout.resolve(strict=True)
    parent = Path(__file__).resolve().parents[1] / ".local/elevator-service"
    parent.mkdir(parents=True, exist_ok=True)
    output = Path(mkdtemp(prefix="java-live-", dir=parent))
    java_home = os.environ.get("JAVA_HOME")
    java = str(Path(java_home) / "bin/java") if java_home else "java"
    print(f"Capturing Java clients in {output}", flush=True)
    prepare(checkout, output, args.offline)
    record(checkout, output, java)
    write_csv(output)
    print(f"Both Java clients reached both landings. Trace saved in {output / 'standing.csv'}.")


if __name__ == "__main__":
    main()
