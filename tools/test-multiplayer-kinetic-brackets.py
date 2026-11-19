#!/usr/bin/env python3
"""Check guest bracket replacement, item return, and wrench removal on the host."""

import argparse
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


def load(name):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


brackets = load("test-kinetic-brackets")
multiplayer = load("test-multiplayer")
GUEST = "BracketGuest"


def held(control, item):
    return control.call("inventory")["counts"].get(item, 0)


def on_shaft(host):
    return brackets.attached(host.command(f"/data get block {brackets.coords(brackets.SHAFT)} Bracket"))


def verify(args):
    with fixture_world(args, "KineticBracketsLAN", render=True, pack=args.pack) as host:
        brackets.setup(host)
        host.step_to(host.clock() + 1)
        brackets.press(host, brackets.WOOD, brackets.SHAFT, "up")
        if on_shaft(host) != ("wood", "shaft", "up", "true") or held(host, brackets.WOOD) != 1:
            raise RuntimeError("Host did not attach a single wooden bracket to the shaft.")
        host.command("/tp @s 10.5 101 -7.5")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hc-bracket-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, GUEST, render=True, scenario="multiplayer-brackets", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/tp {GUEST} 8.5 101 -12.0",
                f"/item replace entity {GUEST} hotbar.0 with {brackets.METAL} 2",
                f"/item replace entity {GUEST} hotbar.1 with {brackets.WRENCH} 1",
            ))
            multiplayer.until("the guest to reach the shaft", lambda: (
                guest.call("state")["player"]["position"] == [8.5, 101.0, -12.0]
            ))
            host.step_to(host.clock() + 1)
            multiplayer.until("the guest to receive the metal brackets", lambda: held(guest, brackets.METAL) == 2)
            brackets.press(guest, brackets.METAL, brackets.SHAFT, "up", teleport=False)
            multiplayer.until("the metal bracket to replace wood on the server", lambda: (
                on_shaft(host) == ("metal", "shaft", "up", "true")
            ))
            multiplayer.until("the guest to receive the wooden bracket", lambda: (
                held(guest, brackets.WOOD) == 1 and held(guest, brackets.METAL) == 1
            ))
            if args.frames:
                guest.call("screenshot", args.frames / "guest-metal.png")
            brackets.press(guest, brackets.WRENCH, brackets.SHAFT, "up", teleport=False)
            multiplayer.until("the wrench to remove the server bracket and refund the metal", lambda: (
                on_shaft(host)[0] == "none" and held(guest, brackets.METAL) == 2
            ))
            if args.frames:
                guest.call("screenshot", args.frames / "guest-removed.png")
    print("The host attached wood and the guest replaced it and used the wrench, receiving both original brackets.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--frames", type=Path)
    args = parser.parse_args()
    if args.frames:
        args.frames.mkdir(parents=True, exist_ok=True)
    verify(args)


if __name__ == "__main__":
    main()
