#!/usr/bin/env python3
"""Compare pie launch and impact status to pinned Java."""
import argparse
import csv
from importlib import import_module
import math
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

carrot=import_module("test-potato-cannon-carrot")
multiplayer=import_module("test-multiplayer")
ORIGIN=(8.5,101.0,3.5)
TARGET="@e[tag=baked_target,limit=1]"
SHOT="@e[type=create:potato_projectile,limit=1]"


def run(args):
    with (ROOT/"fixtures/potato-cannon-pie-launch-java.csv").open() as f:
        launch={r["case"]:r for r in csv.DictReader(f)}
    with (ROOT/"fixtures/potato-cannon-pie-target-java.csv").open() as f:
        target={(r["case"],int(r["tick"])):r for r in csv.DictReader(f)}
    cases=args.case or ("unlit","invulnerable","burning_invulnerable")
    with TemporaryDirectory(prefix="hc-baked-") as tmp:
        with fixture_world(args,"PieHit",render=False,pack=args.pack) as host:
            host.commands(("/fill 5 100 0 12 100 16 minecraft:stone", "/fill 5 101 0 12 106 16 minecraft:air"))
            with carrot.actor_for(host,args,Path(tmp)) as (actor,name):
                host.command(f"/gamemode survival {name}")
                for index,case in enumerate(cases):
                    if index:
                        actor.call("wait",20)
                        host.call("command",f"/kill {SHOT}")
                        host.call("command",f"/kill {TARGET}")
                    host.call("command",f"/clear {name}")
                    host.command(f"/tp {name} 8.5 101 3.5 0 0")
                    host.command(f"/item replace entity {name} hotbar.0 with create:potato_cannon")
                    host.command(f"/item replace entity {name} hotbar.1 with minecraft:pumpkin_pie 3")
                    flag=1 if case in ("invulnerable", "burning_invulnerable") else 0
                    fire=120 if case=="burning_invulnerable" else 0
                    host.command(f'/summon minecraft:pig 8.0 102.0 8.5 {{NoAI:1b,NoGravity:1b,Invulnerable:{flag}b,Fire:{fire}s,Tags:["baked_target"]}}')
                    multiplayer.until("cannon and ammo",lambda:actor.call("inventory")["counts"].get("minecraft:pumpkin_pie")==3
                                      and actor.call("inventory")["counts"].get("create:potato_cannon")==1)
                    actor.call("select","create:potato_cannon")
                    actor.call("use-item")
                    actor.call("wait",5)
                    assert actor.call("inventory")["counts"].get("minecraft:pumpkin_pie")==3
                    assert carrot.data(host,SHOT) is None
                    print(f"{case}: baseline did not fire",flush=True)



if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("ctl","client","resources"):
        p.add_argument(key,type=lambda path:Path(path).resolve(strict=True))
    p.add_argument("--pack",type=Path,default=ROOT/".local/create.hmod")
    p.add_argument("--lan",action="store_true")

    p.add_argument("--case",action="append",choices=("unlit","invulnerable","burning_invulnerable"))
    os.environ["HORIZON_NO_AUDIO"]="1"
    run(p.parse_args())
