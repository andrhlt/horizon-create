#!/usr/bin/env python3
"""Run a bounded motor → shaft → cogwheel flow through managed offline Play."""

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid

from fixture_world import FixtureWorld


POSITIONS = ((0, 100, 0), (1, 100, 0), (2, 100, 0))
EXPECTED_BLOCKS = ("create:motor", "create:simple_kinetic", "create:simple_kinetic")


def launch(args, world, socket):
    command = [
        str(args.launcher), "play", "--instance", args.instance,
        "--version", args.version.name, "--world", world, "--creative", "--json",
    ]
    for item in ("--headless", "--control", "--control-socket", str(socket)):
        command.extend(("--arg", item))
    env = os.environ.copy()
    env.update({
        "HORIZON_LAUNCHER_HOME": str(args.launcher_home),
        "HORIZON_LAUNCHER_DEVELOPER_OFFLINE": "1",
        "HORIZON_NO_AUDIO": "1",
    })
    log = socket.parent / "play.log"
    stream = log.open("w")
    process = subprocess.Popen(command, cwd=args.instance_dir, env=env,
                               stdout=stream, stderr=subprocess.STDOUT, text=True)
    deadline = time.monotonic() + 120
    ctl = args.version / "horizon-ctl"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        probe = subprocess.run([str(ctl), "--socket", str(socket), "status"],
                               capture_output=True, text=True, timeout=5)
        if probe.returncode == 0:
            control = FixtureWorld(ctl, socket, {}, launch=())
            control.call("command", "/tick freeze")
            return process, stream, control, log
        time.sleep(0.25)
    stream.close()
    raise RuntimeError(f"Managed offline Play did not start:\n{log.read_text(errors='replace')}")


def close(process, stream, control):
    if control.socket.exists():
        control.stop()
    process.wait(timeout=30)
    stream.close()


@contextmanager
def managed_world(args, world):
    with tempfile.TemporaryDirectory(prefix="app2136-kinetic-flow-") as temporary:
        socket = Path(temporary) / "control.sock"
        process, stream, control, log = launch(args, world, socket)
        try:
            yield control
        finally:
            close(process, stream, control)
            args.log.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(log, args.log)


def install_pack(args):
    mods = args.instance_dir / "horizon-mods"
    mods.mkdir(parents=True, exist_ok=True)
    destination = mods / "create.hmod"
    if not destination.is_file() or destination.read_bytes() != args.pack.read_bytes():
        shutil.copy2(args.pack, destination)
    enabled = args.instance_dir / "horizon-mods.txt"
    if not enabled.is_file() or "mod.create:true" not in enabled.read_text(encoding="utf-8"):
        enabled.write_text("mod.create:true\n", encoding="utf-8")


def block_data(control):
    return control.commands(
        f"/data get block {x} {y} {z}" for x, y, z in POSITIONS
    )


def speeds(data):
    result = []
    for expected, nbt in zip(EXPECTED_BLOCKS, data, strict=True):
        if f'id: "{expected}"' not in nbt:
            raise RuntimeError(f"Expected {expected} block entity: {nbt}")
        match = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)f\b", nbt)
        if not match:
            raise RuntimeError(f"Missing Speed in {nbt}")
        result.append(float(match.group(1)))
        network = re.search(r"Network: \{Capacity: ([\d.]+)f, Stress: ([\d.]+)f\}", nbt)
        if not network or float(network.group(1)) < 0 or float(network.group(2)) < 0:
            raise RuntimeError(f"Missing or invalid network totals in {nbt}")
    return result


def change_speed(control, value, ticks=10):
    control.commands((
        f"/data merge block {POSITIONS[0][0]} {POSITIONS[0][1]} {POSITIONS[0][2]} {{ScrollValue:{value}}}",
        f"/tick step {ticks}",
    ))
    return block_data(control)


def verify(args):
    install_pack(args)
    world = f"APP2136Kinetic-{uuid.uuid4().hex[:8]}"
    with managed_world(args, world) as control:
        control.commands((
            "/setblock 0 100 0 create:creative_motor[facing=east]",
            "/setblock 1 100 0 create:shaft[axis=x]",
            "/setblock 2 100 0 create:cogwheel[axis=x]",
        ))
        forward = speeds(change_speed(control, 32))
        if forward != [32.0] * 3:
            raise RuntimeError(f"Forward propagation failed: {forward}")
        reverse = speeds(change_speed(control, -16))
        if reverse != [-16.0] * 3:
            raise RuntimeError(f"Reverse propagation failed: {reverse}")
        stopped = speeds(change_speed(control, 0, ticks=3))
        if stopped != [0.0] * 3:
            raise RuntimeError(f"Stop propagation failed: {stopped}")
        active = speeds(change_speed(control, 24))
        if active != [24.0] * 3:
            raise RuntimeError(f"Restart propagation failed: {active}")
        control.call("save")

    with managed_world(args, world) as reopened:
        data = block_data(reopened)
        reopened_speeds = speeds(data)
        if reopened_speeds != [24.0] * 3 or "ScrollValue: 24" not in data[0]:
            raise RuntimeError(f"Active kinetic setup did not survive reopen: {data}")

    print("Motor, shaft and cogwheel propagated +32, -16, 0 and +24 RPM; active +24 saved and reopened.")
    print("Setting changes in this fixture use server commands; board UI and guest input are separate gates.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--instance", required=True)
    parser.add_argument("--instance-dir", type=lambda value: Path(value).resolve(strict=True), required=True)
    parser.add_argument("--launcher", type=lambda value: Path(value).resolve(strict=True), required=True)
    parser.add_argument("--launcher-home", type=lambda value: Path(value).resolve(strict=True), required=True)
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True), required=True)
    parser.add_argument("--log", type=Path, default=Path(".local/horizon-typed-kinetic-flow.log"))
    args = parser.parse_args()
    if not (args.version / ".installed").is_file():
        parser.error(f"Not an installed managed candidate: {args.version}")
    verify(args)


if __name__ == "__main__":
    main()
