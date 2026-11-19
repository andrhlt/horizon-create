#!/usr/bin/env python3
"""Compare pumpkin-pie launch, pig impact and attachment slide to Java."""
import argparse,csv,math,os
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT,fixture_world
carrot=import_module('test-potato-cannon-carrot')
multiplayer=import_module('test-multiplayer')
SHOT='@e[type=create:potato_projectile,limit=1]'
TARGET='@e[tag=pie_target,limit=1]'
ORIGIN=(8.5,101.0,3.5)

def run(args):
 with (ROOT/'fixtures/potato-cannon-pie-launch-java.csv').open() as f: launch={r['case']:r for r in csv.DictReader(f)}
 prefix='potato-cannon-pie-moving-'
 with (ROOT/f'fixtures/{prefix}target-java.csv').open() as f: target={(r['case'],int(r['tick'])):r for r in csv.DictReader(f)}
 with (ROOT/f'fixtures/{prefix}stuck-java.csv').open() as f: stuck={(r['case'],int(r['tick'])):r for r in csv.DictReader(f)}
 cases=('unlit',)
 for case in cases:
  with TemporaryDirectory(prefix='hc-pie-sticky-') as tmp:
   with fixture_world(args,'PieSticky',render=False,pack=args.pack) as host:
    host.commands(('/fill 5 100 0 12 100 16 minecraft:stone','/fill 5 101 0 12 106 16 minecraft:air'))
    with carrot.actor_for(host,args,Path(tmp)) as (actor,name):
     flag=1 if case=='invulnerable' else 0
     host.commands((f'/gamemode survival {name}',f'/tp {name} 8.5 101 3.5 0 0',f'/item replace entity {name} hotbar.0 with create:potato_cannon',f'/item replace entity {name} hotbar.1 with minecraft:pumpkin_pie 3',f'/summon minecraft:pig 8.0 102.0 8.5 {{NoAI:1b,NoGravity:1b,Invulnerable:{flag}b,Tags:["pie_target"]}}'))
     multiplayer.until('cannon and ammo',lambda:actor.call('inventory')['counts'].get('minecraft:pumpkin_pie')==3)
     actor.call('select','create:potato_cannon');actor.call('use-item')
     multiplayer.until('fired',lambda:actor.call('inventory')['counts'].get('minecraft:pumpkin_pie')==2)
     held=actor.call('inventory')['held'];assert held.get('damage',0)==int(launch[case]['damage'])
     start=host.clock()
     for tick in range(7):
      if tick:host.step_to(start+tick)
      if tick==3:host.command(f'/execute as {TARGET} at @s run tp @s ~2 ~ ~1')
      pig=carrot.data(host,TARGET);shot=carrot.data(host,SHOT);row=target[(case,tick)]
      import re
      health=float(re.search(r'\bHealth:\s*([\d.]+)f',pig)[1])
      assert math.isclose(health,float(row['health']),abs_tol=1e-6),(case,tick,health,row)
      assert bool(shot)==(int(row['shots'])>0),(case,tick,shot,row)
      if shot:
       expected=stuck[(case,tick)]
       relative=tuple(a-b for a,b in zip(carrot.vector(shot,'Pos'),carrot.vector(pig,'Pos'),strict=True))
       actual=(*relative,*carrot.vector(shot,'Motion'))
       values=tuple(float(expected[k]) for k in ('x','y','z','vx','vy','vz'))
       carrot.near(actual,values,f'{case} tick {tick}')
    print(f'{case}: moving pie attachment matched Java.',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for key in ('ctl','client','resources'):p.add_argument(key,type=lambda path:Path(path).resolve(strict=True))
 p.add_argument('--pack',type=Path,default=ROOT/'.local/create.hmod')
 p.add_argument('--lan',action='store_true')
 p.add_argument('--case',action='append',choices=('unlit','invulnerable'))
 os.environ['HORIZON_NO_AUDIO']='1'
 run(p.parse_args())
