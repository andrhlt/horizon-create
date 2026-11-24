#!/usr/bin/env python3
"""Exercise host Press processing and guest collection on the supported offline route."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import time


def run(args: list[str], *, timeout: int = 30) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}{result.stderr}")
    return result.stdout.strip()


def wait_for(description: str, check, timeout: int = 45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            pass
        time.sleep(0.2)
    raise RuntimeError(f"timed out waiting for {description}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-binary", type=Path, required=True)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--ctl", type=Path, required=True)
    parser.add_argument("--resources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for name in ("server_binary", "client", "ctl", "resources"):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error(f"choose a new output directory; already exists: {args.output}")
    version = args.server_binary.parent
    manifest_path = version / "native-mods.json"
    manifest = json.loads(manifest_path.read_text())
    if {mod.get("id") for mod in manifest.get("mods", [])} != {"create"} or manifest.get("left_out"):
        parser.error("expected the integrated production Create module and no omitted mods")

    args.output.mkdir(parents=True)
    server_dir = args.output / "server"
    server_dir.mkdir()
    (server_dir / "resources").symlink_to(args.resources, target_is_directory=True)
    shared_mod_content = args.output / ".shared-mod-content"
    shared_mod_content.mkdir()
    for game_home in (server_dir, *(args.output / name for name in ("APP2176Host", "APP2176Guest"))):
        cache = game_home / ".horizon-cache"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "mod-content").symlink_to(shared_mod_content, target_is_directory=True)
    names = ("APP2176Host", "APP2176Guest")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    run([str(args.server_binary), "--dir", str(server_dir), "init", "--eula",
         "--world", "APP2176", "--seed", "2176", "--port", str(port),
         "--offline", "--yes", "--op", names[0]])
    run([str(args.server_binary), "--dir", str(server_dir), "config", "set",
         "server.bind=127.0.0.1", "server.whitelist=true",
         "server.enforce_whitelist=true", "server.max_players=2",
         "server.view_distance=3", "server.simulation_distance=3",
         "backups.every=0"])
    for name in names:
        run([str(args.server_binary), "--dir", str(server_dir), "whitelist", "add", name])

    server_log_path = args.output / "server.log"
    server_log = server_log_path.open("w")
    server = subprocess.Popen([str(args.server_binary), "--dir", str(server_dir), "run"],
                              stdin=subprocess.PIPE, stdout=server_log,
                              stderr=subprocess.STDOUT, text=True, start_new_session=True)
    clients: list[tuple[Path, dict[str, str]]] = []
    proof = {"route": "supported localhost offline dedicated server",
             "client_mode": "offscreen", "gameplay": {}}
    try:
        wait_for("server ready", lambda: "Done (" in server_log_path.read_text()
                 if server.poll() is None else None)
        address = f"127.0.0.1:{port}"
        for name in names:
            home = args.output / name
            home.mkdir(exist_ok=True)
            control = args.output / f"{name}.sock"
            env = os.environ.copy()
            env["HORIZON_CONTROL"] = str(control)
            proc = subprocess.Popen(
                [str(args.ctl), "--socket", str(control), "--timeout", "60", "launch",
                 "--offscreen", "--game", str(args.client), "--resources", str(args.resources),
                 "--server", address, "--name", name, "--game-dir", str(home),
                 "--home", str(home), "--player-dir", str(home / "player"),
                 "--render-distance", "3", "--wait"],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            clients.append((control, env))
            output, _ = proc.communicate(timeout=150)
            (args.output / f"{name}.launch.txt").write_text(output)
            if proc.returncode:
                raise RuntimeError(f"{name} launch failed; see {name}.launch.txt")

        def server_command(command: str) -> str:
            return run([str(args.server_binary), "--dir", str(server_dir), "cmd", command])

        def game_time() -> int:
            output = server_command("/time query gametime")
            match = re.search(r"game time is (\d+)", output)
            if not match:
                raise RuntimeError(f"could not read game time: {output}")
            return int(match.group(1))

        def step_ticks(count: int) -> None:
            server_command("/tick freeze")
            before = game_time()
            server_command(f"/tick step {count}")
            wait_for(f"all {count} stepped game ticks",
                     lambda: game_time() >= before + count, timeout=90)
            server_command("/tick freeze")

        def client_call(control: Path, env: dict[str, str], *command: str) -> dict:
            rows = [json.loads(line) for line in run(
                [str(args.ctl), "--socket", str(control), *command], timeout=30
            ).splitlines() if line.strip()]
            if not rows or rows[-1].get("ok") is False:
                raise RuntimeError(f"client command failed: {command}: {rows}")
            return rows[-1]

        def players():
            state = json.loads(run([str(args.server_binary), "--dir", str(server_dir),
                                    "players", "--json"]))
            online = state.get("online", [])
            return state if {player.get("name") for player in online} == set(names) else None

        state = wait_for("host and guest connection", players)
        identities = {player["name"]: player["uuid"]
                      for player in state.get("whitelist", {}).get("players", [])
                      if player.get("name") in names}
        if set(identities) != set(names) or len(set(identities.values())) != 2:
            raise RuntimeError(f"expected two distinct player UUIDs, got {identities}")
        proof["players"] = identities

        server_command("/forceload add 0 0")
        server_command("/tick freeze")
        initial_game_time = game_time()
        for command in (
            # Keep either player from collecting the dropped output while the
            # fixture advances its frozen tick window.
            "/tp APP2176Host 8.5 64 8.5",
            "/setblock 0 63 0 create:basin",
            "/setblock 0 64 0 create:mechanical_press",
            "/setblock 0 66 0 create:creative_motor[facing=down]",
            "/setblock 0 65 0 create:shaft[axis=y]",
            "/data merge block 0 66 0 {ScrollValue:256}",
            '/summon minecraft:item 0.5 63.25 0.5 {Item:{id:"minecraft:iron_ingot",count:1}}',
            # Allow the native chunk/block-entity tick cadence to sample the
            # powered network, scan for an input, and finish the Press cycle.
            # A nominal 120 server ticks can contain only two Press callbacks
            # when this fixture starts from a frozen world. Four hundred ticks
            # cover scan plus one complete cycle at the test motor speed.
            "/tick step 400",
        ):
            server_command(command)
        # /tick step schedules ticks on the server loop and returns before all
        # of them have run. Wait for the requested world time before inspecting
        # the machine, then freeze again so the saved state is deterministic.
        wait_for("all 400 stepped game ticks", lambda: game_time() >= initial_game_time + 400,
                 timeout=90)
        server_command("/tick freeze")
        items = server_command(
            "/execute as @e[type=minecraft:item,x=0,y=63,z=0,distance=..4] run data get entity @s Item"
        )
        if "create:iron_sheet" not in items or "minecraft:iron_ingot" in items:
            diagnostics = [server_command(f"/data get block {pos}")
                           for pos in ("0 64 0", "0 65 0", "0 66 0")]
            raise RuntimeError(f"Host Press cycle did not produce one sheet: items={items}; blocks={diagnostics}")
        proof["gameplay"]["host_press_output"] = items
        server_command("/tick unfreeze")
        server_command(f"/tp {names[1]} 0.5 63.25 0.5")
        guest_control, guest_env = clients[1]
        guest = wait_for(
            "guest to collect the host Press output",
            lambda: (result if result.get("counts", {}).get("create:iron_sheet", 0) == 1 else None)
            if (result := client_call(guest_control, guest_env, "inventory")) else None,
            timeout=30,
        )
        if guest.get("counts", {}).get("minecraft:iron_ingot", 0):
            raise RuntimeError(f"Guest received the wrong Press item: {guest}")
        proof["gameplay"]["guest_inventory"] = guest

        # Basin/Mixer dry mixing and compacting, including full-output
        # conservation and recovery. The separate machines share one isolated
        # dedicated world and the same typed production package.
        server_command("/forceload add 4 0")
        server_command("/forceload add 1 0")
        server_command("/forceload add 2 0")
        server_command("/forceload add 3 0")
        server_command("/setblock 0 102 0 create:basin")
        server_command("/setblock 0 103 0 create:mechanical_mixer")
        server_command("/setblock 0 104 0 create:shaft[axis=y]")
        server_command("/setblock 0 105 0 create:creative_motor[facing=down]")
        server_command("/data merge block 0 105 0 {ScrollValue:256}")
        server_command("/item replace block 0 102 0 container.0 with minecraft:andesite 1")
        server_command("/item replace block 0 102 0 container.1 with minecraft:iron_nugget 1")
        step_ticks(30)
        alloy = server_command("/data get block 0 102 0 Items")
        if "create:andesite_alloy" not in alloy:
            raise RuntimeError(f"Production Mixer did not create Andesite Alloy: {alloy}")
        proof["gameplay"]["basin_mixing"] = alloy

        server_command("/setblock 10 102 0 create:basin")
        server_command("/setblock 10 103 0 create:mechanical_mixer")
        server_command("/setblock 10 104 0 create:shaft[axis=y]")
        server_command("/setblock 10 105 0 create:creative_motor[facing=down]")
        server_command("/data merge block 10 105 0 {ScrollValue:256}")
        server_command("/item replace block 10 102 0 container.0 with minecraft:snow_block 9")
        server_command("/setblock 20 102 0 create:basin")
        server_command("/setblock 20 103 0 create:mechanical_mixer")
        server_command("/setblock 20 104 0 create:shaft[axis=y]")
        server_command("/setblock 20 105 0 create:creative_motor[facing=down]")
        server_command("/data merge block 20 105 0 {ScrollValue:256}")
        for slot in range(9, 18):
            server_command(f"/item replace block 20 102 0 container.{slot} with minecraft:stone 64")
        server_command("/item replace block 20 102 0 container.0 with minecraft:snow_block 9")
        step_ticks(30)
        compacted = server_command("/data get block 10 102 0 Items")
        blocked_basin = server_command("/data get block 20 102 0 Items")
        if 'id: "minecraft:ice"' not in compacted or "minecraft:snow_block" in compacted:
            raise RuntimeError(f"Production dry compacting failed: {compacted}")
        if "minecraft:snow_block" not in blocked_basin or 'id: "minecraft:ice"' in blocked_basin:
            raise RuntimeError(f"Full Basin output did not retain snow inputs: {blocked_basin}")
        server_command("/item replace block 20 102 0 container.9 with minecraft:air")
        step_ticks(30)
        recovered_basin = server_command("/data get block 20 102 0 Items")
        if 'id: "minecraft:ice"' not in recovered_basin or "minecraft:snow_block" in recovered_basin:
            raise RuntimeError(f"Basin did not recover when output space returned: {recovered_basin}")
        proof["gameplay"]["basin_compacting"] = compacted
        proof["gameplay"]["basin_backpressure"] = {
            "blocked": blocked_basin, "recovered": recovered_basin,
        }

        # Opposing powered wheels crush Gravel to Sand. A second controller
        # begins with every output slot full and must retain then resume input.
        for x in (50, 70):
            server_command(f"/setblock {x} 102 0 create:crushing_wheel_controller")
            for side, speed in ((-1, 256), (1, -256)):
                wheel_x = x + side
                server_command(f"/setblock {wheel_x} 102 0 create:crushing_wheel[axis=y]")
                server_command(f"/setblock {wheel_x} 103 0 create:shaft[axis=y]")
                server_command(f"/setblock {wheel_x} 104 0 create:creative_motor[facing=down]")
                server_command(f"/data merge block {wheel_x} 104 0 {{ScrollValue:{speed}}}")
        server_command("/item replace block 50 102 0 container.0 with minecraft:gravel 1")
        for slot in range(1, 16):
            server_command(f"/item replace block 70 102 0 container.{slot} with minecraft:stone 64")
        server_command("/item replace block 70 102 0 container.0 with minecraft:gravel 1")
        step_ticks(100)
        crushed = server_command("/data get block 50 102 0 Items")
        blocked_crushing = server_command("/data get block 70 102 0 Items")
        if 'id: "minecraft:sand"' not in crushed or "minecraft:gravel" in crushed:
            raise RuntimeError(f"Production Crushing Wheels did not produce Sand: {crushed}")
        if "minecraft:gravel" not in blocked_crushing or 'id: "minecraft:sand"' in blocked_crushing:
            raise RuntimeError(f"Full Crushing output did not retain Gravel: {blocked_crushing}")
        for slot in range(1, 16):
            server_command(f"/item replace block 70 102 0 container.{slot} with minecraft:air")
        step_ticks(100)
        recovered_crushing = server_command("/data get block 70 102 0 Items")
        if 'id: "minecraft:sand"' not in recovered_crushing or "minecraft:gravel" in recovered_crushing:
            raise RuntimeError(f"Crushing Wheels did not recover when output space returned: {recovered_crushing}")
        proof["gameplay"]["crushing"] = crushed
        proof["gameplay"]["crushing_backpressure"] = {
            "blocked": blocked_crushing, "recovered": recovered_crushing,
        }

        # Blaze Cake enables heated Brass mixing; coal covers ordinary fuel.
        server_command("/setblock 30 102 0 create:blaze_burner")
        server_command("/item replace block 30 102 0 container.0 with minecraft:coal 1")
        step_ticks(1)
        coal = server_command("/data get block 30 102 0")
        if "fuelLevel: 1" not in coal or "minecraft:coal" in coal:
            raise RuntimeError(f"Production Burner failed to consume ordinary fuel: {coal}")
        server_command("/setblock 40 102 0 create:blaze_burner")
        server_command("/item replace block 40 102 0 container.0 with create:blaze_cake 1")
        server_command("/setblock 40 103 0 create:basin")
        server_command("/setblock 40 104 0 create:mechanical_mixer")
        server_command("/setblock 40 105 0 create:shaft[axis=y]")
        server_command("/setblock 40 106 0 create:creative_motor[facing=down]")
        server_command("/data merge block 40 106 0 {ScrollValue:256}")
        server_command("/item replace block 40 103 0 container.0 with minecraft:copper_ingot 1")
        server_command("/item replace block 40 103 0 container.1 with create:zinc_ingot 1")
        server_command("/setblock 60 103 0 create:basin")
        server_command("/setblock 60 104 0 create:mechanical_mixer")
        server_command("/setblock 60 105 0 create:shaft[axis=y]")
        server_command("/setblock 60 106 0 create:creative_motor[facing=down]")
        server_command("/data merge block 60 106 0 {ScrollValue:256}")
        server_command("/item replace block 60 103 0 container.0 with minecraft:copper_ingot 1")
        server_command("/item replace block 60 103 0 container.1 with create:zinc_ingot 1")
        step_ticks(30)
        brass = server_command("/data get block 40 103 0 Items")
        hot_burner = server_command("/data get block 40 102 0")
        cold = server_command("/data get block 60 103 0 Items")
        if 'id: "create:brass_ingot"' not in brass or "fuelLevel: 2" not in hot_burner:
            raise RuntimeError(f"Blaze Cake did not enable heated Brass mixing: basin={brass}; burner={hot_burner}")
        if "minecraft:copper_ingot" not in cold or "create:zinc_ingot" not in cold or "create:brass_ingot" in cold:
            raise RuntimeError(f"Cold Mixer consumed ingredients without heat: {cold}")
        proof["gameplay"]["burner_coal"] = coal
        proof["gameplay"]["burner_brass"] = {"basin": brass, "burner": hot_burner}
        proof["gameplay"]["cold_mixer_rejection"] = cold

        # Persist real machine inventories and a guest-owned output across a
        # clean server stop/reopen and reconnect.
        server_command("/save-all flush")
        for control, env in clients:
            subprocess.run([str(args.ctl), "--socket", str(control), "quit"], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        server.stdin.write("stop\n")
        server.stdin.flush()
        server.wait(timeout=30)
        server_log.close()
        prior_done = server_log_path.read_text(errors="replace").count("Done (")
        server_log = server_log_path.open("a")
        server = subprocess.Popen([str(args.server_binary), "--dir", str(server_dir), "run"],
                                  stdin=subprocess.PIPE, stdout=server_log,
                                  stderr=subprocess.STDOUT, text=True, start_new_session=True)
        wait_for("server reopen", lambda: server.poll() is None and
                 server_log_path.read_text(errors="replace").count("Done (") > prior_done)
        address = f"127.0.0.1:{port}"
        clients.clear()
        for name in names:
            home = args.output / name
            control = args.output / f"{name}.sock"
            env = os.environ.copy()
            env["HORIZON_CONTROL"] = str(control)
            proc = subprocess.Popen(
                [str(args.ctl), "--socket", str(control), "--timeout", "60", "launch",
                 "--offscreen", "--game", str(args.client), "--resources", str(args.resources),
                 "--server", address, "--name", name, "--game-dir", str(home),
                 "--home", str(home), "--player-dir", str(home / "player"),
                 "--render-distance", "3", "--wait"],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            clients.append((control, env))
            output, _ = proc.communicate(timeout=150)
            (args.output / f"{name}.reopen.txt").write_text(output)
            if proc.returncode:
                raise RuntimeError(f"{name} reconnect failed; see {name}.reopen.txt")
        wait_for("host and guest reconnect", players)
        guest_control, guest_env = clients[1]
        reopened_guest = wait_for(
            "guest Press output inventory after reopen",
            lambda: (result if result.get("counts", {}).get("create:iron_sheet", 0) == 1 else None)
            if (result := client_call(guest_control, guest_env, "inventory")) else None,
        )
        reopened_proofs = {
            "basin_alloy": server_command("/data get block 0 102 0 Items"),
            "basin_ice": server_command("/data get block 10 102 0 Items"),
            "crushing_sand": server_command("/data get block 50 102 0 Items"),
            "crushing_recovered_sand": server_command("/data get block 70 102 0 Items"),
            "burner": server_command("/data get block 40 102 0"),
            "guest_inventory": reopened_guest,
        }
        persisted_items = {
            "basin_alloy": "create:andesite_alloy",
            "basin_ice": 'id: "minecraft:ice"',
            "crushing_sand": 'id: "minecraft:sand"',
            "crushing_recovered_sand": 'id: "minecraft:sand"',
        }
        for key, expected in persisted_items.items():
            if expected not in reopened_proofs[key]:
                raise RuntimeError(f"Machine inventory did not persist across reopen ({key}): {reopened_proofs[key]}")
        if "fuelLevel: 2" not in reopened_proofs["burner"]:
            raise RuntimeError(f"Active Burner fuel did not persist across reopen: {reopened_proofs['burner']}")
        proof["save_reopen"] = reopened_proofs
        proof["build"] = manifest
        proof["sha256"] = {"server": sha256(args.server_binary),
                           "client": sha256(args.client), "ctl": sha256(args.ctl),
                           "native_mods": sha256(manifest_path)}
        (args.output / "app-2176-offline-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
        print(f"Host Press output was collected by the guest; proof: {args.output / 'app-2176-offline-proof.json'}")
    finally:
        for control, env in clients:
            subprocess.run([str(args.ctl), "--socket", str(control), "quit"], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
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
