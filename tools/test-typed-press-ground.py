#!/usr/bin/env python3
"""Exercise a ground-item Press cycle on the pinned managed SDK build."""

import argparse
from contextlib import contextmanager
from pathlib import Path
from shutil import copy2
import tempfile
import time

from fixture_world import FixtureWorld, install_pack
from launcher_managed import launch_managed

PRESS = "0 102 0"


def freeze(control):
    control.call("wait-ready", timeout=90)
    control.call("command", "/tick freeze")
    result = control.call("command", "/tick step 1")
    chat = result.get("chat", [])
    if any("must be frozen" in str(line).lower() for line in chat):
        raise RuntimeError(f"Managed fixture failed to freeze before stepping: {chat}")


@contextmanager
def managed_fixture(args):
    with tempfile.TemporaryDirectory(prefix="hc-managed-press-") as tmp:
        scratch = Path(tmp)
        socket, game = scratch / "ctl.sock", scratch / "game"
        install_pack(game, args.pack)
        mods = args.instance_dir / "horizon-mods"
        mods.mkdir(parents=True, exist_ok=True)
        copy2(args.pack, mods / "create.hmod")
        (args.instance_dir / "horizon-mods.txt").write_text("mod.create:true\n")
        process, log, log_path, world = launch_managed(
            args.client.parent, socket, game, "TypedMechanicalPress",
            instance=args.instance, launcher=args.launcher,
            launcher_home=args.launcher_home, resources=args.resources, creative=True,
        )
        control = FixtureWorld(args.ctl, socket, {}, launch=())
        try:
            freeze(control)
            yield control
            control.call("save")
            control.stop()
            process.wait(timeout=30)
            log.close()
            process, log, log_path, _ = launch_managed(
                args.client.parent, socket, game, world,
                instance=args.instance, launcher=args.launcher,
                launcher_home=args.launcher_home, resources=args.resources,
                creative=True, append_world=False,
            )
            control = FixtureWorld(args.ctl, socket, {}, launch=())
            freeze(control)
            persisted = control.call("command", "/execute as @e[type=minecraft:item] run data get entity @s Item").get("chat", [])
            if not any("create:iron_sheet" in line for line in persisted):
                raise RuntimeError(f"Press output did not persist across reopen: {persisted}")
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


def verify(args):
    with managed_fixture(args) as control:
        sheet = control.command("/give @s create:iron_sheet 1")
        if "unknown item" in sheet.lower():
            raise RuntimeError(f"Create iron-sheet item was not loaded: {sheet}")
        control.command("/clear @s create:iron_sheet")
        control.command("/forceload add 0 0")
        control.commands((
            "/setblock 0 101 0 create:basin",
            f"/setblock {PRESS} create:mechanical_press",
            "/setblock 0 104 0 create:creative_motor[facing=down]",
            "/setblock 0 103 0 create:shaft[axis=y]",
            "/data merge block 0 104 0 {ScrollValue:256}",
            '/summon minecraft:item 0.5 101.25 0.5 {Item:{id:"minecraft:iron_ingot",count:1}}',
            "/tick step 8",
        ))
        control.call("command", "/tick unfreeze")
        time.sleep(0.5)
        control.call("command", "/tick freeze")
        all_items = control.call("command", "/execute as @e[type=minecraft:item] run data get entity @s Item").get("chat", [])
        if not any("create:iron_sheet" in line for line in all_items):
            raise RuntimeError(f"Press did not produce an Iron Sheet: {all_items}")
        if any("minecraft:iron_ingot" in line for line in all_items):
            raise RuntimeError(f"Press failed to consume its iron input: {all_items}")
        print("Typed Press processed ground iron and retained the output across save/reopen.")


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
    verify(args)


if __name__ == "__main__":
    main()
