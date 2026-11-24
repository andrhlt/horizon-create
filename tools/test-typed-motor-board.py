#!/usr/bin/env python3
"""Exercise ordinary Creative Motor board clicks and active save/reopen."""

import argparse
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from fixture_world import FixtureWorld

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
MOTOR_SPEC = importlib.util.spec_from_file_location(
    "creative_motor_fixture", ROOT / "tools/test-creative-motor.py"
)
MOTOR = importlib.util.module_from_spec(MOTOR_SPEC)
MOTOR_SPEC.loader.exec_module(MOTOR)


@contextmanager
def managed_world(args, world):
    socket = Path(tempfile.mkdtemp(prefix="app2136-motor-board-")) / "control.sock"
    log_path = socket.parent / "play.log"
    log = log_path.open("w")
    env = os.environ.copy()
    env.update({
        "HORIZON_LAUNCHER_HOME": str(args.launcher_home),
        "HORIZON_LAUNCHER_DEVELOPER_OFFLINE": "1",
        "HORIZON_NO_AUDIO": "1",
    })
    if args.trace:
        env["CREATE_MOTOR_BOARD_TRACE"] = "1"
    command = [
        str(args.launcher), "play", "--instance", args.instance,
        "--version", args.version.name, "--world", world, "--creative", "--json",
    ]
    for value in ("--offscreen", "--control", "--control-socket", str(socket)):
        command.extend(("--arg", value))
    process = subprocess.Popen(
        command, cwd=args.instance_dir, env=env, stdout=log,
        stderr=subprocess.STDOUT, text=True,
    )
    control = None
    try:
        ctl = args.version / "horizon-ctl"
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Managed Play exited: {log_path.read_text(errors='replace')}")
            try:
                result = subprocess.run(
                    [str(ctl), "--socket", str(socket), "status"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    break
            except subprocess.TimeoutExpired:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError(f"Timed out waiting for managed Play: {log_path}")
        control = FixtureWorld(ctl, socket, {}, launch=())
        control.call("command", "/tick freeze")
        yield control
    finally:
        if control is not None and socket.exists():
            control.stop()
        if process.poll() is None:
            process.wait(timeout=30)
        log.close()
        args.log.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(log_path, args.log)


def setting_state(control):
    motor, shaft = control.commands((
        "/data get block 8 101 -10", "/data get block 8 101 -9",
    ))
    scroll = int(re.search(r"ScrollValue: (-?\d+)", motor).group(1))
    motor_speed = float(re.search(r"Speed: (-?\d+(?:\.\d+)?)f", motor).group(1))
    shaft_speed = float(re.search(r"Speed: (-?\d+(?:\.\d+)?)f", shaft).group(1))
    return scroll, motor_speed, shaft_speed


def set_by_click(control, row, column, expected):
    label = "Counterclockwise RPM" if row == 0 else "Clockwise RPM"
    button = next(
        (item for item in control.call("screen").get("buttons", [])
         if item["label"] == label),
        None,
    )
    if button is None:
        raise RuntimeError(f"The motor board is missing {label}.")
    offset = ((max(1, column) - 1) // 32) * 4 + column + 1.5
    if column % 32 == 0:
        offset += 2
    if column > 0:
        offset += 4
    point = (button["x"] + offset, button["y"] + button["h"] / 2)
    control.call("scroll-at", *point, 0)
    control.call("click-at", *point, "right")
    control.call("wait", 3)
    result = setting_state(control)
    if result != (expected, float(expected), float(expected)):
        raise RuntimeError(f"Click for {expected} RPM produced {result}.")


def run(args):
    mods = args.instance_dir / "horizon-mods"
    mods.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.pack, mods / "create.hmod")
    (args.instance_dir / "horizon-mods.txt").write_text(
        "mod.create:true\n", encoding="utf-8"
    )
    world = f"APP2136MotorBoard-{uuid.uuid4().hex[:8]}"
    with managed_world(args, world) as control:
        # Load one chunk around the selected horizontal motor, so setup does
        # not depend on the generated world's initial spawn chunks.
        control.command("/tp @s 8 104 -10")
        control.call("wait", 1)
        control.commands((
            "/fill 7 100 -11 9 100 -8 minecraft:smooth_stone",
            "/fill 7 101 -11 9 104 -8 minecraft:air",
            "/setblock 8 101 -10 create:creative_motor[facing=south]",
            "/setblock 8 101 -9 create:shaft[axis=z]",
            "/gamemode survival",
        ))
        x, y, z = MOTOR.HORIZONTAL
        _, center_y, center_z = MOTOR.SLOT_OFFSETS["south", "west"]
        control.command(f"/tp @s {x - 2} {y} {z + center_z}")
        control.call("wait", 3)
        control.call("look-at", x + 0.19, y + center_y, z + center_z)
        control.call("mouse", "right", "down")
        control.call("wait", 7)
        labels = [b["label"] for b in control.call("screen").get("buttons", [])]
        if control.call("state")["screen"] != "container" or labels != [
            "Counterclockwise RPM", "Clockwise RPM",
        ]:
            raise RuntimeError(f"Creative Motor board did not open correctly: {labels}")
        for row, value in ((1, 64), (0, 24), (1, 0), (1, 64)):
            set_by_click(control, row, value, value if row else -value)
        if control.call("state")["pointer_grabbed"]:
            raise RuntimeError("Offscreen motor-board use captured the pointer.")
        control.call("save")

    with managed_world(args, world) as reopened:
        state = setting_state(reopened)
        if state != (64, 64.0, 64.0):
            raise RuntimeError(f"Active clicked setting did not survive reopen: {state}")
    print("Board opened; ordinary clicks propagated +64, -24, 0 and +64 RPM.")
    print("Active +64 motor setting and shaft speed survived save/reopen.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--instance", required=True)
    parser.add_argument("--instance-dir", type=lambda value: Path(value).resolve(strict=True), required=True)
    parser.add_argument("--launcher", type=lambda value: Path(value).resolve(strict=True), required=True)
    parser.add_argument("--launcher-home", type=lambda value: Path(value).resolve(strict=True), required=True)
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True), required=True)
    parser.add_argument("--log", type=Path, default=ROOT / ".local/horizon-typed-motor-board.log")
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()
    if not (args.version / ".installed").is_file():
        parser.error(f"Not an installed managed candidate: {args.version}")
    run(args)


if __name__ == "__main__":
    main()
