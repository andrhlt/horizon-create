#!/usr/bin/env python3
"""Exercise the live Brass Tunnel mode board and a side item filter."""

import argparse
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/items/brass_tunnel_split.nbt")
MODES = ("Split", "Forced Split", "Round Robin", "Forced Round Robin",
         "Prefer Nearest", "Randomize", "Synchronize Inputs")
TUNNELS = ((6, 98, -11), (6, 98, -10), (6, 98, -9))
CENTER = TUNNELS[1]


def run(args):
    with fixture_world(args, "Brass-tunnel-settings", STRUCTURE, render=True) as control:
        control.commands((
            "/place template create:gametest/items/brass_tunnel_split 3 96 -12",
            "/setblock 7 98 -13 minecraft:smooth_stone",
            "/gamemode survival",
            "/tp @s 7.5 99 -12.5 25 22",
        ))
        control.call("wait", 3)
        control.call("interact", *CENTER, "up")
        control.call("wait", 4)
        targets = [f"/data get block {x} {y} {z} ScrollValue" for x, y, z in TUNNELS]
        for value, mode in enumerate(MODES):
            control.call("click-button", mode)
            control.call("wait", 3)
            for reply in control.commands(targets):
                if not reply.endswith(f" {value}"):
                    raise RuntimeError(f"{mode} failed to update the whole connected tunnel group: {reply}")
        if args.visual:
            control.call("screenshot", ROOT / ".local/brass-tunnel-settings.png")
        control.call("key", "esc", "tap")
        control.commands((
            "/tp @s 8.8 98 -9.5 90 0",
            "/item replace entity @s hotbar.0 with minecraft:copper_ingot 2",
        ))
        control.call("wait", 3)
        control.call("key", "1", "tap")
        x, y, z = CENTER
        control.call("look-at", x + 0.98, y + 0.8, z + 0.5)
        control.call("mouse", "right", "click")
        control.call("wait", 3)
        command = f"/data get block {x} {y} {z} Filters"
        filters = control.command(command)
        if "minecraft:copper_ingot" not in filters or "Side: 5" not in filters:
            raise RuntimeError(f"East filter was not assigned by the held item: {filters}")
        inventory = control.command("/data get entity @s Inventory")
        if not re.search(r"count: 2\b", inventory):
            raise RuntimeError(f"Setting a filter consumed an item: {inventory}")
        control.call("key", "2", "tap")
        control.call("mouse", "right", "click")
        control.call("wait", 3)
        if "minecraft:copper_ingot" in control.command(command):
            raise RuntimeError("Clicking the filter with an empty hand did not clear it.")
    print("All seven mode controls updated the connected tunnels, and the East filter was set and cleared in survival.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
