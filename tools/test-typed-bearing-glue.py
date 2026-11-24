#!/usr/bin/env python3
"""Exercise one real super-glue marker beyond the seed payload ring."""

import argparse
from contextlib import contextmanager
from pathlib import Path
import re
import shutil
import tempfile

from fixture_world import FixtureWorld, install_pack
from launcher_managed import launch_managed

BEARING = (0, 100, 0)
MOTOR = (0, 99, 0)
CHEST = (1, 101, 0)
EXTENSION = (2, 101, 0)


def xyz(pos):
    return " ".join(map(str, pos))


def data(control, pos):
    return control.command(f"/data get block {xyz(pos)}")


def number(reply, key):
    match = re.search(rf"\b{re.escape(key)}: (-?\d+(?:\.\d+)?)(?:[bslfd])?", reply)
    return float(match.group(1)) if match else None


def positions(reply):
    match = re.search(r"PayloadPositions: \[(.*?)\], x:", reply)
    return [tuple(map(int, values)) for values in re.findall(
        r"\[I; (-?\d+), (-?\d+), (-?\d+)\]", match.group(1)
    )] if match else []


def items(control, pos):
    return sum(map(int, re.findall(r"count: (\d+)", data(control, pos))))


@contextmanager
def managed_fixture(args, world):
    with tempfile.TemporaryDirectory(prefix="app2136-glue-") as tmp:
        scratch = Path(tmp)
        socket = scratch / "ctl.sock"
        game = scratch / "game"
        install_pack(game, args.pack)
        instance_mods = args.instance_dir / "horizon-mods"
        instance_mods.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.pack, instance_mods / "create.hmod")
        (args.instance_dir / "horizon-mods.txt").write_text("mod.create:true\n", encoding="utf-8")
        process, log, log_path, actual_world = launch_managed(
            args.client.parent, socket, game, world,
            instance=args.instance, launcher=args.launcher,
            launcher_home=args.launcher_home, resources=args.resources,
            creative=True,
        )
        control = FixtureWorld(args.ctl, socket, {}, launch=())
        def reopen():
            nonlocal process, log, log_path, control
            control.stop()
            process.wait(timeout=30)
            if not log.closed:
                log.close()
            process, log, log_path, _ = launch_managed(
                args.client.parent, socket, game, actual_world,
                instance=args.instance, launcher=args.launcher,
                launcher_home=args.launcher_home, resources=args.resources,
                creative=True, append_world=False,
            )
            control = FixtureWorld(args.ctl, socket, {}, launch=())
            control.call("command", "/tick freeze")
            return control
        control.reopen = reopen
        try:
            control.call("command", "/tick freeze")
            yield control
        finally:
            if socket.exists():
                control.stop()
            process.wait(timeout=30)
            if not log.closed:
                log.close()
            if args.evidence_dir:
                args.evidence_dir.mkdir(parents=True, exist_ok=True)
                if log_path.is_file():
                    shutil.copy2(log_path, args.evidence_dir / "managed-play.log")
                logs = args.instance_dir / "logs/latest.log"
                if logs.is_file():
                    shutil.copy2(logs, args.evidence_dir / "latest.log")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ctl", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("client", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("resources", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--instance", required=True)
    parser.add_argument("--instance-dir", type=Path, required=True)
    parser.add_argument("--launcher", type=lambda value: Path(value).resolve(strict=True), required=True)
    parser.add_argument("--launcher-home", type=lambda value: Path(value).resolve(strict=True), required=True)
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True), required=True)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    args = parser.parse_args()
    args.instance_dir = args.instance_dir.resolve(strict=True)
    with managed_fixture(args, "TypedBearingGlue") as control:
        control.commands((
            "/fill -3 97 -3 4 105 3 minecraft:air",
            f"/setblock {xyz(BEARING)} create:mechanical_bearing[facing=up]",
            f"/setblock {xyz(MOTOR)} create:creative_motor[facing=up]{{ScrollValue:20}}",
            f"/setblock {xyz(CHEST)} minecraft:chest",
            f"/setblock {xyz(EXTENSION)} minecraft:barrel[facing=north]",
            f"/item replace block {xyz(CHEST)} container.0 with minecraft:iron_ingot 7",
            "/summon minecraft:marker 0 101 0 {CreateSuperGlue:1b,From:[0d,0d,-1d],To:[3d,1d,2d]}",
            "/tp @s 1.5 102 0.5",
        ))
        marker = control.command("/data get entity @e[type=minecraft:marker,limit=1]")
        if "CreateSuperGlue: 1b" not in marker:
            raise RuntimeError(f"Glue marker fixture was not created: {marker}")
        control.command("/tick step 15")
        active = data(control, BEARING)
        carried = positions(active)
        if number(active, "Angle") is None or number(active, "Angle") < 80:
            raise RuntimeError(f"Powered glued bearing did not rotate: {active}")
        if len(carried) != 2 or EXTENSION in carried:
            raise RuntimeError(f"Special-entity glue traversal missed the extension: {active}")
        if number(active, "RiderCaptured") != 1:
            raise RuntimeError(f"Standing payload rider was not captured: {active}")
        if sorted(items(control, position) for position in carried) != [0, 7]:
            raise RuntimeError(f"Glued payload inventory was not conserved: {active}")
        control.call("save")
        control = control.reopen()
        reopened = data(control, BEARING)
        if len(positions(reopened)) != 2 or sorted(items(control, position) for position in positions(reopened)) != [0, 7]:
            raise RuntimeError(f"Active glued payload or inventory was lost on reopen: {reopened}")
        if number(reopened, "RiderCaptured") != 1:
            raise RuntimeError(f"Saved rider state was lost on reopen: {reopened}")
        control.command(f"/data merge block {xyz(MOTOR)} {{ScrollValue:0}}")
        control.command("/tick step 1")
        stopped = data(control, BEARING)
        if "Moving: 0b" not in stopped or sorted(items(control, position) for position in positions(stopped)) != [0, 7]:
            raise RuntimeError(f"Glued payload did not disassemble safely: {stopped}")
        if number(stopped, "RiderSafeDismount") != 1:
            raise RuntimeError(f"Rider was not safely dismounted: {stopped}")
    print("Super-glue traversal moved chest+extension, preserved seven ingots through active save/reopen, and disassembled safely.")


if __name__ == "__main__":
    main()
