#!/usr/bin/env python3
"""Check Haunted Bell LAN convergence and save/reopen state retention."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world
import importlib

multiplayer = importlib.import_module("test-multiplayer")

BELL = "create:haunted_bell"
POS = (9, 170, 24)
POWER = (8, 170, 24)
GUEST = "HauntedBellGuest"


def state(actor):
    return actor.call("block", *POS)["state"]


def run(args):
    with fixture_world(args, "Peculiar-haunted-bells-lifecycle", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 7 169 26 11 169 22 minecraft:stone",
            f"/setblock {POS[0]} {POS[1]} {POS[2]} {BELL}[facing=north,attachment=floor,powered=false]",
            f"/setblock {POWER[0]} {POWER[1]} {POWER[2]} minecraft:air",
            "/gamemode survival",
        ))
        if host.call("block", *POS)["block"] != BELL:
            raise RuntimeError("Haunted Bell was not placed for lifecycle check.")
        port = host.call("lan", "open", 0, "commands", "force")["port"]
        with TemporaryDirectory(prefix="hcb-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
            scenario="peculiar-haunted-bell-lifecycle", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to join", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            multiplayer.until("the guest to see the idle Haunted Bell", lambda: "powered=false" in state(guest))
            host.command(f"/setblock {POWER[0]} {POWER[1]} {POWER[2]} minecraft:redstone_block")
            multiplayer.until("the guest to converge on powered state", lambda: "powered=true" in state(guest))
            host.command("/save-all flush")
            host.restart()
            if "powered=true" not in state(host):
                raise RuntimeError(f"Host Haunted Bell lost powered state across active reopen: {state(host)}")
            host.command(f"/setblock {POWER[0]} {POWER[1]} {POWER[2]} minecraft:air")
            if "powered=false" not in state(host):
                raise RuntimeError(f"Host Haunted Bell did not clear after active reopen: {state(host)}")
            host.command("/save-all flush")
            host.restart()
            if "powered=false" not in state(host):
                raise RuntimeError(f"Host Haunted Bell changed across reopen: {state(host)}")
    print("Haunted Bell host/guest redstone convergence, active powered save/reopen, and idle host save/reopen passed; guest disconnect on host restart is outside this bounded case.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
