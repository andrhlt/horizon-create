#!/usr/bin/env python3
"""Check a LAN guest can stop/restart the steam-engine boiler pump and both clients converge."""

import argparse
from contextlib import ExitStack
from pathlib import Path
import shutil
import tempfile
import time

from fixture_world import ROOT
import importlib.util

_spec = importlib.util.spec_from_file_location("multiplayer", ROOT / "tools/test-multiplayer.py")
mp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mp)

STRUCTURE = Path("gametest/fluids/steam_engine.nbt")
ARTIFACTS = ROOT / ".local/app-1993"
LEVER = (7, 98, -9)
HOST_POS = (9.5, 99.0, -8.5)
GUEST_POS = (5.5, 99.0, -8.5)


def powered(client):
    state = client.call("block", *LEVER)["state"]
    if "minecraft:lever[" not in state:
        raise RuntimeError(f"Expected the steam fixture pump lever, got {state}")
    return "powered=true" in state


def sees_lever(client):
    return "minecraft:lever[" in client.call("block", *LEVER).get("state", "")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--structure", type=Path,
                        default=ROOT / ".local/fixtures/data/create/structure/gametest/fluids/steam_engine.nbt")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="hc-app1993-steam-lan-") as tmp:
        scratch = Path(tmp)
        with ExitStack() as stack:
            address, server_command = stack.enter_context(mp.dedicated(
                args, scratch, scenario="app1993-steam-lan", pack=args.pack, artifact_dir=ARTIFACTS))
            template = scratch / "server/Parity/generated/create/structures" / STRUCTURE
            template.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(args.structure, template)
            server_command("reload")
            logfile = ARTIFACTS / "app1993-steam-lan-server.log"
            mp.until("the server to accept the template reload",
                     lambda: "Reloading!" in logfile.read_text(errors="replace"), seconds=20)
            time.sleep(2)  # Let the server finish applying the resource reload.
            host = stack.enter_context(mp.joined_client(
                args, scratch, address, "SteamHost", scenario="app1993-steam-lan",
                pack=args.pack, artifact_dir=ARTIFACTS))
            guest = stack.enter_context(mp.joined_client(
                args, scratch, address, "SteamGuest", scenario="app1993-steam-lan",
                pack=args.pack, artifact_dir=ARTIFACTS))

            server_command("place template create:gametest/fluids/steam_engine 3 96 -12")
            server_command("fill 4 98 -14 14 98 -5 minecraft:smooth_stone")
            server_command("fill 4 99 -13 14 104 -6 minecraft:air")
            server_command("setblock 7 98 -9 minecraft:lever[face=floor,facing=west,powered=false]")
            server_command("gamemode survival SteamHost")
            server_command("gamemode survival SteamGuest")
            server_command("tp SteamHost 9.5 99 -8.5")
            server_command("tp SteamGuest 5.5 99 -8.5")
            mp.until("both clients to receive the steam fixture lever",
                     lambda: sees_lever(host) and sees_lever(guest), seconds=20)
            mp.until("both clients to observe the initial unpowered lever",
                     lambda: not powered(host) and not powered(guest))
            mp.until("both survival players to be in lever range", lambda:
                     host.call("state")["player"]["position"] == list(HOST_POS)
                     and guest.call("state")["player"]["position"] == list(GUEST_POS))
            guest.call("interact", *LEVER, "up")
            mp.until("host and guest to observe the guest's lever action",
                     lambda: powered(host) and powered(guest))
            host.call("interact", *LEVER, "up")
            mp.until("host and guest to observe the host restart action",
                     lambda: not powered(host) and not powered(guest))
    print("Steam fixture pump stop/restart actions from guest and host converged on both LAN clients.")


if __name__ == "__main__":
    main()
