#!/usr/bin/env python3
"""Compare golden-apple cannon impact and effects to pinned Java."""
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
    # Isolate each shot in a fresh world.
    if args.case is None:
        import copy
        for case in ("golden", "enchanted"):
            trial=copy.copy(args)
            trial.case=[case]
            run(trial)
        return
    with (ROOT/"fixtures/potato-cannon-gapple-launch-java.csv").open() as f:
        launch={r["case"]:r for r in csv.DictReader(f)}
    with (ROOT/"fixtures/potato-cannon-gapple-target-java.csv").open() as f:
        target={(r["case"],int(r["tick"])):r for r in csv.DictReader(f)}
    cases=args.case or ("golden","enchanted")
    with TemporaryDirectory(prefix="hc-baked-") as tmp:
        with fixture_world(args,"GappleCannon",render=False,pack=args.pack) as host:
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
                    ammo="enchanted_golden_apple" if case=="enchanted" else "golden_apple"
                    host.command(f"/item replace entity {name} hotbar.1 with minecraft:{ammo} 3")
                    flag=0
                    fire=0
                    host.command(f'/summon minecraft:pig 8.0 102.0 8.5 {{NoAI:1b,NoGravity:1b,Invulnerable:{flag}b,Fire:{fire}s,Tags:["baked_target"]}}')
                    multiplayer.until("cannon and ammo",lambda:actor.call("inventory")["counts"].get(f"minecraft:{ammo}")==3
                                      and actor.call("inventory")["counts"].get("create:potato_cannon")==1)
                    actor.call("select","create:potato_cannon")
                    actor.call("use-item")
                    if args.baseline:
                        actor.call("wait",5)
                        assert actor.call("inventory")["counts"].get(f"minecraft:{ammo}")==3
                        assert carrot.data(host,SHOT) is None
                        print(f"{case}: baseline did not fire",flush=True)
                        continue
                    multiplayer.until("golden apple shot",lambda:actor.call("inventory")["counts"].get(f"minecraft:{ammo}")==2)
                    shot=carrot.data(host,SHOT);row=launch[case]
                    assert shot and f"minecraft:{ammo}" in shot,(case,shot)
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
                        absorption=float(re.search(r"\bAbsorptionAmount:\s*([0-9.]+)f",pig)[1])
                        effects=re.search(r'\bactive_effects:\s*(\[[^\]]*\])',pig)
                        entries=re.findall(r'\{[^{}]*\}',effects[1] if effects else '')
                        actual_effects={}
                        for entry in entries:
                            name=re.search(r'id:\s*"minecraft:([a-z_]+)"',entry)
                            duration=re.search(r'duration:\s*(\d+)',entry)
                            amplifier=re.search(r'amplifier:\s*(\d+)',entry)
                            if name and duration: actual_effects[name[1]]=(int(duration[1]),int(amplifier[1]) if amplifier else 0)
                        expected_effects={name:(int(row[name+'_duration']),int(row[name+'_amplifier'])) for name in ('regeneration','absorption','resistance','fire_resistance') if int(row[name+'_duration'])>=0}
                        assert actual_effects==expected_effects,(case,tick,actual_effects,expected_effects,pig)
                        actual=(health,absorption,int(carrot.data(host,SHOT) is not None))
                        expected=(float(row['health']),float(row['absorption']),int(row['shots']))
                        assert actual==expected,(case,tick,actual,expected,pig)
                        if tick==1:
                            actual=carrot.vector(pig,'Motion')
                            expected=tuple(float(row[k]) for k in ('vx','vy','vz'))
                            carrot.near(actual,expected,case+' impact')
                    print(f'{case}: golden apple impact and effects matched Java',flush=True)
    if not args.baseline:print("Golden-apple impacts matched pinned Java.")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("ctl","client","resources"):
        p.add_argument(key,type=lambda path:Path(path).resolve(strict=True))
    p.add_argument("--pack",type=Path,default=ROOT/".local/create.hmod")
    p.add_argument("--lan",action="store_true")
    p.add_argument("--baseline",action="store_true")
    p.add_argument("--case",action="append",choices=("golden","enchanted"))
    os.environ["HORIZON_NO_AUDIO"]="1"
    run(p.parse_args())
