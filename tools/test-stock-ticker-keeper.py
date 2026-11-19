#!/usr/bin/env python3
"""Replay the Java Stock Ticker keeper checks through block interaction."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import json

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
placement = import_module("test-clipboard-placement")
TICKER = "create:stock_ticker"
KEY = "create.stock_ticker.keeper_missing"
SEATS = {
    "empty_seat": (1, 0, 0),
    "occupied_seat": (1, 0, 0),
    "occupied_one_below": (1, -1, 0),
    "occupied_two_below": (1, -2, 0),
    "occupied_diagonal": (1, 0, 1),
}
BURNERS = {
    "empty_burner": (0, "create:empty_blaze_burner"),
    "adjacent_burner": (0, "create:blaze_burner[blaze=smouldering]"),
    "burner_below": (-1, "create:blaze_burner[blaze=smouldering]"),
}


def setup(host, cases):
    commands = [
        "/gamerule spawn_mobs false",
        "/fill 5 168 5 29 168 25 minecraft:stone",
        "/tp @s 15.5 171 15.5",
    ]
    occupied = 0
    for case, (x, y, z) in cases.items():
        commands += [
            f"/setblock {x} {y-1} {z+3} minecraft:stone",
            f"/setblock {x} {y} {z} {TICKER}",
        ]
        if case in SEATS:
            dx, dy, dz = SEATS[case]
            sx, sy, sz = x + dx, y + dy, z + dz
            commands.append(f"/setblock {sx} {sy} {sz} create:red_seat")
            if case != "empty_seat":
                occupied += 1
                commands.append(f"/summon minecraft:pig {sx+.5} {sy+3.25} {sz+.5}")
        if case in BURNERS:
            dy, block = BURNERS[case]
            commands.append(f"/setblock {x+1} {y+dy} {z} {block}")
    host.commands(commands)
    tick = host.clock()
    for offset in range(1, 19):
        host.step_to(tick + offset)
    pigs = [mob for mob in host.call("mobs", 32)["near"] if mob["kind"] == "minecraft:pig"]
    assert sum(mob["passenger"] and mob["mount"] is not None for mob in pigs) == occupied, pigs


def replay(host, actor, player, rows, cases, missing):
    host.command(f"/item replace entity {player} hotbar.0 with minecraft:stick")
    mp.until("the actor to receive the Stick", lambda: mp.count(actor, "minecraft:stick") == 1)
    actor.call("select", "minecraft:stick")
    start = host.clock() - 1
    for row in rows:
        case = row["case"]
        host.step_to(start + int(row["tick"]))
        x, y, z = cases[case]
        feet = [x + .5, y, z + 3.5]
        host.command(f"/tp {player} {placement.coords(feet)}")
        mp.until("the actor to reach the Ticker", lambda: actor.call("state")["player"]["position"] == feet)
        actor.call("look-at", x + .5, y + .65, z + .5)
        mp.until("the actor to aim at the Ticker", lambda: placement.ray_hit(actor, (x, y, z), "south"))
        marker = f"case {case}"
        host.command(f'/title {player} actionbar {{"text":"{marker}"}}')
        get_actionbar = lambda: actor.call("messages").get("actionbar")
        mp.until("the action bar marker to arrive", lambda: get_actionbar() == marker)
        actor.call("wait", 3)
        actor.call("mouse", "right", "click")
        if row["keeper"] == "false":
            mp.until(f"the missing keeper message for {case}", lambda: get_actionbar() == missing)
        else:
            actor.call("wait", 12)
            assert get_actionbar() == marker, (case, get_actionbar())
        print(f'{row["tick"]} {case}: keeper feedback matches Java.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/stock-ticker-keeper-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    with ZipFile(args.pack) as pack:
        missing = json.loads(pack.read("assets/create/lang/en_us.json"))[KEY]
    cases = {row["case"]: (7 + index % 3 * 8, 171, 7 + index // 3 * 7)
             for index, row in enumerate(rows)}
    env = {"HORIZON_NO_AUDIO": "1"}
    mode = "LAN" if args.lan else "Solo"
    with ExitStack() as resources:
        host = resources.enter_context(fixture_world(args, f"StockTickerKeeper{mode}", pack=args.pack, env=env))
        setup(host, cases)
        actor, player = host, "@s"
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(resources.enter_context(TemporaryDirectory(prefix="hc-stock-ticker-")))
            player = "TickerGuest"
            actor = resources.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True, scenario="stock-ticker-keeper",
                pack=args.pack, env=env,
            ))
            mp.until("the Ticker guest to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]
            ))
        replay(host, actor, player, rows, cases, missing)
    print(f"{mode} matched {len(rows)} Java Stock Ticker keeper checks.")


if __name__ == "__main__":
    main()
