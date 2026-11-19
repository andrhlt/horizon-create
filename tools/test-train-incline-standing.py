#!/usr/bin/env python3
"""Check a standing LAN guest through a gradual rising train connection."""
import argparse, csv, math, re
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world
train=import_module('test-simple-train')
mp=import_module('test-multiplayer')
X,Y,Z=train.X,train.Y,train.Z
GUEST='SlopeGuest'

def layout(w, updown=False):
 w.commands((f'/fill {X-4} {Y-1} {Z-5} {X+25} {Y-1} {Z+5} minecraft:smooth_stone',f'/fill {X-3} {Y} {Z} {X+24} {Y} {Z} create:track[shape=xo]', f'/fill {X-(26 if updown else 45)} {Y+4} {Z-4} {X-19} {Y+4} {Z+4} minecraft:smooth_stone', f'/fill {X-(26 if updown else 45)} {Y+5} {Z} {X-20} {Y+5} {Z} create:track[shape=xo]', '/gamemode survival',f'/tp @s {X-0.5} {Y} {Z+0.5} 90 20','/item replace entity @s hotbar.0 with create:track 64'))
 w.call('wait',3)
 w.call('key','1','tap')
 train.click_track(w,X-3)
 selected=w.command('/data get entity @s Inventory')
 assert 'create:track_connecting_from' in selected,selected
 w.command(f'/tp @s {X-17.5} {Y+5} {Z+0.5} 90 20')
 w.call('wait',3)
 w.call('interact',X-19,Y+4,Z,'up')
 w.call('wait',3)
 selected=w.command('/data get entity @s Inventory')
 assert 'create:track_connecting_from' not in selected,selected
 if updown:
  w.commands((f'/fill {X-65} {Y-1} {Z-4} {X-42} {Y-1} {Z+4} minecraft:smooth_stone',
              f'/fill {X-65} {Y} {Z} {X-43} {Y} {Z} create:track[shape=xo]',
              '/item replace entity @s hotbar.0 with create:track 64',
              f'/tp @s {X-24.5} {Y+5} {Z+0.5} 90 20'))
  w.call('wait',3)
  w.call('key','1','tap')
  w.call('look-at',X-25.5,Y+5.06,Z+0.5)
  w.call('mouse','right','click')
  w.call('wait',3)
  selected=w.command('/data get entity @s Inventory')
  assert 'create:track_connecting_from' in selected,selected
  w.command(f'/tp @s {X-40.5} {Y} {Z+0.5} 90 20')
  w.call('wait',3)
  w.call('interact',X-42,Y-1,Z,'up')
  w.call('wait',3)
  selected=w.command('/data get entity @s Inventory')
  assert 'create:track_connecting_from' not in selected,selected

def points(w):
 r=w.command(f'/data get entity {train.ENTITY} CreateTrain.WheelPointsXYZ')
 v=[float(n) for n in re.findall(f'({train.NUMBER})d',r)]
 assert len(v)==12,r
 return [v[i:i+3] for i in range(0,12,3)]

def run(a):
 if a.updown:
  with (ROOT / 'fixtures/train-updown-java.csv').open() as source:
   rows={int(row['tick']):row for row in csv.DictReader(source)}
  assert float(rows[90]['wheel_1_y'])>5.9 and float(rows[130]['wheel_1_y'])<1.1
 with TemporaryDirectory(prefix='hc-slope-',dir='/private/tmp') as scratch, fixture_world(a,'TrainIncline',train.STRUCTURE,render=True,pack=a.pack,env={'HORIZON_NO_AUDIO':'1'}) as h:
  h.command('/attribute @s minecraft:gravity base set 0')
  if a.updown: h.command(f'/forceload add {X-66} {Z} {X+25} {Z}')
  train.setup(h,lambda world: layout(world,a.updown))
  h.command('/attribute @s minecraft:gravity base set 0')
  port=h.call('lan','open','0','commands','force')['port']
  with mp.joined_client(a,Path(scratch),f'127.0.0.1:{port}',GUEST,render=False,scenario='train-incline',pack=a.pack,env={'HORIZON_NO_AUDIO':'1'}) as g:
   mp.until('guest join',lambda:any(p['name']==GUEST and p['placed'] for p in h.call('lan','status')['guests']))
   h.command(f'/gamemode survival {GUEST}')
   h.command(f'/attribute {GUEST} minecraft:gravity base set 0')
   h.command(f'/tp {GUEST} {X+4.5} {Y+3.0001001} {Z+0.5}')
   mp.until('guest on deck',lambda: abs(g.call('state')['player']['position'][0]-(X+4.5))<0.01)
   h.command(f'/attribute {GUEST} minecraft:gravity base set 0.08')
   h.command(f'/tp @s {X+1.5} {Y+7} {Z+1.5}')
   start=h.clock()
   highest=0.0
   try:
    for t in range(13,141 if a.updown else 101):
     if t>13:h.step_to(start+t-13)
     p=points(h); pivot=[(p[0][i]+p[1][i])/2 for i in range(3)]
     highest=max(highest,pivot[1])
     head=[(p[2][i]+p[3][i])/2-pivot[i] for i in range(3)]
     n=math.sqrt(sum(v*v for v in head)); hx,hy,hz=(v/n for v in head)
     state=g.call('state')['player'];x,y,z=state['position']
     dx,dy,dz=x-(X+pivot[0]),y-(Y+pivot[1]),z-(Z+pivot[2])
     lx=dx*hx+dy*hy+dz*hz; ly=-dx*hy+dy*hx
     assert abs(lx-3)<0.5 and abs(ly-2)<0.4 and abs(z-(Z+pivot[2]))<0.4, (t,state,pivot,head,lx,ly)
     if t==18:h.call('key','w','down')
     if t==(160 if a.updown else 92):h.call('key','w','up')
     if t>=26 and t%3==2:
      h.command(f'/tp @s {X+pivot[0]:.6f} {Y+pivot[1]+6:.6f} {Z+1.5:.6f}')
      h.call('wait',3)
   finally:h.call('key','w','up')
   assert highest>5.5 and (pivot[1]<1.5 if a.updown else pivot[1]>5.5), (highest,pivot)
   print('An unseated guest remained on the train through the gradual ' + ('ascent and descent.' if a.updown else 'incline.'))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for k in ('ctl','client','resources'):p.add_argument(k,type=lambda x:Path(x).resolve())
 p.add_argument('--pack',type=lambda x:Path(x).resolve())
 p.add_argument('--updown',action='store_true')
 run(p.parse_args())
