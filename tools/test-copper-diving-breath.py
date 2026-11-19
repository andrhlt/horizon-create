#!/usr/bin/env python3
"""Compare submerged equipped and ordinary mobs against the pinned Java oracle."""
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
AIR = re.compile(r"\bAir: (-?\d+)s")
TANK = re.compile(r'"create:banktank_air": (\d+)')


def run(args, scratch):
    with (ROOT / "fixtures/copper-diving-breath-java.csv").open() as file:
        rows = list(csv.DictReader(file))
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, "CopperDivingBreath", env=ENV, pack=args.pack))
        observers = (host,)
        if args.lan:
            name = "DivingObserver"
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            guest = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, render=True,
                scenario="copper-diving-breath", pack=args.pack, env=ENV))
            mp.until("diving observer joins", lambda: any(
                player["name"] == name and player["placed"] for player in host.call("lan", "status")["guests"]))
            host.command(f"/tp {name} 11.5 171 27.5")
            mp.until("the observer arrives beside the diving pools",
                     lambda: abs(guest.call("state")["player"]["position"][2] - 27.5) < 0.1)
            observers += (guest,)
        host.commands((
            "/fill 5 169 19 17 169 28 minecraft:stone",
            "/fill 5 170 19 17 175 28 minecraft:air",
            "/fill 8 170 21 10 172 23 minecraft:stone",
            "/fill 12 170 21 14 172 23 minecraft:stone",
            "/fill 9 170 22 9 172 22 minecraft:water",
            "/fill 13 170 22 13 172 22 minecraft:water",
        ))
        host.command("/tp @s 11.5 171 26.5")
        start = host.clock()
        phase = int(rows[0]["phase"])
        for tick in range(start + 1, start + (phase - start) % 20 + 1):
            host.step_to(tick)
        start = host.clock()
        host.commands((
            '/summon minecraft:pig 9.5 170 22.5 {Tags:["DivingGear"],NoAI:1b,NoGravity:1b,Air:280s,'
            'equipment:{head:{id:"create:copper_diving_helmet",count:1},'
            'chest:{id:"create:copper_backtank",count:1,components:{"create:banktank_air":2}}}}',
            '/summon minecraft:pig 13.5 170 22.5 {Tags:["DivingOrdinary"],NoAI:1b,NoGravity:1b,Air:280s}',
        ))
        now = 0
        differences = []
        for row in rows:
            tick = int(row["tick"])
            if tick != now:
                host.step_to(start + tick)
                now = tick
            tag = "DivingGear" if row["case"] == "gear" else "DivingOrdinary"
            state = host.command(f"/data get entity @e[type=minecraft:pig,tag={tag},limit=1]")
            air, tank = AIR.search(state), TANK.search(state)
            assert air, state
            actual = (int(air[1]), int(tank[1]) if tank else 0)
            expected = (int(row["air"]), int(row["tank"]))
            if actual != expected:
                differences.append((row["case"], tick, actual, expected))
        for observer in observers:
            try:
                mp.until("both submerged pigs are tracked by the observer",
                         lambda: len(observer.call("entities", 30, "minecraft:pig")["entities"]) >= 2)
            except RuntimeError as error:
                raise AssertionError((observer.call("state")["player"], observer.call("entities", 128))) from error
        assert not differences, (len(differences), differences[:12])
        print(f"Submerged air and remaining tank matched all {len(rows)} Java rows.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    with TemporaryDirectory(prefix="hc-copper-diving-breath-", dir="/private/tmp") as scratch:
        run(parser.parse_args(), Path(scratch))
