#!/usr/bin/env python3
"""Check that a LAN guest retains Builder's Tea's bottle and Haste after rejoin."""

import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

mp = import_module("test-multiplayer")
GUEST = "TeaGuest"
TEA = "create:builders_tea"
BOTTLE = "minecraft:glass_bottle"


def joined(host):
    return any(player["name"] == GUEST and player["placed"]
               for player in host.call("lan", "status")["guests"])


def tea_state(host):
    return host.command(f"/data get entity {GUEST}")


def check_drink_state(host, guest, label):
    state = tea_state(host)
    counts = guest.call("inventory")["counts"]
    if counts.get(TEA, 0) != 0 or counts.get(BOTTLE, 0) != 1:
        raise AssertionError(f"{label}: guest inventory is {counts}")
    if "playerGameType: 0" not in state:
        raise AssertionError(f"{label}: guest is not in survival mode: {state}")
    for expected in ('id: \"minecraft:haste\"', "show_particles: 0b", "show_icon: 0b"):
        if expected not in state:
            raise AssertionError(f"{label}: missing {expected!r} in {state}")
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()

    with fixture_world(args, "BuildersTeaRejoin", render=True, pack=args.pack) as host:
        host.command("/gamerule naturalRegeneration false")
        address = f"127.0.0.1:{host.call('lan', 'open', 0, 'commands')['port']}"
        with TemporaryDirectory(prefix="hc-tea-rejoin-") as scratch:
            home = Path(scratch)
            for stage in ("drink", "rejoin"):
                with mp.joined_client(args, home, address, GUEST, render=True,
                                      scenario=f"builders-tea-{stage}", pack=args.pack) as guest:
                    mp.until(f"guest {stage} connection", lambda: joined(host))
                    if stage == "drink":
                        host.commands((f"/gamemode survival {GUEST}",
                                       f"/item replace entity {GUEST} hotbar.0 with {TEA} 1"))
                        mp.until("Builder's Tea to reach guest", lambda: mp.count(guest, TEA) == 1)
                        guest.call("select", TEA)
                        guest.call("mouse", "right", "down")
                        try:
                            mp.until("tea consumption and Haste", lambda:
                                     mp.count(guest, BOTTLE) == 1 and mp.count(guest, TEA) == 0
                                     and 'id: \"minecraft:haste\"' in tea_state(host))
                        finally:
                            guest.call("mouse", "right", "up")
                        before = check_drink_state(host, guest, "before disconnect")
                        print(f"Guest drank Tea: {before}", flush=True)
                    else:
                        mp.until("guest survival mode to restore", lambda:
                                 "playerGameType: 0" in tea_state(host))
                        state = check_drink_state(host, guest, "after rejoin")
                        print(f"Guest retained bottle and hidden Haste after rejoin: {state}", flush=True)
                if stage == "drink":
                    mp.until("guest disconnect", lambda: not joined(host))


if __name__ == "__main__":
    main()
