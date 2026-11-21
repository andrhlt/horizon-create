#!/usr/bin/env python3
"""Check a LAN guest can extend and resize a Steam Whistle with host convergence."""
import argparse
from contextlib import ExitStack
from pathlib import Path
import tempfile

from fixture_world import ROOT
import importlib.util

_spec = importlib.util.spec_from_file_location("multiplayer", ROOT / "tools/test-multiplayer.py")
mp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mp)

WHISTLE = (9, 171, 20)
EXTENSION = (9, 172, 20)
HOST_POS = (12.5, 170.0, 23.5)
GUEST_POS = (9.5, 170.0, 23.5)


def state(client, pos):
    return client.call("block", *pos)["state"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="hc-app1994-whistle-lan-") as tmp:
        scratch = Path(tmp)
        with ExitStack() as stack:
            address, server = stack.enter_context(mp.dedicated(
                args, scratch, scenario="app1994-whistle-lan", pack=args.pack,
                artifact_dir=ROOT / ".local/app-1994"))
            host = stack.enter_context(mp.joined_client(
                args, scratch, address, "WhistleHost", scenario="app1994-whistle-lan", pack=args.pack,
                artifact_dir=ROOT / ".local/app-1994"))
            guest = stack.enter_context(mp.joined_client(
                args, scratch, address, "WhistleGuest", scenario="app1994-whistle-lan", pack=args.pack,
                artifact_dir=ROOT / ".local/app-1994"))

            server("fill 4 169 16 15 169 27 minecraft:stone")
            server("fill 4 170 16 15 177 27 minecraft:air")
            server("setblock 9 170 20 create:fluid_tank")
            server("setblock 9 171 20 create:steam_whistle[facing=north,powered=false,size=medium,wall=false]")
            server("gamemode survival WhistleHost")
            server("gamemode survival WhistleGuest")
            server("tp WhistleHost 12.5 170 23.5")
            server("tp WhistleGuest 9.5 170 23.5")
            mp.until("both clients to see the whistle", lambda:
                     "create:steam_whistle[" in state(host, WHISTLE)
                     and "create:steam_whistle[" in state(guest, WHISTLE))
            mp.until("both players to reach the fixture", lambda:
                     host.call("state")["player"]["position"] == list(HOST_POS)
                     and guest.call("state")["player"]["position"] == list(GUEST_POS))

            guest.call("select", "create:steam_whistle")
            guest.call("look-at", 9.5, 171.5, 20.5)
            mp.until("guest targets the whistle", lambda:
                     (guest.call("looking-at").get("block") or {}).get("pos") == list(WHISTLE))
            guest.call("mouse", "right", "click")
            mp.until("guest grows the whistle", lambda: "shape=single" in state(host, EXTENSION)
                     and "shape=single" in state(guest, EXTENSION))

            guest.call("select", "create:wrench")
            guest.call("mouse", "right", "click")
            mp.until("guest changes the octave", lambda:
                     "size=large" in state(host, WHISTLE)
                     and "size=large" in state(guest, WHISTLE)
                     and "size=large" in state(host, EXTENSION)
                     and "size=large" in state(guest, EXTENSION))
    print("Guest extension growth and wrench octave changes converged on host and guest.")


if __name__ == "__main__":
    main()
