#!/usr/bin/env python3
"""Exercise the real Create wheat milling recipe and output backpressure."""

import argparse
from contextlib import contextmanager
from pathlib import Path
from shutil import copy2
import tempfile

from fixture_world import FixtureWorld, install_pack
from launcher_managed import launch_managed


MILL = (0, 100, 0)
PROCESSING_TICKS = 155


@contextmanager
def managed_fixture(args, pack):
    with tempfile.TemporaryDirectory(prefix="hc-managed-millstone-") as tmp:
        scratch = Path(tmp)
        socket = scratch / "ctl.sock"
        game = scratch / "game"
        install_pack(game, pack)
        mods = args.instance_dir / "horizon-mods"
        mods.mkdir(parents=True, exist_ok=True)
        copy2(pack, mods / "create.hmod")
        (args.instance_dir / "horizon-mods.txt").write_text(
            "mod.create:true\n", encoding="utf-8"
        )
        process, log, log_path, world = launch_managed(
            args.client.parent,
            socket,
            game,
            "TypedMillstoneProduction",
            instance=args.instance,
            launcher=args.launcher,
            launcher_home=args.launcher_home,
            resources=args.resources,
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
                args.client.parent, socket, game, world,
                instance=args.instance, launcher=args.launcher,
                launcher_home=args.launcher_home, resources=args.resources,
                creative=True, append_world=False,
            )
            control = FixtureWorld(args.ctl, socket, {}, launch=())
            control.call("script", script='command "/tick freeze"\n')
            return control
        control.reopen = reopen
        try:
            control.call("script", script='command "/tick freeze"\n')
            yield control
        finally:
            if socket.exists():
                control.stop()
            process.wait(timeout=30)
            if not log.closed:
                log.close()
            args.evidence_dir.mkdir(parents=True, exist_ok=True)
            for source, name in (
                (log_path, "managed-play.log"),
                (args.instance_dir / "logs/latest.log", "latest.log"),
            ):
                if source.is_file():
                    copy2(source, args.evidence_dir / name)


def xyz(pos):
    return " ".join(map(str, pos))


def block_data(control):
    return control.command(f"/data get block {xyz(MILL)}")


def advance(control, ticks):
    for _ in range(ticks):
        control.call("command", "/tick step 1")


def require_flour(data):
    if "create:wheat_flour" not in data or "count: 1" not in data:
        raise RuntimeError(f"Real wheat milling did not produce one flour: {data}")


def verify(args):
    with managed_fixture(args, args.pack) as control:
        control.command("/forceload add 0 0")
        flour_probe = control.command("/give @s create:wheat_flour 1")
        if "unknown item" in flour_probe.lower():
            raise RuntimeError(f"Wheat Flour was not registered: {flour_probe}")
        control.command("/clear @s create:wheat_flour")
        control.commands((
            f"/setblock {xyz(MILL)} create:millstone",
            f"/data merge block {xyz(MILL)} {{Speed:16.0f}}",
            f"/item replace block {xyz(MILL)} container.0 with minecraft:wheat 1",
        ))
        advance(control, PROCESSING_TICKS)
        completed = block_data(control)
        if 'id: "minecraft:wheat"' in completed:
            raise RuntimeError(f"Real wheat input was not consumed: {completed}")
        require_flour(completed)

        control.call("save")
        control = control.reopen()
        reopened = block_data(control)
        require_flour(reopened)

        control.commands(tuple(
            f"/item replace block {xyz(MILL)} container.{slot} with create:wheat_flour 64"
            for slot in range(1, 10)
        ) + (f"/item replace block {xyz(MILL)} container.0 with minecraft:wheat 1",))
        advance(control, PROCESSING_TICKS)
        blocked = block_data(control)
        if 'id: "minecraft:wheat"' not in blocked:
            raise RuntimeError(f"Full output slot caused input loss: {blocked}")
        if "create:wheat_flour" not in blocked or "count: 64" not in blocked:
            raise RuntimeError(f"Full output slot changed unexpectedly: {blocked}")

        control.command(f"/item replace block {xyz(MILL)} container.1 with air")
        advance(control, PROCESSING_TICKS)
        recovered = block_data(control)
        if 'id: "minecraft:wheat"' in recovered:
            raise RuntimeError(f"Cleared output did not allow recovery: {recovered}")
        if "create:wheat_flour" not in recovered:
            raise RuntimeError(f"Recovery produced no flour: {recovered}")

    print("Typed Millstone matched real wheat milling, retained output across reopen, and conserved input under full output.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("resources", nargs="?", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--instance", required=True)
    parser.add_argument("--instance-dir", type=Path, required=True)
    parser.add_argument("--launcher", type=Path, required=True)
    parser.add_argument("--launcher-home", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path,
                        default=Path(__file__).resolve().parents[1] / ".local/app2136-millstone-evidence")
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
