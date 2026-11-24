#!/usr/bin/env python3
"""Exercise fuel timing and heated mixing through typed Burner/Mixer parts."""

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

    with tempfile.TemporaryDirectory(prefix="hc-managed-burner-") as tmp:
        scratch = Path(tmp)
        socket, game = scratch / "ctl.sock", scratch / "game"
        install_pack(game, args.pack)
        mods = args.instance_dir / "horizon-mods"
        mods.mkdir(parents=True, exist_ok=True)
        copy2(args.pack, mods / "create.hmod")
        (args.instance_dir / "horizon-mods.txt").write_text("mod.create:true\n")
        process, log, log_path, world = launch_managed(
            args.client.parent, socket, game, "TypedBurnerIntegration", instance=args.instance,
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
                "/setblock 0 102 0 create:blaze_burner",
                "/item replace block 0 102 0 container.0 with minecraft:coal 1",
                "/tick step 1",
            ))
            coal = control.call("command", "/data get block 0 102 0").get("chat", [])
            if not any("fuelLevel: 1" in str(line) and "burnTimeRemaining:" in str(line) for line in coal):
                raise RuntimeError(f"Ordinary fuel did not start the Burner: {coal}")
            if any("minecraft:coal" in str(line) for line in coal):
                raise RuntimeError(f"Burner failed to consume one coal: {coal}")
            control.commands((
                "/setblock 30 102 0 create:blaze_burner",
                "/item replace block 30 102 0 container.0 with create:blaze_cake 1",
                "/setblock 30 103 0 create:basin",
                "/setblock 30 104 0 create:mechanical_mixer",
                "/setblock 30 105 0 create:shaft[axis=y]",
                "/setblock 30 106 0 create:creative_motor[facing=down]",
                "/data merge block 30 106 0 {ScrollValue:256}",
                "/item replace block 30 103 0 container.0 with minecraft:copper_ingot 1",
                "/item replace block 30 103 0 container.1 with create:zinc_ingot 1",
                "/tick step 30",
            ))
            brass = control.call("command", "/data get block 30 103 0 Items").get("chat", [])
            burner = control.call("command", "/data get block 30 102 0").get("chat", [])
            if not any('id: "create:brass_ingot"' in str(line) for line in brass):
                raise RuntimeError(f"Superheated Burner did not enable brass mixing: basin={brass}; burner={burner}")
            if not any("fuelLevel: 2" in str(line) and "burnTimeRemaining:" in str(line) for line in burner):
                raise RuntimeError(f"Blaze Cake did not persist superheated fuel state: {burner}")
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
            reopened = control.call("command", "/data get block 30 102 0").get("chat", [])
            if not any("fuelLevel: 2" in str(line) and "burnTimeRemaining:" in str(line) for line in reopened):
                raise RuntimeError(f"Burner active fuel state did not survive save/reopen: {reopened}")
            print("Burner coal and blaze-cake fuel, heated Brass mixing, and active save/reopen passed.")
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
