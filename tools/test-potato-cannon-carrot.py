#!/usr/bin/env python3
"""Compare carrot launch and first pig impact to pinned Java, fully headlessly."""
import argparse
from contextlib import contextmanager
import csv
from importlib import import_module
import math
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
ORIGIN = (8.5, 101.0, 3.5)
TARGET = "@e[tag=carrot_target,limit=1]"
PROJECTILE = "@e[type=create:potato_projectile,limit=1]"


@contextmanager
def actor_for(host, args, scratch):
    if not args.lan:
        yield host, "@s"
        return
    address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
    with multiplayer.joined_client(args, scratch, address, "CarrotGuest", render=False,
                                   scenario="carrot", pack=args.pack) as guest:
        multiplayer.until("guest to join", lambda: any(p["name"] == "CarrotGuest" and p["placed"]
                          for p in host.call("lan", "status")["guests"]))
        yield guest, "CarrotGuest"


def data(host, selector):
    reply = host.command(f"/data get entity {selector}")
    return reply.split("entity data: ", 1)[1] if "entity data: " in reply else None


def vector(raw, key):
    text = re.search(rf"\b{key}:\s*\[([^\]]+)\]", raw)[1]
    return tuple(float(value.strip().removesuffix("d")) for value in text.split(","))


def near(actual, expected, name):
    assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(actual, expected, strict=True)), (name, actual, expected)


def run(args):
    if args.potato:
        with (ROOT / "fixtures/potato-cannon-launch-java.csv").open() as f:
            launch = next(row for row in csv.DictReader(f) if row["case"] == "potato")
        with (ROOT / "fixtures/potato-cannon-impact-java.csv").open() as f:
            target = {int(row["tick"]): row for row in csv.DictReader(f)}
    else:
        with (ROOT / "fixtures/potato-cannon-carrot-launch-java.csv").open() as f:
            launch = next(csv.DictReader(f))
        with (ROOT / "fixtures/potato-cannon-carrot-target-java.csv").open() as f:
            target = {int(row["tick"]): row for row in csv.DictReader(f)}
    ammo = "minecraft:potato" if args.potato else "minecraft:carrot"
    impact_tick = 2 if args.potato else 1
    with TemporaryDirectory(prefix="hc-carrot-") as tmp:
        with fixture_world(args, "CarrotCannon", render=False, pack=args.pack) as host:
            host.commands(("/fill 5 100 0 12 100 16 minecraft:stone", "/fill 5 101 0 12 106 16 minecraft:air"))
            with actor_for(host, args, Path(tmp)) as (actor, name):
                host.commands((f"/gamemode survival {name}", f"/clear {name}",
                    f"/tp {name} 8.5 101 3.5 0 0",
                    '/summon minecraft:pig 8.0 102.0 8.5 {NoAI:1b,NoGravity:1b,Tags:["carrot_target"]}'))
                if args.backtank:
                    host.commands(("/setblock 9 101 2 create:copper_backtank", "/data merge block 9 101 2 {Air:100}"))
                    actor.call("interact", 9, 101, 2, "up")
                    multiplayer.until("equipped tank", lambda: '"create:banktank_air": 100' in (data(host, name) or ""))
                    host.command(f"/tp {name} 8.5 101 3.5 0 0")
                host.commands((f"/item replace entity {name} hotbar.0 with create:potato_cannon",
                               f"/item replace entity {name} hotbar.1 with {ammo} 3"))
                actor.call("select", "create:potato_cannon")
                multiplayer.until("ammo", lambda: actor.call("inventory")["counts"].get(ammo) == 3)
                actor.call("use-item")
                multiplayer.until("shot", lambda: actor.call("inventory")["counts"].get(ammo) == 2)
                shot = data(host, PROJECTILE)
                assert shot is not None and ammo in shot, shot
                held = actor.call("inventory")["held"]
                assert held.get("damage", 0) == (0 if args.backtank else int(launch["damage"])), held
                if args.backtank:
                    assert '"create:banktank_air": 96' in (data(host, name) or "")
                pos = tuple(a-b for a,b in zip(vector(shot, "Pos"), ORIGIN, strict=True))
                near((*pos, *vector(shot, "Motion")), tuple(float(launch[k]) for k in ("x","y","z","vx","vy","vz")), "launch")
                for _ in range(impact_tick):
                    host.step_to(host.clock() + 1)
                pig = data(host, TARGET)
                row = target[impact_tick]
                actual = (float(re.search(r"\bHealth:\s*([0-9.]+)f", pig)[1]),
                          *(a-b for a,b in zip(vector(pig, "Pos"), ORIGIN, strict=True)), *vector(pig, "Motion"))
                expected = tuple(float(row[k]) for k in ("health","x","y","z","vx","vy","vz"))
                near(actual, expected, "pig hit")
                assert data(host, PROJECTILE) is None
    print(f"{ammo} launch and first pig hit matched pinned Java; backtank={args.backtank}.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        p.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    p.add_argument("--lan", action="store_true")
    p.add_argument("--potato", action="store_true")
    p.add_argument("--backtank", action="store_true")
    os.environ["HORIZON_NO_AUDIO"] = "1"
    run(p.parse_args())
