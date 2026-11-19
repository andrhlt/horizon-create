#!/usr/bin/env python3
"""Compare real tick-paced pumpkin-block cannon refires with pinned Java."""
import argparse,csv,os
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT,fixture_world
placement=import_module('test-package-placement')
filters,editor=placement.package.filters,placement.editor
CASES=('pumpkin',)

def run(args):
    with (ROOT/'fixtures/potato-cannon-pumpkin-refire-java.csv').open() as f:
        rows={(r['case'],int(r['tick'])):r for r in csv.DictReader(f)}
    for case in args.case or CASES:
        ammo='minecraft:pumpkin'
        with TemporaryDirectory(prefix='hc-gapple-refire-') as tmp:
            with fixture_world(args,'GappleRefire',render=True,pack=args.pack) as host:
                host.commands(('/fill 5 100 0 12 100 50 minecraft:stone','/fill 5 101 0 12 106 50 minecraft:air'))
                with filters.actor_for(host,args,Path(tmp) if args.lan else None) as (actor,name):
                    host.command(f'/gamemode survival {name}')
                    host.command(f'/tp {name} 8.5 101 3.5 0 0')
                    host.command(f'/item replace entity {name} hotbar.0 with create:potato_cannon')
                    host.command(f'/item replace entity {name} hotbar.1 with {ammo} 3')
                    actor.call('key','1','tap')
                    editor.wait_for(actor,'cannon and ammo',lambda: (actor.call('inventory')['held'] or {}).get('item')=='create:potato_cannon' and actor.call('inventory')['counts'].get(ammo)==3)
                    actor.call('wait',10)
                    replies=actor.call('script',script='mouse right click\nwait 1\ninventory\n'*20)
                    inventories=[r for r in replies if 'counts' in r]
                    first=next((i for i,inv in enumerate(inventories) if inv['counts'].get(ammo)==2),None)
                    assert first is not None and len(inventories)>=first+17,(case,first,len(inventories))
                    for tick in range(17):
                        inv=inventories[first+tick];row=rows[(case,tick)]
                        actual=(inv['hotbar'][0].get('count',0),inv['hotbar'][1].get('count',0),(inv['held'] or {}).get('damage',0))
                        expected=tuple(int(row[k]) for k in ('main_count','inventory_count','damage'))
                        assert actual==expected,(case,tick,actual,expected)
                    print(f'{case}: first and second shots match Java through tick 16',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('ctl','client','resources'):p.add_argument(key,type=lambda path:Path(path).resolve(strict=True))
    p.add_argument('--pack',type=Path,default=ROOT/'.local/create.hmod')
    p.add_argument('--lan',action='store_true')
    p.add_argument('--case',action='append',choices=CASES)
    os.environ['HORIZON_NO_AUDIO']='1'
    run(p.parse_args())
