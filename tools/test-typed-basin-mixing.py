#!/usr/bin/env python3
"""Exercise a dry mixing recipe through the typed Basin and Mixer parts."""

import argparse
from pathlib import Path
from shutil import copy2
import tempfile
import time

from fixture_world import FixtureWorld, install_pack
from launcher_managed import launch_managed

BASIN = "0 102 0"
COMPACTING = "10 102 0"
BACKPRESSURE = "20 102 0"


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

    with tempfile.TemporaryDirectory(prefix="hc-managed-basin-") as tmp:
        scratch = Path(tmp)
        socket, game = scratch / "ctl.sock", scratch / "game"
        install_pack(game, args.pack)
        mods = args.instance_dir / "horizon-mods"
        mods.mkdir(parents=True, exist_ok=True)
        copy2(args.pack, mods / "create.hmod")
        (args.instance_dir / "horizon-mods.txt").write_text("mod.create:true\n")
        world_name = "TypedBasinMixing"
        process, log, log_path, world = launch_managed(
            args.client.parent, socket, game, world_name, instance=args.instance,
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
                f"/setblock {BASIN} create:basin",
                "/setblock 0 105 0 create:creative_motor[facing=down]",
                "/setblock 0 104 0 create:shaft[axis=y]",
                "/setblock 0 103 0 create:mechanical_mixer",
                "/data merge block 0 105 0 {ScrollValue:256}",
                f"/item replace block {BASIN} container.0 with minecraft:andesite 1",
                f"/item replace block {BASIN} container.1 with minecraft:iron_nugget 1",
                "/tick step 30",
            ))
            data = control.call("command", f"/data get block {BASIN} Items").get("chat", [])
            if not any("create:andesite_alloy" in str(line) for line in data):
                diagnostics = {
                    pos: control.call("command", f"/data get block {pos}").get("chat", [])
                    for pos in ("0 102 0", "0 103 0", "0 104 0", "0 105 0")
                }
                raise RuntimeError(f"Typed Basin did not complete production andesite-alloy mixing: items={data}; blocks={diagnostics}")
            control.commands((
                f"/setblock {COMPACTING} create:basin",
                "/setblock 10 105 0 create:creative_motor[facing=down]",
                "/setblock 10 104 0 create:shaft[axis=y]",
                "/setblock 10 103 0 create:mechanical_mixer",
                "/data merge block 10 105 0 {ScrollValue:256}",
                f"/item replace block {COMPACTING} container.0 with minecraft:snow_block 9",
                f"/setblock {BACKPRESSURE} create:basin",
                "/setblock 20 105 0 create:creative_motor[facing=down]",
                "/setblock 20 104 0 create:shaft[axis=y]",
                "/setblock 20 103 0 create:mechanical_mixer",
                "/data merge block 20 105 0 {ScrollValue:256}",
                *[f"/item replace block {BACKPRESSURE} container.{slot} with minecraft:stone 64" for slot in range(9, 18)],
                f"/item replace block {BACKPRESSURE} container.0 with minecraft:snow_block 9",
                "/tick step 30",
            ))
            compacted = control.call("command", f"/data get block {COMPACTING} Items").get("chat", [])
            if not any('id: "minecraft:ice"' in str(line) for line in compacted) or any("minecraft:snow_block" in str(line) for line in compacted):
                raise RuntimeError(f"Dry compacting did not conserve inputs into ice: {compacted}")
            blocked = control.call("command", f"/data get block {BACKPRESSURE} Items").get("chat", [])
            if not any("minecraft:snow_block" in str(line) for line in blocked) or any('id: "minecraft:ice"' in str(line) for line in blocked):
                details = {
                    pos: control.call("command", f"/data get block {pos}").get("chat", [])
                    for pos in (BACKPRESSURE, "20 103 0", "20 104 0", "20 105 0")
                }
                raise RuntimeError(f"Full Basin output did not retain compacting inputs: {details}")
            control.call("command", f"/item replace block {BACKPRESSURE} container.9 with minecraft:air")
            control.call("command", "/tick step 30")
            recovered = control.call("command", f"/data get block {BACKPRESSURE} Items").get("chat", [])
            if not any('id: "minecraft:ice"' in str(line) for line in recovered) or any("minecraft:snow_block" in str(line) for line in recovered):
                raise RuntimeError(f"Basin did not recover when output space returned: {recovered}")
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
            data = control.call("command", f"/data get block {BASIN} Items").get("chat", [])
            if not any("create:andesite_alloy" in str(line) for line in data):
                raise RuntimeError(f"Basin output did not survive save/reopen: {data}")
            for pos, item in ((COMPACTING, "minecraft:ice"), (BACKPRESSURE, "minecraft:ice")):
                reopened = control.call("command", f"/data get block {pos} Items").get("chat", [])
                if not any(f'id: "{item}"' in str(line) for line in reopened):
                    raise RuntimeError(f"Basin output at {pos} did not survive save/reopen: {reopened}")
            print("Typed Basin passed dry mixing, dry compacting, full-output backpressure/recovery and save/reopen.")
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
