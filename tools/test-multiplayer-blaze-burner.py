#!/usr/bin/env python3
"""Fuel a Blaze Burner as a LAN guest and observe the host-authoritative state."""

import argparse
import importlib
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

mp = importlib.import_module("test-multiplayer")
BURNER = (30, 97, 30)
GUEST_POSITION = (26.5, 97.0, 30.5)


def fuel_remaining(host):
    text = host.command(f"/data get block {BURNER[0]} {BURNER[1]} {BURNER[2]} burnTimeRemaining")
    match = re.search(r": (\d+)$", text)
    if not match:
        raise RuntimeError(f"The host cannot read burner fuel time: {text}")
    return int(match[1])


def run(args):
    with TemporaryDirectory(prefix="hc-burner-lan-") as directory:
        with fixture_world(args, "Blaze-burner-LAN", render=True, pack=args.pack) as host:
            # Keep the guest clear of the host. Overlapping player hitboxes
            # intercept the guest's block click before it reaches the burner.
            host.commands((
                "/fill 25 96 27 32 96 32 minecraft:smooth_stone",
                "/fill 25 97 27 32 100 32 minecraft:air",
                f"/setblock {BURNER[0]} {BURNER[1]} {BURNER[2]} create:blaze_burner[blaze=smouldering,facing=west]",
                f"/data merge block {BURNER[0]} {BURNER[1]} {BURNER[2]} {{fuelLevel:0,burnTimeRemaining:0}}",
                "/setworldspawn 1000 100 1000",
                "/gamemode survival",
            ))
            name = "BurnerGuest"
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            with mp.joined_client(
                args, Path(directory), f"127.0.0.1:{port}", name, render=True,
                scenario="blaze-burner-fuel", pack=args.pack,
            ) as guest:
                mp.until("the burner guest to join", lambda: any(
                    player["name"] == name and player["placed"]
                    for player in host.call("lan", "status")["guests"]
                ))
                host.commands((
                    f"/gamemode survival {name}",
                    f"/tp {name} {GUEST_POSITION[0]} {GUEST_POSITION[1]} {GUEST_POSITION[2]} -90 20",
                    f"/item replace entity {name} hotbar.0 with minecraft:coal 1",
                ))
                mp.until("the guest to receive coal", lambda:
                    guest.call("inventory")["counts"].get("minecraft:coal", 0) == 1)
                mp.until("the guest to reach the burner", lambda:
                    guest.call("state")["player"]["position"] == list(GUEST_POSITION))
                mp.until("the guest to see the burner", lambda:
                    guest.call("block", *BURNER)["block"] == "create:blaze_burner")
                guest.call("select", "minecraft:coal")
                held = host.command(f"/data get entity {name} SelectedItem")
                if "minecraft:coal" not in held:
                    raise RuntimeError(f"The LAN host did not observe guest coal in hand before fueling: {held}")
                guest.call("look-at", BURNER[0] + 0.5, BURNER[1] + 0.5, BURNER[2] + 0.5)
                mp.until("the guest to target the burner", lambda:
                    (guest.call("looking-at").get("block") or {}).get("pos") == list(BURNER))
                before = fuel_remaining(host)
                guest.call("mouse", "right", "click")
                try:
                    mp.until("the host to observe guest fueling", lambda:
                        fuel_remaining(host) > before + 500)
                except RuntimeError as error:
                    raise RuntimeError(
                        f"{error}; before={before}, after={fuel_remaining(host)}, "
                        f"guest_inventory={guest.call('inventory')}, "
                        f"host_inventory={host.command(f'/data get entity {name} Inventory')}, "
                        f"host_hand={host.command(f'/data get entity {name} SelectedItem')}, "
                        f"host_burner_data={host.command(f'/data get block {BURNER[0]} {BURNER[1]} {BURNER[2]}')}, "
                        f"guest_target={guest.call('looking-at')}, "
                        f"host_block={host.call('block', *BURNER)}"
                    ) from error
                mp.until("the guest's coal to be consumed", lambda:
                    guest.call("inventory")["counts"].get("minecraft:coal", 0) == 0)
                state = host.call("block", *BURNER)["state"]
                if "blaze=kindled" not in state:
                    raise RuntimeError(f"The host did not observe kindled heat after guest fueling: {state}")
                mp.until("the guest to observe kindled heat", lambda:
                    "blaze=kindled" in guest.call("block", *BURNER)["state"])
    print("The LAN guest consumed coal; both players observed the kindled burner state.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
