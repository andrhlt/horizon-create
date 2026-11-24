#!/usr/bin/env python3
"""Verify a production Create package on a loopback two-client server."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
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
    parser.add_argument("--package", type=Path, required=True,
                        help="Production Create .hmod installed on server and both clients")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for key in ("server_binary", "client", "ctl"):
        setattr(args, key, getattr(args, key).resolve(strict=True))
    args.resources = args.resources.resolve(strict=True)
    if args.package:
        args.package = args.package.resolve(strict=True)
        if args.package.suffix != ".hmod":
            parser.error(f"package must be a .hmod file: {args.package}")
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error(f"choose a new output directory; already exists: {args.output}")
    if not args.resources.is_dir():
        parser.error(f"resources is not a directory: {args.resources}")
    manifest_path = args.server_binary.parent / "native-mods.json"
    if not manifest_path.is_file():
        parser.error(f"missing native build manifest next to server: {manifest_path}")
    native_manifest = json.loads(manifest_path.read_text())
    native_mod_ids = {mod.get("id") for mod in native_manifest.get("mods", [])}
    if "create" not in native_mod_ids or native_manifest.get("left_out"):
        parser.error("runtime must contain the production Create native module with no omitted mods")
    args.output.mkdir(parents=True)
    server_dir = args.output / "server"
    names = ("Create2172Host", "Create2172Guest")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]

    run([str(args.server_binary), "--dir", str(server_dir), "init", "--eula",
         "--world", "APP2172", "--seed", "2172", "--port", str(port),
         "--offline", "--yes", "--op", "Create2172Host"])
    package_hash = None
    if args.package:
        server_mods = server_dir / "horizon-mods"
        server_mods.mkdir(exist_ok=True)
        shutil.copy2(args.package, server_mods / args.package.name)
        (server_dir / "horizon-mods.txt").write_text("mod.create:true\n")
        package_hash = sha256(args.package)
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
            if args.package:
                client_mods = home / "horizon-mods"
                client_mods.mkdir()
                shutil.copy2(args.package, client_mods / args.package.name)
                (home / "horizon-mods.txt").write_text("mod.create:true\n")
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

        def server_command(command: str) -> str:
            result = subprocess.run(
                [str(args.server_binary), "--dir", str(server_dir), "cmd", command],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode:
                raise RuntimeError(f"server command failed: {command}\n{result.stdout}{result.stderr}")
            return result.stdout.strip()

        def client_call(control: Path, env: dict[str, str], *command: str) -> dict:
            output = run([str(args.ctl), "--socket", str(control), *command])
            replies = [json.loads(line) for line in output.splitlines()]
            if not replies or any(reply.get("ok") is False for reply in replies):
                raise RuntimeError(f"client control call failed: {command}: {replies}")
            return replies[-1]

        gameplay = {}
        if args.package:
            gameplay["give_registered_item"] = server_command(
                "/give Create2172Host create:shaft 4"
            )
            host_control, _, host_env = next(row for row in clients if row[0].name == "Create2172Host.sock")
            guest_control, _, guest_env = next(row for row in clients if row[0].name == "Create2172Guest.sock")
            gameplay["host_inventory_converged"] = wait_for(
                "host to receive four Create shafts",
                lambda: (inventory if inventory.get("counts", {}).get("create:shaft", 0) == 4 else None)
                if (inventory := client_call(host_control, host_env, "inventory")) else None,
            )
            gameplay["force_load_test_chunk"] = server_command("/forceload add 0 -1")
            gameplay["place_registered_block"] = server_command(
                "/setblock 0 64 -16 create:shaft[axis=y]"
            )
            gameplay["block_entity_before_reopen"] = server_command(
                "/data get block 0 64 -16"
            )
            gameplay["guest_block_converged"] = wait_for(
                "guest to see the placed Create shaft",
                lambda: (state if state.get("state", "").startswith("create:shaft") else None)
                if (state := client_call(guest_control, guest_env, "block", "0", "64", "-16")) else None,
            )
            gameplay["save_flush"] = server_command("/save-all flush")
            if "create:simple_kinetic" not in gameplay["block_entity_before_reopen"]:
                raise RuntimeError("Create shaft block entity did not register/save before reopen")

            for control, _, env in clients:
                subprocess.run([str(args.ctl), "--socket", str(control), "quit"], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            clients.clear()
            server.stdin.write("stop\n")
            server.stdin.flush()
            server.wait(timeout=20)

            reopen_log_path = args.output / "server-reopen.log"
            with reopen_log_path.open("w") as reopen_log:
                reopened = subprocess.Popen(
                    [str(args.server_binary), "--dir", str(server_dir), "run"],
                    stdin=subprocess.PIPE, stdout=reopen_log, stderr=subprocess.STDOUT,
                    text=True, start_new_session=True,
                )
                try:
                    wait_for("server reopen", lambda: "Done (" in reopen_log_path.read_text()
                             if reopened.poll() is None else None)
                    gameplay["block_entity_after_reopen"] = server_command(
                        "/data get block 0 64 -16"
                    )
                    if "create:simple_kinetic" not in gameplay["block_entity_after_reopen"]:
                        raise RuntimeError("Create shaft block entity was lost on save/reopen")
                    config_after_reopen = json.loads(run([
                        str(args.server_binary), "--dir", str(server_dir), "config", "--json"
                    ]))
                    gameplay["config_after_reopen"] = {
                        "server": {key: config_after_reopen.get("server", {}).get(key)
                                   for key in ("bind", "whitelist", "enforce_whitelist",
                                               "max_players", "view_distance",
                                               "simulation_distance", "online_mode")},
                        "world": {key: config_after_reopen.get("world", {}).get(key)
                                  for key in ("name", "seed", "game_mode")},
                    }
                finally:
                    if reopened.poll() is None:
                        reopened.stdin.write("stop\n")
                        reopened.stdin.flush()
                        reopened.wait(timeout=20)

        cache = server_dir / ".horizon-cache" / "mod-content"
        cache_dirs = sorted(path for path in cache.iterdir() if path.is_dir()) if cache.exists() else []
        mod_content = {}
        if args.package and cache_dirs:
            mod_content = json.loads((cache_dirs[-1] / "registries.json").read_text())
        registry_counts = {
            kind: sum(key.startswith("create:") for key in
                      mod_content.get(kind, {}).get("entries", {}))
            for kind in ("minecraft:block", "minecraft:item", "minecraft:fluid",
                         "minecraft:entity_type")
        }
        warnings_path = cache_dirs[-1] / "horizon-mod-content-warnings.txt" if cache_dirs else None
        warnings = warnings_path.read_text() if warnings_path and warnings_path.exists() else ""
        if not all(registry_counts.values()) or warnings.strip():
            raise RuntimeError(f"Create package registry load had warnings or no registrations: {registry_counts}; {warnings}")
        expected_ids = {
            "minecraft:block": "create:shaft",
            "minecraft:item": "create:shaft",
            "minecraft:fluid": "create:chocolate",
            "minecraft:entity_type": "create:package",
        }
        for kind, entry in expected_ids.items():
            if entry not in mod_content.get(kind, {}).get("entries", {}):
                raise RuntimeError(f"Create registration missing from {kind}: {entry}")
        package_copies = {
            "server": sha256(server_dir / "horizon-mods" / args.package.name),
            **{name: sha256(args.output / name / "horizon-mods" / args.package.name)
               for name in names},
        }
        if any(digest != package_hash for digest in package_copies.values()):
            raise RuntimeError(f"server/client package copies differ: {package_copies}")
        receipt = {
            "route": "supported offline localhost dedicated server",
            "bind": "127.0.0.1",
            "engine": json.loads(manifest_path.read_text()).get("horizon"),
            "native_mods": native_manifest,
            "sha256": {str(path): sha256(path) for path in
                       (args.server_binary, args.client, args.ctl, manifest_path)},
            "production_package": {
                "filename": args.package.name,
                "source": str(args.package),
                "sha256": package_hash,
                "server_copy_sha256": sha256(server_dir / "horizon-mods" / args.package.name),
                "client_copy_sha256": {
                    name: sha256(args.output / name / "horizon-mods" / args.package.name)
                    for name in names
                },
            },
            "resources": str(args.resources),
            "players": identities,
            "online_names": sorted(player["name"] for player in players["online"]),
            "registry_counts": registry_counts,
            "registry_warnings": warnings,
            "gameplay": gameplay,
            "production_package_installed": True,
            "production_package_verified": bool(gameplay and not warnings),
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
