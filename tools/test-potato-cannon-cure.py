#!/usr/bin/env python3
"""Probe golden apple impacts on weak and ordinary zombie villagers."""
import argparse,os,re,math
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT,fixture_world
carrot=import_module('test-potato-cannon-carrot')
multiplayer=import_module('test-multiplayer')
TARGET='@e[tag=cure_target,limit=1]'
SHOT='@e[type=create:potato_projectile,limit=1]'

def run(args):
 for case in args.case or ('weak','no_weakness'):
  with TemporaryDirectory(prefix='hc-cannon-cure-') as tmp:
   with fixture_world(args,'CannonCure',render=False,pack=args.pack) as host:
    host.commands(('/fill 5 100 0 12 100 16 minecraft:stone','/fill 5 101 0 12 106 16 minecraft:air'))
    with carrot.actor_for(host,args,Path(tmp)) as (actor,name):
     host.command(f'/gamemode survival {name}')
     host.command(f'/tp {name} 8.5 101 3.5 0 0')
     host.command(f'/item replace entity {name} hotbar.0 with create:potato_cannon')
     host.command(f'/item replace entity {name} hotbar.1 with minecraft:golden_apple 3')
     host.command('/summon minecraft:zombie_villager 8.0 102.0 8.5 {NoAI:1b,NoGravity:1b,Tags:["cure_target"]}')
     if case=='weak':
      host.command(f'/effect give {TARGET} minecraft:weakness 30 0 true')
      host.step_to(host.clock()+1)
     multiplayer.until('cannon and ammo',lambda:actor.call('inventory')['counts'].get('minecraft:golden_apple')==3)
     actor.call('select','create:potato_cannon');actor.call('use-item')
     multiplayer.until('shot',lambda:actor.call('inventory')['counts'].get('minecraft:golden_apple')==2)
     initial_time=None
     for tick in range(5):
      if tick:host.step_to(host.clock()+1)
      raw=carrot.data(host,TARGET)
      print(f'{case} tick {tick}: {raw}',flush=True)
      if args.baseline: continue
      health=float(re.search(r'\bHealth:\s*([\d.]+)f',raw)[1])
      absorption=float(re.search(r'\bAbsorptionAmount:\s*([\d.]+)f',raw)[1])
      timer=int(re.search(r'\bConversionTime:\s*(-?\d+)',raw)[1])
      match=re.search(r'\bactive_effects:\s*(\[[^\]]*\])',raw)
      entries=re.findall(r'\{[^{}]*\}',match[1] if match else '')
      effects={}
      for entry in entries:
       name=re.search(r'id:\s*"minecraft:([a-z_]+)"',entry)
       duration=re.search(r'duration:\s*(\d+)',entry)
       amp=re.search(r'amplifier:\s*(\d+)',entry)
       if name and duration:effects[name[1]]=(int(duration[1]),int(amp[1]) if amp else 0)
      assert math.isclose(health,20 if tick<2 else 19.059999466,abs_tol=1e-5),(case,tick,health)
      assert (carrot.data(host,SHOT) is not None)==(tick<2),(case,tick,'projectile')
      if case=='weak':
       assert absorption==0,(case,tick,absorption)
       if tick<2:
        assert timer==-1 and effects.get('weakness')==(599-tick,0),(case,tick,timer,effects)
       else:
        if tick==2:
         initial_time=timer
         assert 3600<=timer<=6000,(case,tick,timer)
        assert timer==initial_time-(tick-2) and effects=={'strength':(timer,0)},(case,tick,timer,effects)
        credit=re.search(r'\bConversionPlayer:\s*\[I;\s*([^\]]+)\]',raw)
        assert credit and tuple(int(v.strip()) for v in credit[1].split(','))==(-1106062372,668158354,-1936234818,1409108421),(case,tick,raw)
      else:
       assert timer==-1 and absorption==(0 if tick<2 else 4),(case,tick,timer,absorption)
       expected={} if tick<2 else {'absorption':(2402-tick,0)}
       assert effects==expected,(case,tick,effects,expected)
     if not args.baseline:print(f'{case}: Java conversion and effects matched',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for key in ('ctl','client','resources'):p.add_argument(key,type=lambda path:Path(path).resolve(strict=True))
 p.add_argument('--pack',type=Path,default=ROOT/'.local/create.hmod')
 p.add_argument('--lan',action='store_true')
 p.add_argument('--baseline',action='store_true')
 p.add_argument('--case',action='append',choices=('weak','no_weakness'))
 os.environ['HORIZON_NO_AUDIO']='1'
 run(p.parse_args())
