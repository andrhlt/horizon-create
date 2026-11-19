#!/usr/bin/env python3
"""Compare horizontal pumpkin shot, falling block and landing with pinned Java."""
import argparse,csv,math,os,re
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT,fixture_world
carrot=import_module('test-potato-cannon-carrot')
multiplayer=import_module('test-multiplayer')
ORIGIN=(8,101,3)
SHOT='@e[type=create:potato_projectile,limit=1]'
FALL='@e[type=minecraft:falling_block,limit=1]'

def run(args):
 with (ROOT/'fixtures/potato-cannon-pumpkin-side-launch-java.csv').open() as f: launch=next(csv.DictReader(f))
 with (ROOT/'fixtures/potato-cannon-pumpkin-side-java.csv').open() as f: rows=list(csv.DictReader(f))[:3]
 with TemporaryDirectory(prefix='hc-pumpkin-side-') as tmp:
  with fixture_world(args,'PumpkinSide',render=False,pack=args.pack) as host:
   host.commands(('/fill 6 99 -2 11 105 7 minecraft:air','/setblock 8 101 3 minecraft:stone','/setblock 8 100 2 minecraft:stone','/setblock 9 99 0 minecraft:stone'))
   with carrot.actor_for(host,args,Path(tmp)) as (actor,name):
    host.commands((f'/gamemode survival {name}',f'/tp {name} 9.25 100 0.0 0 0',f'/item replace entity {name} hotbar.0 with create:potato_cannon',f'/item replace entity {name} hotbar.1 with minecraft:pumpkin 3'))
    multiplayer.until('cannon and pumpkin',lambda:actor.call('inventory')['counts'].get('minecraft:pumpkin')==3)
    actor.call('select','create:potato_cannon');actor.call('use-item')
    multiplayer.until('pumpkin shot',lambda:actor.call('inventory')['counts'].get('minecraft:pumpkin')==2)
    assert (actor.call('inventory')['held'] or {}).get('damage',0)==int(launch['damage'])
    shot=carrot.data(host,SHOT);assert shot
    pos=tuple(a-b for a,b in zip(carrot.vector(shot,'Pos'),ORIGIN,strict=True));actual=(*pos,*carrot.vector(shot,'Motion'))
    expected=tuple(float(launch[k]) for k in ('x','y','z','vx','vy','vz'));carrot.near(actual,expected,'launch')
    start=host.clock()
    for row in rows:
     host.step_to(start+int(row['tick']))
     expected_block='minecraft:'+row['block']
     multiplayer.until('the completed landing update',lambda:host.call('block',8,101,2)['block']==expected_block)
     block=host.call('block',8,101,2)
     assert block['block']==expected_block,(row,block)
     assert (carrot.data(host,SHOT) is not None)==(int(row['projectiles'])>0),row
     falling=carrot.data(host,FALL)
     assert (falling is not None)==(int(row['falling'])>0),(row,falling)
     if falling:
      pos=tuple(a-b for a,b in zip(carrot.vector(falling,'Pos'),ORIGIN,strict=True))
      actual=(*pos,*carrot.vector(falling,'Motion'))
      expected=tuple(float(row[k]) for k in ('x','y','z','vx','vy','vz'))
      carrot.near(actual,expected,'falling')
      age=re.search(r'\bTime:\s*(-?\d+)',falling)
      assert age and int(age[1])==int(row['age']),(row,falling)
 print('Pumpkin horizontal projectile, falling block and landing matched Java.',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for key in ('ctl','client','resources'):p.add_argument(key,type=lambda path:Path(path).resolve(strict=True))
 p.add_argument('--pack',type=Path,default=ROOT/'.local/create.hmod')
 p.add_argument('--lan',action='store_true')
 os.environ['HORIZON_NO_AUDIO']='1'
 run(p.parse_args())
