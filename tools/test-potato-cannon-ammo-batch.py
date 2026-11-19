#!/usr/bin/env python3
"""Replay a pinned six-ammunition Java launch and living-impact batch."""
import argparse
import csv
from importlib import import_module
import math
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

carrot = import_module("test-potato-cannon-carrot")
multiplayer = import_module("test-multiplayer")
CASES = ("potato", "carrot", "apple", "beetroot", "melon_slice", "golden_carrot")
ORIGIN = (8.5, 101.0, 3.5)
TARGET = "@e[tag=ammo_target,limit=1]"
SHOT = "@e[type=create:potato_projectile,limit=1]"


def run(args):
    with (ROOT / "fixtures/potato-cannon-batch-launch-java.csv").open() as f:
        launch = {r["case"]: r for r in csv.DictReader(f)}
    with (ROOT / "fixtures/potato-cannon-batch-target-java.csv").open() as f:
        targets = {(r["case"], int(r["tick"])): r for r in csv.DictReader(f)}
    cases = args.case or CASES
    with TemporaryDirectory(prefix="hc-ammo-batch-") as tmp:
        with fixture_world(args, "AmmoBatch", render=False, pack=args.pack) as host:
            host.commands(("/fill 5 100 0 12 100 16 minecraft:stone", "/fill 5 101 0 12 106 16 minecraft:air"))
            with carrot.actor_for(host, args, Path(tmp)) as (actor, name):
                host.command(f"/gamemode survival {name}")
                for index, case in enumerate(cases):
                    if index:
                        actor.call("wait", 20)
                        host.call("command", f"/kill {SHOT}")
                        host.call("command", f"/kill {TARGET}")
                    host.call("command", f"/clear {name}")
                    host.command(f"/tp {name} 8.5 101 3.5 0 0")
                    host.command(f"/item replace entity {name} hotbar.0 with create:potato_cannon")
                    host.command(f"/item replace entity {name} hotbar.1 with minecraft:{case} 3")
                    host.command('/summon minecraft:pig 8.0 102.0 8.5 {NoAI:1b,NoGravity:1b,Tags:["ammo_target"]}')
                    host.command(f"/attribute {TARGET} minecraft:max_health base set 40")
                    host.command(f"/data merge entity {TARGET} {{Health:40.0f}}")
                    actor.call("select", "create:potato_cannon")
                    ammo = f"minecraft:{case}"
                    multiplayer.until("ammo setup", lambda: actor.call("inventory")["counts"].get(ammo) == 3)
                    actor.call("use-item")
                    if args.baseline:
                        actor.call("wait", 5)
                        assert actor.call("inventory")["counts"].get(ammo) == 3
                        assert carrot.data(host, SHOT) is None
                        print(f"{case}: baseline did not fire", flush=True)
                        continue
                    multiplayer.until("shot", lambda: actor.call("inventory")["counts"].get(ammo) == 2)
                    shot = carrot.data(host, SHOT)
                    assert shot and ammo in shot, (case, shot)
                    held = actor.call("inventory")["held"]
                    assert held.get("damage",0) == int(launch[case]["damage"]), (case, held)
                    pos = tuple(a-b for a,b in zip(carrot.vector(shot,"Pos"), ORIGIN, strict=True))
                    actual = (*pos, *carrot.vector(shot,"Motion"))
                    expected = tuple(float(launch[case][k]) for k in ("x","y","z","vx","vy","vz"))
                    assert all(math.isclose(a,b,abs_tol=1e-6) for a,b in zip(actual,expected,strict=True)), (case,actual,expected)
                    impact_tick = 2 if case == "potato" else 1
                    for _ in range(impact_tick): host.step_to(host.clock()+1)
                    pig = carrot.data(host,TARGET); row = targets[(case,impact_tick)]
                    health = float(re.search(r"\bHealth:\s*([0-9.]+)f",pig)[1])
                    actual = (health, *(a-b for a,b in zip(carrot.vector(pig,"Pos"),ORIGIN,strict=True)), *carrot.vector(pig,"Motion"))
                    expected = tuple(float(row[k]) for k in ("health","x","y","z","vx","vy","vz"))
                    assert all(math.isclose(a,b,abs_tol=1e-6) for a,b in zip(actual,expected,strict=True)), (case,actual,expected)
                    assert carrot.data(host,SHOT) is None
                    print(f"{case}: launch and tick-{impact_tick} hit matched Java", flush=True)
    if not args.baseline: print("Six ammunition launch and hit cases matched Java.")


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("ctl","client","resources"):
        p.add_argument(key,type=lambda path:Path(path).resolve(strict=True))
    p.add_argument("--pack",type=Path,default=ROOT/".local/create.hmod")
    p.add_argument("--lan",action="store_true")
    p.add_argument("--baseline",action="store_true")
    p.add_argument("--case",action="append",choices=CASES)
    os.environ["HORIZON_NO_AUDIO"]="1"
    run(p.parse_args())
