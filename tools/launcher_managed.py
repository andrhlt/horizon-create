"""Managed Horizon Play launcher for headless control fixtures."""

import json
import os
from pathlib import Path
import subprocess
import time
import uuid


def launch_managed(version, socket, game_dir, world, *, instance, launcher,
                   launcher_home, resources, creative=False, append_world=True):
    version = Path(version).resolve()
    socket = Path(socket).resolve()
    game_dir = Path(game_dir).resolve()
    resources = Path(resources).resolve() if resources else None
    if not (version / ".installed").is_file():
        raise RuntimeError(f"Not an installed managed candidate: {version}")
    if not (version / "native-mods.json").is_file():
        raise RuntimeError(f"Candidate lacks native-mods.json: {version}")
    if resources is not None and not (resources / "horizon-resources.json").is_file():
        raise RuntimeError(f"Invalid 26.3 resource root: {resources}")
    game_dir.mkdir(parents=True, exist_ok=True)
    if append_world:
        world = f"{world}-{uuid.uuid4().hex[:8]}"
    command = [str(launcher), "play", "--instance", instance,
               "--version", version.name, "--world", world, "--json"]
    if creative:
        command.append("--creative")
    args = ("--headless", "--control", "--control-socket", str(socket))
    if resources is not None:
        args += ("--resources", str(resources))
    for arg in args:
        command.extend(("--arg", arg))
    env = os.environ.copy()
    env.update({"HORIZON_LAUNCHER_HOME": str(launcher_home),
                "HORIZON_LAUNCHER_DEVELOPER_OFFLINE": "1",
                "HORIZON_NO_AUDIO": "1", "HORIZON_CONTROL": str(socket)})
    log_path = game_dir / "managed-play.log"
    log = log_path.open("w")
    process = subprocess.Popen(command, cwd=game_dir, env=env, stdout=log,
                               stderr=subprocess.STDOUT, text=True)
    deadline = time.monotonic() + 120
    last_error = None
    ctl = version / "horizon-ctl"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        probe = subprocess.run([str(ctl), "--socket", str(socket), "status"],
                               capture_output=True, text=True, timeout=5)
        if probe.returncode == 0:
            return process, log, log_path, world
        last_error = probe.stderr.strip() or probe.stdout.strip()
        time.sleep(0.25)
    log.close()
    output = log_path.read_text(errors="replace")
    raise RuntimeError(f"Managed Play did not become ready (exit={process.poll()}, "
                       f"last={last_error!r})\n{output}")
