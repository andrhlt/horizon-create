#!/usr/bin/env python3
"""Compare left-dominant main/offhand launches with pinned Java."""
import argparse,csv,os
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT,fixture_world

carrot=import_module('test-potato-cannon-carrot')
multiplayer=import_module('test-multiplayer')
ORIGIN=(8.5,101.0,3.5)
SHOT='@e[type=create:potato_projectile,limit=1]'

@contextmanager
def left_actor(host,args,scratch):
    if not args.lan:
        game=Path(host._launch[host._launch.index('--game-dir')+1])
        host.stop()
        (game/'options.txt').write_text('mainHand:left\n')
        host.open()
        yield host,'@s'
    else:
        address=f"127.0.0.1:{host.call('lan','open','0','commands','force')['port']}"
        home=scratch/'LeftCannonGuest'
        home.mkdir(parents=True)
        (home/'options.txt').write_text('mainHand:left\n')
        with multiplayer.joined_client(args,scratch,address,'LeftCannonGuest',scenario='left-cannon',pack=args.pack) as guest:
            multiplayer.until('guest to join',lambda:any(p['name']=='LeftCannonGuest' and p['placed'] for p in host.call('lan','status')['guests']))
            yield guest,'LeftCannonGuest'

def run(args):
    with (ROOT/'fixtures/potato-cannon-left-java.csv').open() as f: rows={r['case']:r for r in csv.DictReader(f)}
    failures=[]
    with TemporaryDirectory(prefix='hc-left-cannon-') as tmp:
        with fixture_world(args,'LeftCannon',render=False,pack=args.pack) as host:
            with left_actor(host,args,Path(tmp)) as (actor,name):
                host.commands(('/fill 5 100 0 12 100 16 minecraft:stone','/fill 5 101 0 12 106 16 minecraft:air'))
                host.command(f'/gamemode survival {name}')
                for index,case in enumerate(('main_cannon','off_cannon')):
                    if index:
                        actor.call('wait',20)
                        host.call('command',f'/kill {SHOT}')
                    host.call('command',f'/clear {name}')
                    host.command(f'/tp {name} 8.5 101 3.5 0 0')
                    if case=='main_cannon':
                        host.command(f'/item replace entity {name} hotbar.0 with create:potato_cannon')
                        host.command(f'/item replace entity {name} hotbar.1 with minecraft:potato 3')
                    else:
                        host.command(f'/item replace entity {name} weapon.offhand with create:potato_cannon')
                        host.command(f'/item replace entity {name} hotbar.0 with minecraft:potato 3')
                    actor.call('select','1')
                    multiplayer.until('cannon and potato',lambda:actor.call('inventory')['counts'].get('minecraft:potato')==3 and (actor.call('inventory')['held'] if case=='main_cannon' else actor.call('inventory')['offhand']).get('item')=='create:potato_cannon')
                    actor.call('use-item')
                    multiplayer.until('shot',lambda:actor.call('inventory')['counts'].get('minecraft:potato')==2)
                    inv=actor.call('inventory'); row=rows[case]
                    cannon=inv['held'] if case=='main_cannon' else inv['offhand']
                    actual=(inv['hotbar'][0].get('count',0),inv['hotbar'][1].get('count',0),cannon.get('damage',0))
                    expected=tuple(int(row[k]) for k in ('main_count','inventory_count','damage'))
                    assert actual==expected,(case,actual,expected)
                    shot=carrot.data(host,SHOT)
                    assert shot and 'minecraft:potato' in shot,(case,shot)
                    pos=tuple(a-b for a,b in zip(carrot.vector(shot,'Pos'),ORIGIN,strict=True))
                    actual=(*pos,*carrot.vector(shot,'Motion'))
                    expected=tuple(float(row[k]) for k in ('x','y','z','vx','vy','vz'))
                    print(f'{case}: actual {actual}; Java {expected}',flush=True)
                    try: carrot.near(actual,expected,case)
                    except AssertionError: failures.append(case)
                    else: print(f'{case}: left-handed launch and wear matched Java',flush=True)
    assert not failures, failures

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('ctl','client','resources'): p.add_argument(key,type=lambda path:Path(path).resolve(strict=True))
    p.add_argument('--pack',type=Path,default=ROOT/'.local/create.hmod')
    p.add_argument('--lan',action='store_true')
    os.environ['HORIZON_NO_AUDIO']='1'
    run(p.parse_args())
