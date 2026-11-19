#!/usr/bin/env python3
"""Check charged, named Backtank placement and pickup."""

import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
POS = (8, 170, 21)
SUPPORT = (8, 169, 21)
WATER = "minecraft:water[level=0]"
NAME = "Dive Supply"
CHARGE = 284


def inspect(host, actor, player, phase, tank):
    block = host.call("block", *POS)
    chest = host.command(f"/data get entity {player} equipment.chest")
    chest_count = "1" if f'id: "{tank}"' in chest else "0"
    inventory = actor.call("inventory")
    held_count = sum(stack.get("count", 0) for stack in inventory["hotbar"]
                     if stack.get("item") == tank)
    assert inventory["counts"].get(tank, 0) == held_count + int(chest_count)
    if phase == "place":
        state = block["state"]
        facing = re.search(r"\bfacing=(\w+)", state).group(1)
        water = re.search(r"\bwaterlogged=(\w+)", state).group(1)
        stored = host.command("/data get block 8 170 21")
        charge = re.search(r"\bAir: (\d+)", stored).group(1)
        component = re.search(r'"create:banktank_air": (\d+)', stored).group(1)
        assert component == charge, stored
        name = re.search(r'"minecraft:custom_name": "([^"]+)"', stored).group(1)
    else:
        facing = "-"
        water = str(block["state"] == WATER).lower()
        charge = re.search(r'"create:banktank_air": (\d+)', chest).group(1)
        name = re.search(r'"minecraft:custom_name": "([^"]+)"', chest).group(1)
    return dict(phase=phase, block=block["block"], facing=facing, water=water,
                air=charge, name=name, held=str(held_count), chest=chest_count)


def run(args):
    mode = "LAN" if args.lan else "Solo"
    tank = f"create:{args.material}_backtank"
    placed_state = f"{tank}[facing=south,waterlogged=true]"
    with (ROOT / f"fixtures/{args.material}-backtank-pickup-java.csv").open(newline="") as file:
        expected = list(csv.DictReader(file))
    with ExitStack() as scope:
        env = {"HORIZON_NO_AUDIO": "1"}
        host = scope.enter_context(fixture_world(args, f"BacktankPickup{mode}", pack=args.pack, env=env))
        actor, player = host, "@s"
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            player = "BacktankGuest"
            temporary = Path(scope.enter_context(TemporaryDirectory(prefix="hc-backtank-")))
            actor = scope.enter_context(mp.joined_client(args, temporary, f"127.0.0.1:{port}", player,
                                                        scenario="backtank-pickup", pack=args.pack, env=env))
            mp.until("the guest to join", lambda: any(guest["name"] == player and guest["placed"]
                     for guest in host.call("lan", "status")["guests"]))
        host.commands((
            "/fill 5 169 19 11 169 27 minecraft:stone",
            "/fill 5 170 19 11 174 27 minecraft:air",
            "/setblock 8 170 21 minecraft:water",
            f"/tp {player} 8.5 170 24.5 180 30",
            f"/gamemode survival {player}",
            f'/item replace entity {player} hotbar.0 with {tank}[minecraft:custom_name="{NAME}"]',
        ))
        mp.until("the actor to hold the named tank", lambda: actor.call("inventory")["counts"].get(tank) == 1)
        actor.call("interact", *SUPPORT, "up")
        mp.until("the placed tank", lambda: host.call("block", *POS)["state"] == placed_state)
        assert "Modified block data" in host.command(f"/data merge block 8 170 21 {{Air:{CHARGE}}}")
        actor.call("interact", *POS, "south")
        mp.until("equipment synchronization", lambda: f'id: "{tank}"' in
                 host.command(f"/data get entity {player} equipment.chest"))
        moved = host.command(f"/item replace entity {player} hotbar.0 from entity {player} armor.chest")
        assert "Replaced 1 slot" in moved, moved
        host.command(f"/item replace entity {player} armor.chest with minecraft:air")
        mp.until("the actor to hold the charged tank", lambda: actor.call("inventory")["counts"].get(tank) == 1)
        tick = host.clock()
        actor.call("interact", *SUPPORT, "up")
        mp.until("the actor to see the charged tank", lambda: actor.call("block", *POS)["state"] == placed_state)
        mp.until("the actor to consume the held tank", lambda: tank not in actor.call("inventory")["counts"])
        placed = inspect(host, actor, player, "place", tank)
        assert host.clock() == tick
        actor.call("interact", *POS, "south")
        mp.until("the actor to see restored source water", lambda: actor.call("block", *POS)["state"] == WATER)
        mp.until("the actor to receive chest equipment", lambda: actor.call("inventory")["counts"].get(tank) == 1)
        picked = inspect(host, actor, player, "pickup", tank)
        assert host.clock() == tick
    assert [placed, picked] == expected, (expected, placed, picked)
    print(f"{mode}: {args.material.title()} Backtank matched Java: {placed}; {picked}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--material", choices=("copper", "netherite"), default="copper")
    run(parser.parse_args())
