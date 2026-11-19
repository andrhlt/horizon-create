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
CASES=("main_cannon","off_cannon")


def run(args):
    with (ROOT/"fixtures/potato-cannon-baked-cooldown-java.csv").open() as f:
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
                    ammo="minecraft:baked_potato"
                    main_index=0
                    if case=="main_cannon":
                        host.command(f"/item replace entity {name} hotbar.0 with create:potato_cannon")
                        host.command(f"/item replace entity {name} hotbar.1 with {ammo} 3")
                    else:
                        host.command(f"/item replace entity {name} weapon.offhand with create:potato_cannon")
                        host.command(f"/item replace entity {name} hotbar.0 with {ammo} 3")
                    actor.call("key","1","tap")
                    editor.wait_for(actor,"cannon and ammo",lambda: actor.call("inventory")["counts"].get(ammo)==3 and (actor.call("inventory")["held"] if case=="main_cannon" else actor.call("inventory")["offhand"]).get("item")=="create:potato_cannon")
                    actor.call("wait",10)
                    reload=15
                    replies=actor.call("script",script="mouse right click\nwait 1\ninventory\n"*(reload+5))
                    inventories=[r for r in replies if "counts" in r]
                    first=next((i for i,inv in enumerate(inventories) if inv["counts"].get(ammo)==2),None)
                    assert first is not None,(case,"no first shot")
                    assert len(inventories)>=first+reload+2,(case,first,len(inventories))
                    for tick in range(reload+2):
                        inv=inventories[first+tick]
                        actual=(inv["hotbar"][main_index].get("count",0),inv["hotbar"][1].get("count",0),(inv["hotbar"][0] if case=="main_cannon" else inv["offhand"]).get("damage",0))
                        row=rows[(case,tick)]
                        expected=tuple(int(row[k]) for k in ("main_count","inventory_count","damage"))
                        assert actual==expected,(case,tick,actual,expected)
                    print(f"{case}: baked cooldown {reload} matched Java",flush=True)
    print("Baked cannon cooldown boundaries matched Java.")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("ctl","client","resources"):
        p.add_argument(key,type=lambda path:Path(path).resolve(strict=True))
    p.add_argument("--pack",type=Path,default=ROOT/".local/create.hmod")
    p.add_argument("--lan",action="store_true")
    p.add_argument("--case",action="append",choices=CASES)
    os.environ["HORIZON_NO_AUDIO"]="1"
    run(p.parse_args())
