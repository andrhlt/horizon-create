#!/usr/bin/env python3
"""Compare the original Cardboard armor fuel with a real Horizon furnace."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
recycle = import_module("test-window-recycling")


def trace(world, reference, furnaces):
    queries = tuple(f"/data get block {recycle.coords(position)}" for position in furnaces.values())
    rows = []
    start = world.clock()
    for tick in range(len(reference) // len(furnaces)):
        if tick:
            world.step_to(start + tick)
        for item, reply in zip(furnaces, world.commands(queries), strict=True):
            fuel_slot = next((tag for tag in re.findall(r"\{[^{}]*\}", reply) if "Slot: 1" in tag), "")
            row = recycle.read_furnace(tick, item, reply, "")
            count = recycle.numeric(fuel_slot, "count") if fuel_slot else "0"
            rows.append([*row[:5], count, *row[7:]])
    differences = [(want, got) for want, got in zip(reference, rows, strict=True) if want != got]
    if differences:
        raise AssertionError(f"{len(differences)} furnace differences: {differences[:6]}")
    print(f"All {len(rows)} Java furnace samples matched across the four Cardboard armor fuels.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/cardboard-armor-fuel-java.csv").open(newline="") as source:
        reader = csv.reader(source)
        next(reader)
        reference = list(reader)
    items = dict.fromkeys(row[1] for row in reference)
    furnaces = {item: (5 + 2 * index, 180, 23) for index, item in enumerate(items)}
    scenario = "CardboardArmorFuelLAN" if args.lan else "CardboardArmorFuel"
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, scenario, render=args.lan, pack=args.pack))
        world.commands((
            "/fill 3 179 21 13 179 26 minecraft:smooth_stone",
            "/tp @s 8.5 180 22.5",
            *(f"/setblock {recycle.coords(position)} minecraft:furnace" for position in furnaces.values()),
        ))
        guest = None
        first = next(iter(furnaces.values()))
        if args.lan:
            name = "FuelGuest"
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            directory = Path(stack.enter_context(TemporaryDirectory(prefix="hc-fuel-")))
            guest = stack.enter_context(mp.joined_client(
                args, directory, f"127.0.0.1:{port}", name, render=True, scenario="cardboard-fuel", pack=args.pack,
            ))
            mp.until("the fuel guest to join", lambda: any(
                player["name"] == name and player["placed"] for player in world.call("lan", "status")["guests"]
            ))
            world.commands((f"/gamemode survival {name}", f"/tp {name} 5.5 180 25.5"))
            mp.until("the fuel guest to reach the furnace", lambda:
                     tuple(guest.call("state")["player"]["position"]) == (5.5, 180, 25.5))
            mp.until("the fuel guest to see the furnace", lambda: guest.call("block", *first)["block"] == "minecraft:furnace")
        world.commands(
            command for item, position in furnaces.items()
            for command in (f"/item replace block {recycle.coords(position)} container.0 with minecraft:raw_iron",
                            f"/item replace block {recycle.coords(position)} container.1 with {item}")
        )
        trace(world, reference, furnaces)
        if guest:
            guest.call("interact", *first, "south")
            mp.until("the guest to see the smelted iron", lambda: any(
                (slot["stack"] or {}).get("item") == "minecraft:iron_ingot" for slot in guest.call("menu")["slots"]
            ))
            guest.call("click-slot", 302, "shift")
            mp.until("the guest to collect the iron", lambda: mp.count(guest, "minecraft:iron_ingot") == 1)
            print("The LAN guest collected the finished iron ingot.", flush=True)


if __name__ == "__main__":
    main()
