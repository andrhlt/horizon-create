#!/usr/bin/env python3
"""Exercise the live Brass Tunnel mode board and a side item filter."""

import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/items/brass_tunnel_split.nbt")
MODES = ("Split", "Forced Split", "Round Robin", "Forced Round Robin",
         "Prefer Nearest", "Randomize", "Synchronize Inputs")
TUNNELS = ((6, 98, -11), (6, 98, -10), (6, 98, -9))
CENTER = TUNNELS[1]
GUEST = "TunnelGuest"
multiplayer = import_module("test-multiplayer")


def run(args):
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "Brass-tunnel-settings", STRUCTURE, render=True))
        actor, player = host, "@s"
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-tunnel-settings-")))
            actor = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", GUEST, render=True,
                scenario="brass-tunnel-settings-lan",
            ))
            multiplayer.until("the tunnel settings guest to join", lambda: any(
                guest["name"] == GUEST and guest["placed"]
                for guest in host.call("lan", "status")["guests"]
            ))
            player = GUEST

        host.commands((
            "/place template create:gametest/items/brass_tunnel_split 3 96 -12",
            "/setblock 7 98 -13 minecraft:smooth_stone",
            f"/gamemode survival {player}",
            f"/tp {player} 7.5 99 -12.5 25 22",
        ))
        actor.call("wait", 3)
        actor.call("interact", *CENTER, "up")
        actor.call("wait", 4)
        targets = [f"/data get block {x} {y} {z} ScrollValue" for x, y, z in TUNNELS]
        for value, mode in enumerate(MODES):
            actor.call("click-button", mode)
            actor.call("wait", 3)
            for reply in host.commands(targets):
                if not reply.endswith(f" {value}"):
                    raise RuntimeError(f"{mode} failed to update the whole connected tunnel group: {reply}")
        if args.visual:
            actor.call("screenshot", ROOT / ".local/brass-tunnel-settings.png")
        actor.call("key", "esc", "tap")
        host.commands((
            f"/tp {player} 8.8 98 -9.5 90 0",
            f"/item replace entity {player} hotbar.0 with minecraft:copper_ingot 2",
        ))
        actor.call("wait", 3)
        actor.call("key", "1", "tap")
        x, y, z = CENTER
        actor.call("look-at", x + 0.98, y + 0.8, z + 0.5)
        actor.call("mouse", "right", "click")
        actor.call("wait", 3)
        command = f"/data get block {x} {y} {z} Filters"
        filters = host.command(command)
        if "minecraft:copper_ingot" not in filters or "Side: 5" not in filters:
            raise RuntimeError(f"East filter was not assigned by the held item: {filters}")
        inventory = host.command(f"/data get entity {player} Inventory")
        if not re.search(r"count: 2\b", inventory):
            raise RuntimeError(f"Setting a filter consumed an item: {inventory}")
        actor.call("key", "2", "tap")
        actor.call("mouse", "right", "click")
        actor.call("wait", 3)
        if "minecraft:copper_ingot" in host.command(command):
            raise RuntimeError("Clicking the filter with an empty hand did not clear it.")
    print("All seven mode controls and the East filter updated from the "
          f"{'LAN guest' if args.lan else 'survival player'}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--lan", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
