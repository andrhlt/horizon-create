#!/usr/bin/env python3
"""Exercise an opposing-wheel Crushing cycle and persisted output."""

import argparse
from pathlib import Path
from shutil import copy2
import tempfile

from fixture_world import FixtureWorld, install_pack
from launcher_managed import launch_managed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources", "pack", "launcher", "launcher_home", "instance_dir", "evidence"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--instance", required=True)
    args = parser.parse_args()
    for name in ("ctl", "client", "resources", "pack", "launcher"):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    args.launcher_home = args.launcher_home.resolve(strict=True)
    args.instance_dir = args.instance_dir.resolve()
    args.evidence = args.evidence.resolve()

    with tempfile.TemporaryDirectory(prefix="hc-managed-crushing-") as tmp:
        scratch = Path(tmp)
        socket, game = scratch / "ctl.sock", scratch / "game"
        install_pack(game, args.pack)
        mods = args.instance_dir / "horizon-mods"
        mods.mkdir(parents=True, exist_ok=True)
        copy2(args.pack, mods / "create.hmod")
        (args.instance_dir / "horizon-mods.txt").write_text("mod.create:true\n")
        process, log, log_path, world = launch_managed(
            args.client.parent, socket, game, "TypedCrushingWheels", instance=args.instance,
            launcher=args.launcher, launcher_home=args.launcher_home,
            resources=args.resources, creative=True,
        )
        control = FixtureWorld(args.ctl, socket, {}, launch=())
        try:
            control.call("wait-ready", timeout=90)
            control.call("command", "/tick freeze")
            control.call("command", "/tick step 1")
            control.commands((
                "/forceload add 0 0",
                "/setblock 0 102 0 create:crushing_wheel_controller",
                "/setblock -1 102 0 create:crushing_wheel[axis=y]",
                "/setblock 1 102 0 create:crushing_wheel[axis=y]",
                "/setblock -1 103 0 create:shaft[axis=y]",
                "/setblock -1 104 0 create:creative_motor[facing=down]",
                "/data merge block -1 104 0 {ScrollValue:256}",
                "/setblock 1 103 0 create:shaft[axis=y]",
                "/setblock 1 104 0 create:creative_motor[facing=down]",
                "/data merge block 1 104 0 {ScrollValue:-256}",
                "/item replace block 0 102 0 container.0 with minecraft:gravel 1",
                "/tick step 2",
                "/tick step 100",
            ))
            data = control.call("command", "/data get block 0 102 0 Items").get("chat", [])
            if not any('id: "minecraft:sand"' in str(line) for line in data) or any("minecraft:gravel" in str(line) for line in data):
                details = {pos: control.call("command", f"/data get block {pos}").get("chat", [])
                           for pos in ("-1 102 0", "1 102 0", "0 102 0")}
                raise RuntimeError(f"Opposing-wheel Gravel crushing failed or lost its input: items={data}; blocks={details}")
            control.commands((
                "/setblock 10 102 0 create:crushing_wheel_controller",
                "/setblock 9 102 0 create:crushing_wheel[axis=y]",
                "/setblock 11 102 0 create:crushing_wheel[axis=y]",
                "/setblock 9 103 0 create:shaft[axis=y]",
                "/setblock 9 104 0 create:creative_motor[facing=down]",
                "/data merge block 9 104 0 {ScrollValue:256}",
                "/setblock 11 103 0 create:shaft[axis=y]",
                "/setblock 11 104 0 create:creative_motor[facing=down]",
                "/data merge block 11 104 0 {ScrollValue:-256}",
                *[f"/item replace block 10 102 0 container.{slot} with minecraft:stone 64" for slot in range(1, 16)],
                "/item replace block 10 102 0 container.0 with minecraft:gravel 1",
                "/tick step 100",
            ))
            blocked = control.call("command", "/data get block 10 102 0 Items").get("chat", [])
            if not any('id: "minecraft:gravel"' in str(line) for line in blocked) or any('id: "minecraft:sand"' in str(line) for line in blocked):
                raise RuntimeError(f"Full Crushing output did not retain Gravel: {blocked}")
            control.commands((
                *[f"/item replace block 10 102 0 container.{slot} with minecraft:air" for slot in range(1, 16)],
                "/tick step 100",
            ))
            recovered = control.call("command", "/data get block 10 102 0 Items").get("chat", [])
            if not any('id: "minecraft:sand"' in str(line) for line in recovered) or any('id: "minecraft:gravel"' in str(line) for line in recovered):
                raise RuntimeError(f"Crushing did not recover when output space returned: {recovered}")
            control.call("save")
            control.stop()
            process.wait(timeout=30)
            log.close()
            process, log, log_path, _ = launch_managed(
                args.client.parent, socket, game, world, instance=args.instance,
                launcher=args.launcher, launcher_home=args.launcher_home,
                resources=args.resources, creative=True, append_world=False,
            )
            control = FixtureWorld(args.ctl, socket, {}, launch=())
            control.call("wait-ready", timeout=90)
            control.call("command", "/tick freeze")
            control.call("command", "/tick step 1")
            persisted = control.call("command", "/data get block 0 102 0 Items").get("chat", [])
            if not any('id: "minecraft:sand"' in str(line) for line in persisted):
                raise RuntimeError(f"Crushing output did not survive save/reopen: {persisted}")
            persisted_blocked_lane = control.call("command", "/data get block 10 102 0 Items").get("chat", [])
            if not any('id: "minecraft:sand"' in str(line) for line in persisted_blocked_lane):
                raise RuntimeError(f"Recovered Crushing output did not survive save/reopen: {persisted_blocked_lane}")
            print("Opposing wheel speed validation, Gravel crushing, full-output conservation/recovery, and save/reopen passed.")
        finally:
            if socket.exists():
                control.stop()
            process.wait(timeout=30)
            if not log.closed:
                log.close()
            args.evidence.mkdir(parents=True, exist_ok=True)
            for source, name in ((log_path, "managed-play.log"),
                                 (args.instance_dir / "logs/latest.log", "latest.log")):
                if source.is_file():
                    copy2(source, args.evidence / name)


if __name__ == "__main__":
    main()
