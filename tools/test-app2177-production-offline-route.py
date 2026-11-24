#!/usr/bin/env python3
"""Prove the supported pinned offline dedicated-server route with two UUIDs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time


def tree_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(file.relative_to(path).as_posix().encode())
        with file.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


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
    parser.add_argument("--launcher", type=Path, required=True)
    parser.add_argument("--content-source", type=Path, required=True,
                        help="APP-2177 Create content hmod merged into the native create package")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for key in ("server_binary", "client", "ctl"):
        setattr(args, key, getattr(args, key).resolve(strict=True))
    args.resources = args.resources.resolve(strict=True)
    args.launcher = args.launcher.resolve(strict=True)
    args.content_source = args.content_source.resolve(strict=True)
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
        parser.error("runtime must contain the combined production Create native package with no omitted mods")
    args.output.mkdir(parents=True)
    server_dir = args.output / "server"
    server_dir.mkdir(parents=True)
    # Prepared engine resources are immutable inputs. Link the pinned set into
    # this isolated server directory while keeping the world, config and logs
    # entirely under --output.
    (server_dir / "resources").symlink_to(args.resources, target_is_directory=True)
    names = ("Create2177Host", "Create2177Guest")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]

    run([str(args.server_binary), "--dir", str(server_dir), "init", "--eula",
         "--world", "APP2177", "--seed", "2172", "--port", str(port),
         "--offline", "--yes", "--op", "Create2177Host"])
    package_hash = tree_sha256(args.server_binary.parent / "horizon-native-mods" / "create")
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
                       "launch", "--offscreen", "--game", str(args.client),
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

        def client_call(client, *command):
            control, _, env = client
            result = subprocess.run(
                [str(args.ctl), "--socket", str(control), *map(str, command)],
                env=env, capture_output=True, text=True, timeout=15,
            )
            if result.returncode:
                raise RuntimeError(f"client command failed: {command}\n{result.stdout}{result.stderr}")
            rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            if not rows or rows[-1].get("ok") is False:
                raise RuntimeError(f"client command returned no successful result: {command} {rows}")
            return rows[-1]

        gameplay = {}
        if "create" in native_mod_ids:
            gameplay["give_registered_item"] = server_command(
                "/give Create2177Host create:shaft 4"
            )
            gameplay["force_load_test_chunk"] = server_command("/forceload add 0 -1")
            server_command("/forceload add 1 -1")
            server_command("/forceload add 1 -2")
            server_command("/forceload add 2 -3")
            server_command("/forceload add 3 3")
            server_command("/tick freeze")
            for command in (
                "/setblock -1 64 -16 create:creative_motor[facing=east]",
                "/setblock 0 64 -16 create:shaft[axis=x]",
                "/setblock 1 64 -16 create:clutch[axis=x,powered=false]",
                "/setblock 2 64 -16 create:shaft[axis=x]",
                "/setblock 3 64 -16 create:gearshift[axis=x,powered=false]",
                "/setblock 4 64 -16 create:shaft[axis=x]",
                "/data merge block -1 64 -16 {ScrollValue:32}",
                "/tick step 10",
            ):
                server_command(command)
            gameplay["forward_motor"] = server_command("/data get block -1 64 -16")
            gameplay["forward_shaft"] = server_command("/data get block 0 64 -16")
            gameplay["clutch_running"] = server_command("/data get block 2 64 -16")
            gameplay["gearshift_forward"] = server_command("/data get block 4 64 -16")
            if any("Speed: 32.0f" not in gameplay[key] for key in (
                "forward_motor", "forward_shaft", "clutch_running", "gearshift_forward"
            )):
                raise RuntimeError(f"Forward transmission failed: {gameplay}")
            server_command("/setblock 1 64 -16 create:clutch[axis=x,powered=true]")
            time.sleep(0.25)
            gameplay["client_clutch_powered"] = []
            for control, _, env in clients:
                observed = subprocess.run(
                    [str(args.ctl), "--socket", str(control), "block", "1", "64", "-16"],
                    env=env, capture_output=True, text=True, timeout=15,
                )
                if observed.returncode:
                    raise RuntimeError(f"client clutch query failed: {observed.stdout}{observed.stderr}")
                state = json.loads(observed.stdout.splitlines()[-1])
                gameplay["client_clutch_powered"].append(state)
                if "powered=true" not in state.get("state", ""):
                    raise RuntimeError(f"client missed clutch power change: {state}")
            gameplay["clutch_stopped"] = server_command("/data get block 2 64 -16")
            if "Speed: 0.0f" not in gameplay["clutch_stopped"]:
                raise RuntimeError(f"Powered clutch did not stop its output: {gameplay['clutch_stopped']}")
            server_command("/setblock 1 64 -16 create:clutch[axis=x,powered=false]")
            server_command("/setblock 3 64 -16 create:gearshift[axis=x,powered=true]")
            server_command("/tick step 10")
            time.sleep(0.25)
            gameplay["gearshift_reverse"] = server_command("/data get block 4 64 -16")
            if "Speed: -32.0f" not in gameplay["gearshift_reverse"]:
                raise RuntimeError(f"Powered gearshift did not reverse its output: {gameplay['gearshift_reverse']}")
            # Fan terminal, item movement, signed airflow, and stop behavior.
            for command in (
                "/forceload add 70 -16",
                "/forceload add 70 -20",
                "/forceload add 80 -20",
                "/setblock 69 63 -16 minecraft:stone",
                "/setblock 70 63 -16 minecraft:stone",
                "/setblock 71 63 -16 minecraft:stone",
                "/setblock 72 63 -16 minecraft:stone",
                "/setblock 73 63 -16 minecraft:stone",
                "/setblock 74 63 -16 minecraft:stone",
                "/setblock 72 64 -16 minecraft:air",
                "/setblock 73 64 -16 minecraft:air",
                "/setblock 74 64 -16 minecraft:air",
                "/setblock 75 64 -16 minecraft:stone",
                "/setblock 69 64 -16 create:creative_motor[facing=east]",
                "/setblock 70 64 -16 create:shaft[axis=x]",
                "/setblock 71 64 -16 create:encased_fan[facing=east]",
                "/data merge block 69 64 -16 {ScrollValue:32}",
                "/tick step 5",
            ):
                server_command(command)
            gameplay["fan_forward_motor"] = server_command("/data get block 69 64 -16")
            gameplay["fan_forward_state"] = server_command("/data get block 71 64 -16")
            if ("Speed: 32.0f" not in gameplay["fan_forward_motor"]
                    or "Speed: 32.0f" not in gameplay["fan_forward_state"]):
                raise RuntimeError(f"Powered Fan did not join its kinetic source: {gameplay['fan_forward_state']}")
            server_command('/summon minecraft:item 73.5 64.5 -15.5 {Item:{id:"minecraft:stone",count:1},NoGravity:1b,Tags:["app2177_air"]}')
            server_command("/tick step 20")
            gameplay["fan_item_forward_motion"] = server_command(
                "/data get entity @e[type=minecraft:item,tag=app2177_air,limit=1] Motion"
            )
            motion_number = r"([-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?)d?"
            match = re.search(r"(?:Motion:\s*)?\[\s*" + motion_number, gameplay["fan_item_forward_motion"])
            if match is None or float(match.group(1)) <= 0:
                fan_state = server_command("/data get block 71 64 -16")
                item_state = server_command("/data get entity @e[type=minecraft:item,tag=app2177_air,limit=1]")
                facing_state = server_command("/execute if block 71 64 -16 create:encased_fan[facing=east] run say fan-facing-east")
                raise RuntimeError(f"Powered Fan did not move an item along its facing: motion={gameplay['fan_item_forward_motion']}; fan={fan_state}; item={item_state}; facing={facing_state}")
            server_command('/summon minecraft:item 70.75 64.5 -15.5 {Item:{id:"minecraft:stone",count:1},NoGravity:1b,Tags:["app2177_reverse"]}')
            server_command("/data merge block 69 64 -16 {ScrollValue:-32}")
            server_command("/tick step 20")
            gameplay["fan_reverse_state"] = server_command("/data get block 71 64 -16")
            gameplay["fan_item_reverse_motion"] = server_command(
                "/data get entity @e[type=minecraft:item,tag=app2177_reverse,limit=1] Motion"
            )
            match = re.search(r"(?:Motion:\s*)?\[\s*" + motion_number, gameplay["fan_item_reverse_motion"])
            if ("Speed: -32.0f" not in gameplay["fan_reverse_state"]
                    or match is None or float(match.group(1)) >= 0):
                raise RuntimeError(f"Reversed Fan failed to reverse item airflow: {gameplay['fan_reverse_state']} {gameplay['fan_item_reverse_motion']}")
            server_command("/data merge block 69 64 -16 {ScrollValue:0}")
            server_command("/tick step 5")
            gameplay["fan_stopped_state"] = server_command("/data get block 71 64 -16")
            if "Speed: 0.0f" not in gameplay["fan_stopped_state"]:
                raise RuntimeError(f"Fan did not stop when its motor stopped: {gameplay['fan_stopped_state']}")

            # A guaranteed splashing recipe exercises catalyst detection, the
            # persisted item timer, recipe lookup, and result replacement.
            for command in (
                "/setblock 70 63 -20 minecraft:stone",
                "/setblock 71 63 -20 minecraft:stone",
                "/setblock 72 63 -20 minecraft:stone",
                "/setblock 73 63 -20 minecraft:stone",
                "/setblock 74 63 -20 minecraft:stone",
                "/setblock 72 64 -20 minecraft:air",
                "/setblock 73 64 -20 minecraft:air",
                "/setblock 75 64 -20 minecraft:stone",
                "/setblock 70 64 -20 create:creative_motor[facing=east]",
                "/setblock 71 64 -20 create:encased_fan[facing=east]",
                "/data merge block 70 64 -20 {ScrollValue:32}",
                "/setblock 74 64 -20 minecraft:water",
            ):
                server_command(command)
            gameplay["fan_catalyst_state"] = server_command(
                "/execute if block 74 64 -20 minecraft:water run say app2177-water-present"
            )
            if "app2177-water-present" not in gameplay["fan_catalyst_state"]:
                raise RuntimeError(f"Could not place the water catalyst: {gameplay['fan_catalyst_state']}")
            server_command('/summon minecraft:item 74.5 64.5 -19.5 {Item:{id:"create:crushed_raw_zinc",count:1},NoGravity:1b,Tags:["app2177_process"]}')
            # Let the dedicated server run the normal BE scheduler for the
            # full persisted processing interval; `/tick step` advances world
            # time but does not drive modded kinetic BE callbacks in this
            # engine build.
            server_command("/tick unfreeze")
            time.sleep(9)
            server_command("/tick freeze")
            gameplay["fan_processing_result"] = server_command(
                "/data get entity @e[type=minecraft:item,tag=app2177_process,limit=1] Item.id"
            )
            if "create:zinc_nugget" not in gameplay["fan_processing_result"]:
                fan_state = server_command("/data get block 71 64 -20")
                item_state = server_command("/data get entity @e[type=minecraft:item,tag=app2177_process,limit=1]")
                raise RuntimeError(f"Fan splashing recipe did not process its representative item: result={gameplay['fan_processing_result']}; fan={fan_state}; item={item_state}")

            # A supported Nozzle follows the Fan's effective signed speed.
            for command in (
                "/setblock 80 63 -20 minecraft:stone",
                "/setblock 81 63 -20 minecraft:stone",
                "/setblock 82 63 -20 minecraft:stone",
                "/setblock 83 64 -20 minecraft:air",
                "/setblock 84 64 -20 minecraft:air",
                "/setblock 85 64 -20 minecraft:air",
                "/setblock 85 65 -20 minecraft:air",
                "/setblock 85 64 -19 minecraft:air",
                "/setblock 85 64 -22 minecraft:air",
                "/setblock 85 65 -19 minecraft:air",
                "/setblock 85 65 -22 minecraft:air",
                "/setblock 80 64 -20 create:creative_motor[facing=east]",
                "/setblock 81 64 -20 create:encased_fan[facing=east]",
                "/setblock 82 64 -20 create:nozzle[facing=east]",
                "/data merge block 80 64 -20 {ScrollValue:32}",
                "/tp Create2177Host 85 64 -19.5",
                "/tp Create2177Guest 60 64 -19.5",
            ):
                server_command(command)
            server_command("/tick unfreeze")
            time.sleep(0.5)
            server_command("/tick freeze")
            gameplay["nozzle_push_host_state"] = server_command("/data get entity Create2177Host")
            gameplay["nozzle_push_fan_state"] = server_command("/data get block 81 64 -20")
            if "Speed: 32.0f" not in gameplay["nozzle_push_fan_state"]:
                raise RuntimeError(f"Nozzle push check has no positive Fan RPM: {gameplay['nozzle_push_fan_state']}")
            gameplay["nozzle_push_host_state"] = server_command("/data get entity Create2177Host")
            gameplay["nozzle_push_host_motion"] = server_command("/data get entity Create2177Host Motion")
            match = re.search(r"Pos:\s*\[\s*" + motion_number, gameplay["nozzle_push_host_state"])
            if match is None or float(match.group(1)) <= 85.5:
                nozzle_state = server_command("/data get block 82 64 -20")
                raise RuntimeError(f"Powered Nozzle did not push host: {gameplay['nozzle_push_host_state']}; nozzle={nozzle_state}")
            # Move the guest into the same axial lane after isolating the host.
            server_command("/tp Create2177Host 60 64 -19.5")
            server_command("/tp Create2177Guest 85 64 -19.5")
            server_command("/data merge entity Create2177Guest {Motion:[0.0d,0.0d,0.0d]}")
            server_command("/tick unfreeze")
            time.sleep(0.25)
            server_command("/tick freeze")
            gameplay["nozzle_push_guest_state"] = server_command("/data get entity Create2177Guest")
            gameplay["nozzle_push_guest_motion"] = server_command("/data get entity Create2177Guest Motion")
            match = re.search(r"Pos:\s*\[\s*" + motion_number, gameplay["nozzle_push_guest_state"])
            if match is None or float(match.group(1)) <= 85.5:
                raise RuntimeError(f"Powered Nozzle did not push guest: {gameplay['nozzle_push_guest_state']}")
            server_command("/tp Create2177Host 85 64 -19.5")
            server_command("/tp Create2177Guest 60 64 -19.5")
            server_command("/data merge entity Create2177Host {Motion:[0.0d,0.0d,0.0d]}")
            server_command("/data merge block 80 64 -20 {ScrollValue:-32}")
            server_command("/tick unfreeze")
            time.sleep(0.5)
            server_command("/tick freeze")
            gameplay["nozzle_pull_fan_state"] = server_command("/data get block 81 64 -20")
            if "Speed: -32.0f" not in gameplay["nozzle_pull_fan_state"]:
                raise RuntimeError(f"Nozzle pull check has no reversed Fan RPM: {gameplay['nozzle_pull_fan_state']}")
            gameplay["nozzle_pull_host_state"] = server_command("/data get entity Create2177Host")
            gameplay["nozzle_pull_host_motion"] = server_command("/data get entity Create2177Host Motion")
            match = re.search(r"Pos:\s*\[\s*" + motion_number, gameplay["nozzle_pull_host_state"])
            if match is None or float(match.group(1)) >= 85.5:
                raise RuntimeError(f"Reversed Nozzle did not pull host: {gameplay['nozzle_pull_host_state']}")
            server_command("/tp Create2177Host 60 64 -19.5")
            server_command("/tp Create2177Guest 85 64 -19.5")
            server_command("/data merge entity Create2177Guest {Motion:[0.0d,0.0d,0.0d]}")
            server_command("/tick unfreeze")
            time.sleep(0.25)
            server_command("/tick freeze")
            gameplay["nozzle_pull_guest_state"] = server_command("/data get entity Create2177Guest")
            gameplay["nozzle_pull_guest_motion"] = server_command("/data get entity Create2177Guest Motion")
            match = re.search(r"Pos:\s*\[\s*" + motion_number, gameplay["nozzle_pull_guest_state"])
            if match is None or float(match.group(1)) >= 85.5:
                raise RuntimeError(f"Reversed Nozzle did not pull guest: {gameplay['nozzle_pull_guest_state']}")
            gameplay["nozzle_supported_state"] = server_command("/data get block 82 64 -20")
            if "create:nozzle" not in gameplay["nozzle_supported_state"]:
                raise RuntimeError(f"Nozzle failed to remain attached to its Fan: {gameplay['nozzle_supported_state']}")
            for control, _, env in clients:
                observed = subprocess.run(
                    [str(args.ctl), "--socket", str(control), "block", "82", "64", "-20"],
                    env=env, capture_output=True, text=True, timeout=15,
                )
                if observed.returncode:
                    raise RuntimeError(f"Nozzle client query failed: {observed.stdout}{observed.stderr}")
                state = json.loads(observed.stdout.splitlines()[-1])
                gameplay.setdefault("client_nozzle_observations", []).append(state)
                if "create:nozzle" not in state.get("state", ""):
                    raise RuntimeError(f"Host/guest did not converge on Nozzle state: {state}")
            server_command("/data merge block 80 64 -20 {ScrollValue:32}")
            server_command("/tick step 10")

            server_command("/setblock 3 64 -16 create:gearshift[axis=x,powered=false]")
            server_command("/tick step 10")
            server_command("/setblock 5 64 -16 create:creative_motor[facing=west]")
            time.sleep(0.25)
            gameplay["opposing_source_join"] = server_command("/execute if block 5 64 -16 minecraft:air run say conflicting-source-rejected")
            gameplay["source_after_rejection"] = server_command("/data get block 0 64 -16")
            if ("conflicting-source-rejected" not in gameplay["opposing_source_join"]
                    or "Speed: 32.0f" not in gameplay["source_after_rejection"]):
                raise RuntimeError(f"Conflicting source was not rejected without disturbing the live network: {gameplay}")
            for command in (
                "/setblock 6 64 -16 create:creative_motor[facing=east]",
                "/setblock 7 64 -16 create:shaft[axis=x]",
                "/setblock 8 64 -16 create:large_cogwheel[axis=x]",
                "/setblock 8 65 -15 create:cogwheel[axis=x]",
                "/setblock 9 65 -15 create:shaft[axis=x]",
                "/data merge block 6 64 -16 {ScrollValue:32}",
                "/tick step 10",
            ):
                server_command(command)
            gameplay["ratio_large"] = server_command("/data get block 8 64 -16")
            gameplay["ratio_small"] = server_command("/data get block 8 65 -15")
            gameplay["ratio_output"] = server_command("/data get block 9 65 -15")
            if "Speed: -64.0f" not in gameplay["ratio_output"]:
                raise RuntimeError(f"Large-to-small cogwheel ratio failed: {gameplay['ratio_output']}")
            # Exercise the standalone adapter types and chain signal sampling
            # in the same loaded world before save/reopen.
            for command in (
                "/setblock 14 64 -16 create:creative_motor[facing=east]",
                "/setblock 15 64 -16 create:shaft[axis=x]",
                "/setblock 16 64 -16 create:gearbox[axis=y]",
                "/setblock 17 64 -16 create:shaft[axis=x]",
                "/setblock 18 64 -16 create:flywheel[axis=x]",
                "/data merge block 14 64 -16 {ScrollValue:32}",
                "/setblock 22 64 -16 create:creative_motor[facing=east]",
                "/setblock 23 64 -16 create:adjustable_chain_gearshift[axis=x,part=start,axis_along_first=true,powered=false]",
                "/setblock 23 65 -16 create:adjustable_chain_gearshift[axis=x,part=end,axis_along_first=true,powered=false]",
                "/setblock 24 65 -16 create:shaft[axis=x]",
                "/data merge block 22 64 -16 {ScrollValue:32}",
                "/setblock 23 65 -15 minecraft:redstone_block",
                "/setblock 28 64 -16 create:creative_motor[facing=east]",
                "/setblock 29 64 -16 create:shaft[axis=x]",
                "/setblock 30 64 -16 create:rotation_speed_controller[axis=x]",
                "/setblock 30 65 -16 create:large_cogwheel[axis=z]",
                "/setblock 30 65 -15 create:shaft[axis=z]",
                "/data merge block 28 64 -16 {ScrollValue:32}",
                "/setblock 28 64 -30 create:creative_motor[facing=east]",
                "/setblock 29 64 -30 create:shaft[axis=x]",
                "/setblock 30 64 -30 create:sequenced_gearshift[axis=x,state=0,vertical=false]",
                "/setblock 31 64 -30 create:shaft[axis=x]",
                "/data merge block 28 64 -30 {ScrollValue:32}",
                "/data merge block 30 64 -30 {Instructions:[{Type:\"TURN_ANGLE\",Modifier:\"BACK\",Value:360},{Type:\"END\",Modifier:\"FORWARD\",Value:0}],InstructionIndex:-1,InstructionDuration:-1,Timer:0,PrevPowered:0}",
                "/setblock 40 63 -39 create:creative_motor[facing=up]",
                "/data merge block 40 63 -39 {ScrollValue:32}",
                "/setblock 40 64 -39 create:cogwheel[axis=y]",
                "/setblock 41 64 -39 create:cogwheel[axis=y]",
                "/setblock 40 64 -38 create:cogwheel[axis=y]",
                "/setblock 41 64 -38 create:cogwheel[axis=y]",
                "/setblock 35 64 -16 create:creative_motor[facing=east]",
                "/setblock 36 64 -16 create:gearbox[axis=z]",
                "/setblock 37 64 -16 create:gearbox[axis=z]",
                "/setblock 37 65 -16 create:gearbox[axis=z]",
                "/setblock 36 65 -16 create:gearbox[axis=z]",
                "/data merge block 35 64 -16 {ScrollValue:32}",
            ):
                server_command(command)
            # Exercise both actual client menus. The controller slider is the
            # sole source of its target; the sequencer row button is the sole
            # source of its reverse instruction.
            server_command("/tick unfreeze")
            time.sleep(0.5)
            server_command("/tp Create2177Host 30.5 64 -18.5")
            client_call(clients[0], "wait-ready")
            client_call(clients[0], "interact", "30", "64", "-16", "north")
            controller_screen = client_call(clients[0], "screen")
            controller_buttons = controller_screen.get("buttons", [])
            controller_widget = next((button for button in controller_buttons
                                      if button.get("label", "").startswith("Rotation speed:")), None)
            if controller_widget is None:
                raise RuntimeError(f"Rotation Speed Controller editor did not open: {controller_screen}")
            controller_x = controller_widget["x"] + controller_widget["w"] * (320.0 / 512.0)
            controller_y = controller_widget["y"] + controller_widget["h"] / 2
            controller_click = client_call(clients[0], "click-at", controller_x, controller_y)
            time.sleep(0.5)
            server_command("/tick freeze")
            gameplay["controller_ui_state"] = server_command("/data get block 30 64 -16")
            if "ScrollValue: 64" not in gameplay["controller_ui_state"]:
                raise RuntimeError(
                    f"Controller editor did not save the selected target: {gameplay['controller_ui_state']}; "
                    f"screen={controller_screen}; click={controller_click}; at=({controller_x},{controller_y})"
                )
            client_call(clients[0], "key", "esc", "tap")
            server_command("/tick unfreeze")
            time.sleep(0.5)
            server_command("/tp Create2177Host 30.5 64 -32.5")
            client_call(clients[0], "wait-ready")
            client_call(clients[0], "interact", "30", "64", "-30", "north")
            sequencer_screen = client_call(clients[0], "screen")
            sequencer_widget = next((button for button in sequencer_screen.get("buttons", [])
                                     if button.get("label", "").startswith("0: Turn -90")), None)
            if sequencer_widget is None:
                raise RuntimeError(f"Sequenced Gearshift editor did not open: {sequencer_screen}")
            client_call(clients[0], "click-at", sequencer_widget["x"] + sequencer_widget["w"] / 2 + 25.5,
                        sequencer_widget["y"] + sequencer_widget["h"] / 2)
            time.sleep(0.5)
            server_command("/tick freeze")
            gameplay["sequencer_ui_state"] = server_command("/data get block 30 64 -30")
            if 'Modifier: "BACK"' not in gameplay["sequencer_ui_state"]:
                raise RuntimeError(f"Sequencer editor did not save its selected instruction: {gameplay['sequencer_ui_state']}")
            client_call(clients[0], "key", "esc", "tap")
            server_command("/data merge block 30 64 -30 {Instructions:[{Type:\"TURN_ANGLE\",Modifier:\"BACK\",Value:360},{Type:\"END\",Modifier:\"FORWARD\",Value:0}],InstructionIndex:-1,InstructionDuration:-1,Timer:0,PrevPowered:0}")
            server_command("/setblock 30 65 -30 minecraft:redstone_block")
            server_command("/tick step 20")
            gameplay["consistent_loop_output"] = server_command("/data get block 41 64 -38")
            if "Speed: 32.0f" not in gameplay["consistent_loop_output"]:
                raise RuntimeError(f"Consistent cogwheel loop did not transmit: {gameplay['consistent_loop_output']}")
            gameplay["gearbox_output"] = server_command("/data get block 17 64 -16")
            gameplay["flywheel_speed"] = server_command("/data get block 18 64 -16")
            gameplay["chain_signal_state"] = server_command("/data get block 23 65 -16")
            gameplay["chain_output"] = server_command("/data get block 24 65 -16")
            gameplay["controller_state"] = server_command("/data get block 30 64 -16")
            gameplay["controller_output"] = server_command("/data get block 30 65 -15")
            gameplay["sequencer_state"] = server_command("/data get block 30 64 -30")
            gameplay["sequencer_output"] = server_command("/data get block 31 64 -30")
            gameplay["gearbox_loop_conflict"] = server_command("/data get block 37 65 -16")
            if "Speed: -32.0f" not in gameplay["gearbox_output"]:
                raise RuntimeError(f"Gearbox did not transmit signed RPM: {gameplay['gearbox_output']}")
            if "Speed: -32.0f" not in gameplay["flywheel_speed"]:
                raise RuntimeError(f"Flywheel did not join the gearbox output: {gameplay['flywheel_speed']}")
            if "Signal: 15" not in gameplay["chain_signal_state"] or "Speed: 16.0f" not in gameplay["chain_output"]:
                raise RuntimeError(f"Powered chain gearshift did not sample/translate signal: {gameplay['chain_signal_state']} {gameplay['chain_output']}")
            if "Speed: 64.0f" not in gameplay["controller_output"]:
                raise RuntimeError(f"Rotation Speed Controller missed its configured RPM: {gameplay['controller_state']} {gameplay['controller_output']}")
            if "InstructionIndex: 0" not in gameplay["sequencer_state"] or "Speed: -32.0f" not in gameplay["sequencer_output"]:
                raise RuntimeError(f"Powered Sequenced Gearshift did not run its saved reverse program: {gameplay['sequencer_state']} {gameplay['sequencer_output']}")
            if "Speed: 0.0f" not in gameplay["gearbox_loop_conflict"]:
                raise RuntimeError(f"Inconsistent four-Gearbox loop remained driven: {gameplay['gearbox_loop_conflict']}")
            gameplay["client_clutch_observations"] = []
            for control, _, env in clients:
                observed = subprocess.run(
                    [str(args.ctl), "--socket", str(control), "block", "1", "64", "-16"],
                    env=env, capture_output=True, text=True, timeout=15,
                )
                if observed.returncode:
                    raise RuntimeError(f"client block query failed: {observed.stdout}{observed.stderr}")
                state = json.loads(observed.stdout.splitlines()[-1])
                gameplay["client_clutch_observations"].append(state)
            # APP-2173's broader stress-overload fixture is validated separately.
            # Here, keep the loaded world focused on Fan/Nozzle persistence.
            server_command("/setblock 3 64 -16 create:gearshift[axis=x,powered=false]")
            time.sleep(0.25)
            gameplay["block_entity_before_reopen"] = server_command("/data get block 0 64 -16")
            gameplay["fan_before_reopen"] = server_command("/data get block 71 64 -20")
            gameplay["nozzle_before_reopen"] = server_command("/data get block 82 64 -20")
            if ("Speed: 32.0f" not in gameplay["fan_before_reopen"]
                    or "CreateNozzleRange" not in gameplay["nozzle_before_reopen"]):
                raise RuntimeError(f"Active Fan/Nozzle state was not saved: {gameplay['fan_before_reopen']} {gameplay['nozzle_before_reopen']}")
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
                    server_command("/tick freeze")
                    gameplay["block_entity_after_reopen"] = server_command(
                        "/data get block 0 64 -16"
                    )
                    gameplay["fan_after_reopen"] = server_command("/data get block 71 64 -20")
                    gameplay["nozzle_after_reopen"] = server_command("/data get block 82 64 -20")
                    gameplay["processed_item_after_reopen"] = server_command(
                        "/data get entity @e[type=minecraft:item,tag=app2177_process,limit=1] Item.id"
                    )
                    gameplay["ratio_output_after_reopen"] = server_command(
                        "/data get block 9 65 -15"
                    )
                    gameplay["controller_after_reopen"] = server_command(
                        "/data get block 30 64 -16"
                    )
                    gameplay["controller_output_after_reopen"] = server_command(
                        "/data get block 30 65 -15"
                    )
                    gameplay["sequencer_after_reopen"] = server_command(
                        "/data get block 30 64 -30"
                    )
                    gameplay["sequencer_output_after_reopen"] = server_command(
                        "/data get block 31 64 -30"
                    )
                    if ("create:simple_kinetic" not in gameplay["block_entity_after_reopen"]
                            or "Speed: 32.0f" not in gameplay["block_entity_after_reopen"]
                            or "Speed: -64.0f" not in gameplay["ratio_output_after_reopen"]
                            or "ScrollValue: 64" not in gameplay["controller_after_reopen"]
                            or "Speed: 64.0f" not in gameplay["controller_output_after_reopen"]
                            or "InstructionIndex: 0" not in gameplay["sequencer_after_reopen"]
                            or "Speed: -32.0f" not in gameplay["sequencer_output_after_reopen"]
                            or "Speed: 32.0f" not in gameplay["fan_after_reopen"]
                            or "CreateNozzleRange" not in gameplay["nozzle_after_reopen"]
                            or "create:zinc_nugget" not in gameplay["processed_item_after_reopen"]):
                        raise RuntimeError("Active transmission or geared ratio was lost on save/reopen")
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
        if "create" in native_mod_ids and cache_dirs:
            mod_content = json.loads((cache_dirs[-1] / "registries.json").read_text())
        registry_counts = {
            kind: sum(key.startswith("create:") for key in
                      mod_content.get(kind, {}).get("entries", {}))
            for kind in ("minecraft:block", "minecraft:item", "minecraft:fluid",
                         "minecraft:entity_type")
        }
        warnings_path = cache_dirs[-1] / "horizon-mod-content-warnings.txt" if cache_dirs else None
        warnings = warnings_path.read_text() if warnings_path and warnings_path.exists() else ""
        if (registry_counts["minecraft:block"] == 0 or registry_counts["minecraft:item"] == 0) or warnings.strip():
            raise RuntimeError(f"Create package registry load had warnings or no registrations: {registry_counts}; {warnings}")
        expected_ids = {
            "minecraft:block": "create:shaft",
            "minecraft:item": "create:shaft",
        }
        for kind, entry in expected_ids.items():
            if entry not in mod_content.get(kind, {}).get("entries", {}):
                raise RuntimeError(f"Create registration missing from {kind}: {entry}")
        package_dir = args.server_binary.parent / "horizon-native-mods" / "create"
        if tree_sha256(package_dir) != package_hash:
            raise RuntimeError("compiled Create native package changed during route")
        receipt = {
            "route": "supported offline localhost dedicated server",
            "bind": "127.0.0.1",
            "engine": json.loads(manifest_path.read_text()).get("horizon"),
            "native_mods": native_manifest,
            "sha256": {str(path): sha256(path) for path in
                       (args.server_binary, args.client, args.ctl, manifest_path)},
            "production_package": {
                "native_id": "create",
                "native_package_path": str(package_dir),
                "native_package_tree_sha256": package_hash,
                "source_content_hmod": str(args.content_source),
                "source_content_hmod_sha256": sha256(args.content_source),
            },
            "resources": str(args.resources),
            "launcher": {"path": str(args.launcher),
                         "version": run([str(args.launcher), "--version"]).strip(),
                         "sha256": sha256(args.launcher)},
            "content_compatibility": {
                "source_hmod": str(args.content_source),
                "source_hmod_sha256": sha256(args.content_source),
                "recipes_skipped_for_unsupported_load_conditions": sum(
                    "unknown load conditions [neoforge:tag_empty]" in line
                    for line in (args.output / "server.log").read_text().splitlines()),
                "unknown_feature_references": [line.strip() for line in
                    (args.output / "server.log").read_text().splitlines()
                    if "unknown feature reference" in line],
            },
            "players": identities,
            "online_names": sorted(player["name"] for player in players["online"]),
            "registry_counts": registry_counts,
            "registry_warnings": warnings,
            "gameplay": gameplay,
            "production_package_installed": True,
            "production_package_verified": True,
            "package_scope_note": "Combined production native Create package with full 0a-normalized content and kinetic adapters",
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
