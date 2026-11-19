#!/usr/bin/env python3
"""Capture original Create’s two live locally simulated player launches."""
import argparse
import csv
import os
from pathlib import Path
import re
from tempfile import mkdtemp
from contextlib import ExitStack
from importlib import import_module
import socket

capture = import_module("capture-java-elevator-standing")
PATTERN = re.compile(r'LIVE_EJECTOR ([^\r\n\x1b]+)')
ROLES = (("LaunchOne", -11), ("LaunchTwo", -27))


def record(checkout, output, java, elytra, flat):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    server_dir = output / 'server'
    server_dir.mkdir()
    (server_dir / 'eula.txt').write_text('eula=true\n')
    (server_dir / 'server.properties').write_text(
        'level-type=minecraft:flat\nonline-mode=false\nserver-ip=127.0.0.1\n'
        f'server-port={port}\nspawn-protection=0\nview-distance=4\nsimulation-distance=4\n'
        'allow-flight=true\nspawn-monsters=false\ngenerate-structures=false\n'
        'generator-settings={"layers":[{"block":"minecraft:bedrock","height":1},'
        '{"block":"minecraft:stone","height":61}],"biome":"minecraft:plains"}\n'
    )
    with ExitStack() as stack:
        server, server_log = capture.launch(stack, checkout, output, java, 'server', server_dir, ())
        capture.wait_for(server, server_log, r'Done \([.0-9]+s\)!', timeout=90)
        clients = []
        for name, _ in ROLES:
            folder = output / name
            folder.mkdir()
            (folder / 'options.txt').write_text(
                'version:3955\nrenderDistance:4\nsimulationDistance:4\nmaxFps:30\n'
                'graphicsMode:0\nviewBobbing:false\nonboardAccessibility:false\n'
            )
            clients.append(capture.launch(stack, checkout, output, java, 'client', folder, (
                '--username', name, '--width', '640', '--height', '360', '--quickPlayMultiplayer',
                f'127.0.0.1:{port}',
            ), ('-Dparity.ejector.player=true',)))
        for name, _ in ROLES:
            capture.wait_for(server, server_log, rf'{name} joined the game', timeout=120)
        capture.send(server, 'gamerule randomTickSpeed 0', 'gamerule doMobSpawning false', 'tick rate 20',
                     'gamemode spectator @a', 'forceload add 0 -16', 'forceload add 0 -32')
        for name, z in ROLES:
            capture.send(server, f'tp {name} 12.5 107 {z + .5}',
                         f'fill 3 103 {z - 2} 14 103 {z + 2} minecraft:smooth_stone',
                         *((f'fill 8 104 {z - 1} 13 106 {z + 1} minecraft:smooth_stone',)
                           if not flat else ()),
                         f'setblock 5 104 {z} create:weighted_ejector[facing=east]{{HorizontalDistance:4,VerticalDistance:0}}',
                         f'setblock 5 104 {z - 1} create:creative_motor[facing=south]{{ScrollValue:128}}')
        for (process, log), (_, z) in zip(clients, ROLES, strict=True):
            capture.wait_for(process, log, r'LIVE_EJECTOR [^,]+,\d+,CHARGED', timeout=60)
        if elytra:
            for (process, log), (name, z) in zip(clients, ROLES, strict=True):
                for attempt in range(4):
                    offset = len(log.read_text(errors="replace"))
                    capture.send(server, f"gamemode survival {name}",
                                 f"item replace entity {name} armor.chest with minecraft:elytra",
                                 f"tp {name} 5.5 106.5 {z + .5} 0 0")
                    try:
                        capture.wait_for(
                            process, log,
                            r"LIVE_EJECTOR [^,]+,\d+,[^,]+,3\.3062215\d+,6\.3245665\d+,[^\n]+,true,270\.0000,-35\.0000",
                            offset=offset, timeout=5,
                        )
                        break
                    except RuntimeError:
                        if attempt == 3:
                            raise
        else:
            for name, z in ROLES:
                capture.send(server, f"gamemode survival {name}", f"tp {name} 5.5 106.5 {z + .5}")
            for process, log in clients:
                capture.wait_for(process, log,
                    r"LIVE_EJECTOR [^,]+,\d+,CHARGED,4\.\d+,0\.000000000,[^\n]+,true,17\.00" if flat
                else r"LIVE_EJECTOR [^,]+,\d+,CHARGED,4\.\d+,3\.000000000,[^\n]+,true,20\.00", timeout=25)
        if flat:
            for process, log in clients:
                prior = log.stat().st_size
                capture.wait_for(process, log,
                    r"(?:LIVE_EJECTOR [^\n]+\n){6}",
                    offset=prior, timeout=10)
        capture.send(server, 'stop')
        server.wait(timeout=20)


def normalize(rows, elytra, flat):
    after = 12 if elytra else 31 if flat else 22
    for start in range(5, len(rows) - after + 1):
        if float(rows[start][6]) <= .1 or rows[start][3] != "0.500000000":
            continue
        window = rows[start - 5:start + after]
        if elytra and any(row[11:] != ["true", "270.0000", "-35.0000"] for row in window[5:]):
            continue
        tick = int(rows[start][1])
        samples = [(int(row[1]) - tick, *(row[3:] if elytra else row[3:11])) for row in window]
        if [row[0] for row in samples] == list(range(-5, after)):
            return samples
    raise RuntimeError("The original client did not record the expected consecutive player ticks.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--offline", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--elytra", action="store_true")
    mode.add_argument("--flat", action="store_true")
    args = parser.parse_args()
    checkout = args.checkout.resolve(strict=True)
    java_home = os.environ.get("JAVA_HOME")
    java = str(Path(java_home) / "bin/java") if java_home else "java"
    local = Path(__file__).resolve().parents[1] / ".local/ejector-player"
    local.mkdir(parents=True, exist_ok=True)
    output = Path(mkdtemp(prefix="java-live-", dir=local))
    print(f"Capturing original Java clients in {output}", flush=True)
    capture.prepare(checkout, output, args.offline)
    record(checkout, output, java, args.elytra, args.flat)
    raw = [list(csv.reader(PATTERN.findall((output / name / "capture.log").read_text(errors="replace"))))
           for name, _ in ROLES]
    with (output / "live.csv").open("w") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("player", "tick", "state", "x", "y", "z", "vx", "vy", "vz", "grounded", "health", "gliding", "yaw", "pitch"))
        writer.writerows(row for role in raw for row in role)
    if args.flat:
        columns = ("tick", "x", "y", "z", "vx", "vy", "vz", "grounded", "health")
        for (player, _), client in zip(ROLES, raw, strict=True):
            trace = normalize(client, False, True)
            with (output / f"{player}-flat.csv").open("w") as target:
                writer = csv.writer(target, lineterminator="\n")
                writer.writerow(columns)
                writer.writerows(trace)
            print(f"Captured {len(trace)} original flat-landing samples for {player}.")
        return
    reference = normalize(raw[0], args.elytra, False)
    if reference != normalize(raw[1], args.elytra, False):
        raise RuntimeError("The two original clients disagreed on the player launch and landing rows.")
    name = "depot-ejector-elytra-java.csv" if args.elytra else "depot-ejector-player-java.csv"
    path = output / name
    with path.open("w") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        columns = ("tick", "x", "y", "z", "vx", "vy", "vz", "grounded", "health")
        writer.writerow(columns + (("gliding", "yaw", "pitch") if args.elytra else ()))
        writer.writerows(reference)
    print(f"Both original clients recorded the same {len(reference)} player ticks in {path}.")


if __name__ == "__main__":
    main()
