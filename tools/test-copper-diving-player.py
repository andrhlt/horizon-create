#!/usr/bin/env python3
"""Replay original worn Copper Backtank air use as a real Horizon player."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
ENV = {"HORIZON_NO_AUDIO": "1"}
TANK = "create:copper_backtank"
STORED = re.compile(r'"create:banktank_air":\s*(\d+)')


def run(args, scratch):
    with (ROOT / "fixtures/copper-diving-player-java.csv").open() as file:
        case = "potion" if args.potion else "ordinary"
        rows = [row for row in csv.DictReader(file) if row.get("case", "ordinary") == case]
    assert rows, case
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, "CopperDivingPlayer", env=ENV, pack=args.pack))
        actor, player = host, "@s"
        if args.lan:
            player = "DivingGuest"
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            actor = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=False,
                scenario="copper-diving-player", pack=args.pack, env=ENV))
            mp.until("diving guest joins", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]))
        host.call("command", f"/gamemode survival {player}")
        host.commands((
            "/fill 5 169 19 15 169 28 minecraft:stone",
            "/fill 5 170 19 15 175 28 minecraft:air",
            "/fill 8 170 21 10 173 23 minecraft:stone",
            "/fill 9 170 22 9 173 22 minecraft:water",
            f"/tp {player} 9.5 170 25.5",
            f"/attribute {player} minecraft:gravity base set 0",
        ))
        host.command(f"/item replace entity {player} armor.head with create:copper_diving_helmet")
        host.command("/setblock 9 170 24 create:copper_backtank")
        host.command(f"/data merge block 9 170 24 {{Air:{rows[0]['tank']}}}")
        actor.call("interact", 9, 170, 24, "south")
        mp.until("charged tank is equipped",
                 lambda: TANK in host.command(f"/data get entity {player} equipment.chest"))
        start = host.clock()
        phase = int(rows[0]["phase"])
        for tick in range(start + 1, start + (phase - start) % 20 + 1):
            host.step_to(tick)
        start = host.clock()
        if args.potion:
            host.command(f"/effect give {player} minecraft:water_breathing 120 0 true")
        host.command(f"/tp {player} 9.5 170 22.5")
        mp.until("the player enters the water", lambda:
                 abs(actor.call("state")["player"]["position"][2] - 22.5) < 0.1)

        def state():
            tank = host.command(f"/data get entity {player} equipment.chest")
            remaining = STORED.search(tank)
            if args.lan:
                air = next(guest["air"] for guest in host.call("lan", "status")["guests"]
                           if guest["name"] == player)
            else:
                air = actor.call("state")["player"]["air"]
            return air, int(remaining[1]) if remaining else None

        mp.until("tank armor sync reaches the player", lambda: state()[1] == int(rows[0]["tank"]))
        differences = []
        for row in rows:
            tick = int(row["tick"])
            if tick:
                host.step_to(start + tick)
            wanted = (int(row["air"]), int(row["tank"]))
            actual = state()
            if tick and int(rows[tick - 1]["tank"]) > wanted[1] and actual[1] == int(rows[tick - 1]["tank"]):
                try:
                    mp.until("worn tank update", lambda: state()[1] == wanted[1], seconds=1)
                except RuntimeError:
                    pass
                actual = state()
            if actual != wanted:
                differences.append((tick, actual, wanted))
        assert not differences, (len(differences), differences[:12])

        def client_gear():
            chest = next(slot for slot in actor.call("inventory")["armor"] if slot["part"] == "chest")
            component = STORED.search(chest.get("components", ""))
            return (chest.get("item"), int(component[1]) if component else None,
                    actor.call("state")["player"]["air"])

        final_state = (TANK, int(rows[-1]["tank"]), int(rows[-1]["air"]))
        try:
            mp.until("the wearer receives the final air and charge", lambda: client_gear() == final_state)
        except RuntimeError as error:
            raise AssertionError((client_gear(), final_state)) from error
        print(f"Player air and worn tank air matched all {len(rows)} Java ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--potion", action="store_true")
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    with TemporaryDirectory(prefix="hc-copper-diving-player-", dir="/private/tmp") as scratch:
        run(parser.parse_args(), Path(scratch))
