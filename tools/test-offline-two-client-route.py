#!/usr/bin/env python3
"""Prove the supported pinned offline dedicated-server route with two UUIDs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(args: list[str], *, timeout: int = 30) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}{result.stderr}")
    return result.stdout


def wait_for(description: str, check, timeout: int = 45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            pass
        time.sleep(0.2)
    raise RuntimeError(f"timed out waiting for {description}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-binary", type=Path, required=True)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--ctl", type=Path, required=True)
    parser.add_argument("--resources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for key in ("server_binary", "client", "ctl"):
        setattr(args, key, getattr(args, key).resolve(strict=True))
    args.resources = args.resources.resolve(strict=True)
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error(f"choose a new output directory; already exists: {args.output}")
    if not args.resources.is_dir():
        parser.error(f"resources is not a directory: {args.resources}")
    manifest_path = args.server_binary.parent / "native-mods.json"
    if not manifest_path.is_file():
        parser.error(f"missing native build manifest next to server: {manifest_path}")
    args.output.mkdir(parents=True)
    server_dir = args.output / "server"
    names = ("Create2172Host", "Create2172Guest")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]

    run([str(args.server_binary), "--dir", str(server_dir), "init", "--eula",
         "--world", "APP2172", "--seed", "2172", "--port", str(port),
         "--offline", "--yes"])
    run([str(args.server_binary), "--dir", str(server_dir), "config", "set",
         "server.bind=127.0.0.1", "server.whitelist=true",
         "server.enforce_whitelist=true", "server.max_players=2",
         "server.view_distance=3", "server.simulation_distance=3",
         "backups.every=0"])
    for name in names:
        run([str(args.server_binary), "--dir", str(server_dir), "whitelist", "add", name])

    server_log = (args.output / "server.log").open("w")
    server = subprocess.Popen([str(args.server_binary), "--dir", str(server_dir), "run"],
                              stdin=subprocess.PIPE, stdout=server_log,
                              stderr=subprocess.STDOUT, text=True, start_new_session=True)
    clients: list[tuple[Path, Path, dict[str, str]]] = []
    try:
        wait_for("server ready", lambda: "Done (" in (args.output / "server.log").read_text()
                 if server.poll() is None else None)
        address = f"127.0.0.1:{port}"
        for name in names:
            home = args.output / name
            home.mkdir()
            control = args.output / f"{name}.sock"
            env = os.environ.copy()
            env["HORIZON_CONTROL"] = str(control)
            command = [str(args.ctl), "--socket", str(control), "--timeout", "60",
                       "launch", "--headless", "--game", str(args.client),
                       "--resources", str(args.resources), "--server", address,
                       "--name", name, "--game-dir", str(home), "--home", str(home),
                       "--player-dir", str(home / "player"), "--render-distance", "3", "--wait"]
            proc = subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True)
            clients.append((control, home, env))
            output, _ = proc.communicate(timeout=120)
            (args.output / f"{name}.launch.txt").write_text(output)
            if proc.returncode:
                raise RuntimeError(f"{name} failed to launch; see {name}.launch.txt")

        def connected_players():
            state = json.loads(run([str(args.server_binary), "--dir", str(server_dir),
                                    "players", "--json"]))
            online = state.get("online", [])
            if {player.get("name") for player in online} == set(names):
                return state
            return None

        players = wait_for("both named players connected", connected_players)
        whitelist = players.get("whitelist", {}).get("players", [])
        identities = {player["name"]: player["uuid"] for player in whitelist
                      if player.get("name") in names and player.get("uuid")}
        if set(identities) != set(names) or len(set(identities.values())) != 2:
            raise RuntimeError(f"expected two distinct whitelisted UUIDs, got {identities}")
        receipt = {
            "route": "supported offline localhost dedicated server",
            "bind": "127.0.0.1",
            "engine": json.loads(manifest_path.read_text()).get("horizon"),
            "native_mods": json.loads(manifest_path.read_text()),
            "sha256": {str(path): sha256(path) for path in
                       (args.server_binary, args.client, args.ctl, manifest_path)},
            "resources": str(args.resources),
            "players": identities,
            "online_names": sorted(player["name"] for player in players["online"]),
            "production_package_verified": False,
        }
        (args.output / "two-client-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(f"two distinct whitelisted player UUIDs joined {address}; proof: {args.output / 'two-client-proof.json'}")
    finally:
        for control, home, env in clients:
            subprocess.run([str(args.ctl), "--socket", str(control), "quit"], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if server.poll() is None:
            server.stdin.write("stop\n")
            server.stdin.flush()
            try:
                server.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(server.pid, signal.SIGTERM)
                server.wait(timeout=10)
        server_log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
