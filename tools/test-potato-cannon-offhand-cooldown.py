#!/usr/bin/env python3
"""Compare offhand cannon cooldown boundaries against actual Java shots."""
import argparse
import csv
from importlib import import_module
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

placement=import_module("test-package-placement")
filters,editor=placement.package.filters,placement.editor
CASES=("main_potato","main_carrot","inventory_potato","inventory_carrot","main_priority")


def run(args):
    with (ROOT/"fixtures/potato-cannon-offhand-cooldown-java.csv").open() as f:
        rows={(r["case"],int(r["tick"])):r for r in csv.DictReader(f)}
    cases=args.case or CASES
    with TemporaryDirectory(prefix="hc-offhand-cooldown-") as tmp:
        with fixture_world(args,"OffhandCooldown",render=True,pack=args.pack) as host:
            host.commands(("/fill 5 100 0 12 100 50 minecraft:stone", "/fill 5 101 0 12 106 50 minecraft:air"))
            with filters.actor_for(host,args,Path(tmp) if args.lan else None) as (actor,name):
                host.command(f"/gamemode survival {name}")
                for index,case in enumerate(cases):
                    if index: actor.call("wait",20)
                    host.call("command",f"/clear {name}")
                    host.command(f"/tp {name} 8.5 101 3.5 0 0")
                    host.command(f"/item replace entity {name} weapon.offhand with create:potato_cannon")
                    part,food=case.split("_")
                    if case=="main_priority":food="carrot"
                    ammo=f"minecraft:{food}"
                    main_index=5 if case=="main_priority" else 0
                    slot=f"hotbar.{main_index}" if part=="main" else "hotbar.1"
                    host.command(f"/item replace entity {name} {slot} with {ammo} 3")
                    if case=="main_priority":host.command(f"/item replace entity {name} hotbar.1 with minecraft:potato 3")
                    actor.call("key",str(main_index+1),"tap")
                    editor.wait_for(actor,"offhand cannon and ammo",lambda:
                        actor.call("inventory")["offhand"].get("item")=="create:potato_cannon"
                        and actor.call("inventory")["counts"].get(ammo)==3)
                    actor.call("wait",10)
                    reload=15 if food=="potato" else 12
                    replies=actor.call("script",script="mouse right click\nwait 1\ninventory\n"*(reload+5))
                    inventories=[r for r in replies if "counts" in r]
                    first=next(i for i,inv in enumerate(inventories) if inv["counts"].get(ammo)==2)
                    assert len(inventories)>=first+reload+2,(case,first,len(inventories))
                    for tick in range(reload+2):
                        inv=inventories[first+tick]
                        actual=(inv["hotbar"][main_index].get("count",0),inv["hotbar"][1].get("count",0),inv["offhand"].get("damage",0))
                        row=rows[(case,tick)]
                        expected=tuple(int(row[k]) for k in ("main_count","inventory_count","damage"))
                        assert actual==expected,(case,tick,actual,expected)
                    print(f"{case}: offhand cooldown {reload} matched Java",flush=True)
    print("Offhand cannon cooldown boundaries matched Java.")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("ctl","client","resources"):
        p.add_argument(key,type=lambda path:Path(path).resolve(strict=True))
    p.add_argument("--pack",type=Path,default=ROOT/".local/create.hmod")
    p.add_argument("--lan",action="store_true")
    p.add_argument("--case",action="append",choices=CASES)
    os.environ["HORIZON_NO_AUDIO"]="1"
    run(p.parse_args())
