#!/usr/bin/env python3
"""Check idle and boiler-powered Steam Whistle state across cold world reopen."""
import argparse
from pathlib import Path

from fixture_world import ROOT, fixture_world

WHISTLE = (9, 171, 20)
EXTENSIONS = ((9, 172, 20), (9, 173, 20))


def state(control, pos):
    return control.call("block", *pos)["state"]


def data(control, path):
    suffix = f" {path}" if path else ""
    return control.command(f"/data get block {' '.join(map(str, WHISTLE))}{suffix}")


def step(control, count):
    control.command(f"/tick step {count}")
    control.call("wait", count + 4)


def assert_setup(control, *, powered, steam):
    expected = "powered=true" if powered else "powered=false"
    if expected not in state(control, WHISTLE):
        raise RuntimeError(f"Whistle power state was not retained: {state(control, WHISTLE)}")
    if "shape=double" not in state(control, EXTENSIONS[0]) or "shape=single" not in state(control, EXTENSIONS[1]):
        raise RuntimeError("Whistle extension shape was not retained across reopen.")
    if not all("size=large" in state(control, pos) for pos in (WHISTLE, *EXTENSIONS)):
        raise RuntimeError("Whistle octave was not retained across reopen.")
    nbt = data(control, "")
    if "Pitch: 3" not in nbt:
        raise RuntimeError(f"Whistle pitch did not survive reopen: {nbt}")
    if steam and "Steam: 1" not in nbt:
        raise RuntimeError(f"Boiler-driven whistle activation did not resume: {nbt}")


def install(control, *, active):
    control.commands((
        "/setblock 9 170 20 create:fluid_tank",
        "/setblock 9 169 20 minecraft:magma_block",
        "/setblock 9 171 20 create:steam_whistle[facing=north,powered=false,size=large,wall=false]",
        "/setblock 9 172 20 create:steam_whistle_extension[shape=double,size=large]",
        "/setblock 9 173 20 create:steam_whistle_extension[shape=single,size=large]",
        f"/setblock 10 171 20 {'minecraft:redstone_block' if active else 'minecraft:air'}",
    ))


def run(args):
    for active in (False, True):
        label = "Active" if active else "Idle"
        with fixture_world(args, f"Whistle{label}Reopen", pack=args.pack,
                           artifact_dir=ROOT / ".local/app-1994") as control:
            install(control, active=active)
            step(control, 24)
            if active:
                before = data(control, "")
                if "Steam: 1" not in before:
                    raise RuntimeError(f"Fixture did not activate the boiler-powered whistle: {before}")
            assert_setup(control, powered=active, steam=active)
            control.command("/save-all")
            control.restart()
            step(control, 4)
            assert_setup(control, powered=active, steam=active)
    print("Idle and boiler-powered Steam Whistles retained pitch, extension shape, octave and power across cold reopen.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    run(parser.parse_args())
