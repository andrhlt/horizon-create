#!/usr/bin/env python3
"""Compare glistering-melon launch and impact status to pinned Java."""
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
    with (ROOT/"fixtures/potato-cannon-glister-launch-java.csv").open() as f:
        launch={r["case"]:r for r in csv.DictReader(f)}
    with (ROOT/"fixtures/potato-cannon-glister-target-java.csv").open() as f:
        target={(r["case"],int(r["tick"])):r for r in csv.DictReader(f)}
    cases=args.case or ("unlit","invulnerable","burning_invulnerable")
    with TemporaryDirectory(prefix="hc-baked-") as tmp:
        with fixture_world(args,"GlisterCannon",render=False,pack=args.pack) as host:
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
                    host.command(f"/item replace entity {name} hotbar.1 with minecraft:glistering_melon_slice 3")
                    flag=1 if case in ("invulnerable", "burning_invulnerable") else 0
                    fire=120 if case=="burning_invulnerable" else 0
                    host.command(f'/summon minecraft:pig 8.0 102.0 8.5 {{NoAI:1b,NoGravity:1b,Invulnerable:{flag}b,Fire:{fire}s,Tags:["baked_target"]}}')
                    multiplayer.until("cannon and ammo",lambda:actor.call("inventory")["counts"].get("minecraft:glistering_melon_slice")==3
                                      and actor.call("inventory")["counts"].get("create:potato_cannon")==1)
                    actor.call("select","create:potato_cannon")
                    actor.call("use-item")
                    if args.baseline:
                        actor.call("wait",5)
                        assert actor.call("inventory")["counts"].get("minecraft:glistering_melon_slice")==3
                        assert carrot.data(host,SHOT) is None
                        print(f"{case}: baseline did not fire",flush=True)
                        continue
                    multiplayer.until("poison shot",lambda:actor.call("inventory")["counts"].get("minecraft:glistering_melon_slice")==2)
                    shot=carrot.data(host,SHOT);row=launch[case]
                    assert shot and "minecraft:glistering_melon_slice" in shot,(case,shot)
                    held=actor.call("inventory")["held"]
                    assert held.get("damage",0)==int(row["damage"]),(case,held)
                    pos=tuple(a-b for a,b in zip(carrot.vector(shot,"Pos"),ORIGIN,strict=True))
                    actual=(*pos,*carrot.vector(shot,"Motion"))
                    expected=tuple(float(row[k]) for k in ("x","y","z","vx","vy","vz"))
                    carrot.near(actual,expected,case+" launch")
                    for tick in range(5):
                        if tick: host.step_to(host.clock()+1)
                        pig=carrot.data(host,TARGET);row=target[(case,tick)]
                        health=float(re.search(r"\bHealth:\s*([0-9.]+)f",pig)[1])
                        effects=re.search(r'\bactive_effects:\s*(\[[^\]]*\])',pig)
                        raw=effects[1] if effects else ''
                        if raw: assert 'minecraft:glowing' in raw,(case,tick,raw)
                        duration=re.search(r'\bduration:\s*(\d+)',raw)
                        amplifier=re.search(r'\bamplifier:\s*(\d+)',raw)
                        status=(int(duration[1]) if duration else -1,int(amplifier[1]) if amplifier else (0 if duration else -1))
                        expected=(float(row['health']),int(row['duration']),int(row['amplifier']),int(row['shots']))
                        actual=(health,*status,int(carrot.data(host,SHOT) is not None))
                        assert actual==expected,(case,tick,actual,expected,pig)
                        if tick==1:
                            actual=tuple(a-b for a,b in zip(carrot.vector(pig,'Pos'),ORIGIN,strict=True))+carrot.vector(pig,'Motion')
                            expected=tuple(float(row[k]) for k in ('x','y','z','vx','vy','vz'))
                            carrot.near(actual,expected,case+' impact')
                    print(f'{case}: glowing impact and countdown matched Java',flush=True)
    if not args.baseline:print("Glistering-melon impact matched pinned Java.")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("ctl","client","resources"):
        p.add_argument(key,type=lambda path:Path(path).resolve(strict=True))
    p.add_argument("--pack",type=Path,default=ROOT/".local/create.hmod")
    p.add_argument("--lan",action="store_true")
    p.add_argument("--baseline",action="store_true")
    p.add_argument("--case",action="append",choices=("unlit","invulnerable","burning_invulnerable"))
    os.environ["HORIZON_NO_AUDIO"]="1"
    run(p.parse_args())
