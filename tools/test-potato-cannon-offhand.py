#!/usr/bin/env python3
"""Compare offhand cannon use to pinned Java for hand and inventory ammo."""
import argparse
import csv
from importlib import import_module
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

carrot=import_module("test-potato-cannon-carrot")
multiplayer=import_module("test-multiplayer")
CASES=("main_potato","main_carrot","inventory_potato","inventory_carrot","main_priority")
ORIGIN=(8.5,101.0,3.5)
SHOT="@e[type=create:potato_projectile,limit=1]"


def run(args):
    with (ROOT/"fixtures/potato-cannon-offhand-java.csv").open() as f:
        rows={r["case"]:r for r in csv.DictReader(f)}
    cases=args.case or CASES
    with TemporaryDirectory(prefix="hc-offhand-cannon-") as tmp:
        with fixture_world(args,"OffhandCannon",render=False,pack=args.pack) as host:
            host.commands(("/fill 5 100 0 12 100 16 minecraft:stone", "/fill 5 101 0 12 106 16 minecraft:air"))
            with carrot.actor_for(host,args,Path(tmp)) as (actor,name):
                host.command(f"/gamemode survival {name}")
                for index,case in enumerate(cases):
                    if index:
                        actor.call("wait",20)
                        host.call("command",f"/kill {SHOT}")
                    host.call("command",f"/clear {name}")
                    host.command(f"/tp {name} 8.5 101 3.5 0 0")
                    host.command(f"/item replace entity {name} weapon.offhand with create:potato_cannon")
                    part,food=case.split("_")
                    if case == "main_priority": food = "carrot"
                    ammo=f"minecraft:{food}"
                    main_index = 5 if case == "main_priority" else 0
                    slot=f"hotbar.{main_index}" if part == "main" else "hotbar.1"
                    host.command(f"/item replace entity {name} {slot} with {ammo} 3")
                    if case == "main_priority":
                        host.command(f"/item replace entity {name} hotbar.1 with minecraft:potato 3")
                    multiplayer.until("offhand cannon and ammo",lambda:
                        actor.call("inventory")["offhand"].get("item") == "create:potato_cannon"
                        and actor.call("inventory")["counts"].get(ammo) == 3)
                    actor.call("select",str(main_index + 1))
                    actor.call("use-item")
                    if args.baseline:
                        actor.call("wait", 5)
                        inv=actor.call("inventory")
                        assert inv["counts"].get(ammo)==3 and inv["offhand"].get("damage",0)==0, (case,inv)
                        assert carrot.data(host,SHOT) is None
                        print(f"{case}: baseline did not fire",flush=True)
                        continue
                    row=rows[case]
                    multiplayer.until("offhand shot",lambda:actor.call("inventory")["counts"].get(ammo)==2)
                    inv=actor.call("inventory")
                    actual=(inv["hotbar"][main_index].get("count",0),inv["hotbar"][1].get("count",0),inv["offhand"].get("damage",0))
                    expected=tuple(int(row[k]) for k in ("main_count","inventory_count","damage"))
                    assert actual==expected,(case,actual,expected)
                    shot=carrot.data(host,SHOT)
                    assert shot and ammo in shot,(case,shot)
                    pos=tuple(a-b for a,b in zip(carrot.vector(shot,"Pos"),ORIGIN,strict=True))
                    actual=(*pos,*carrot.vector(shot,"Motion"))
                    expected=tuple(float(row[k]) for k in ("x","y","z","vx","vy","vz"))
                    carrot.near(actual,expected,case)
                    print(f"{case}: offhand launch matched Java",flush=True)
    if not args.baseline: print("Offhand cannon launches matched pinned Java.")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("ctl","client","resources"):
        p.add_argument(key,type=lambda path:Path(path).resolve(strict=True))
    p.add_argument("--pack",type=Path,default=ROOT/".local/create.hmod")
    p.add_argument("--lan",action="store_true")
    p.add_argument("--baseline",action="store_true")
    p.add_argument("--case",action="append",choices=CASES)
    os.environ["HORIZON_NO_AUDIO"]="1"
    run(p.parse_args())
