#!/usr/bin/env python3
"""Check a real unseated guest stays on a train through a quarter-turn."""
import argparse
import math
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import fixture_world

curve = import_module('test-curved-train')
mp = import_module('test-multiplayer')
train = curve.train
X, Y, Z = curve.X, curve.Y, curve.Z
GUEST = 'CurveGuest'


def run(args):
    with TemporaryDirectory(prefix='hc-curve-',dir='/private/tmp') as scratch, fixture_world(
        args, 'CurvedTrainStanding', train.STRUCTURE, render=True, pack=args.pack,
        env={'HORIZON_NO_AUDIO':'1'}) as host:
        host.command('/attribute @s minecraft:gravity base set 0')
        train.setup(host, curve.layout)
        host.command('/attribute @s minecraft:gravity base set 0')
        port=host.call('lan','open','0','commands','force')['port']
        with mp.joined_client(args,Path(scratch),f'127.0.0.1:{port}',GUEST,render=True,
                              scenario='curved-standing',pack=args.pack,env={'HORIZON_NO_AUDIO':'1'}) as guest:
            mp.until('guest join', lambda: any(p['name']==GUEST and p['placed'] for p in host.call('lan','status')['guests']))
            host.command(f'/gamemode survival {GUEST}')
            host.command(f'/attribute {GUEST} minecraft:gravity base set 0')
            host.command(f'/tp {GUEST} {X+4.5} {Y+3.0001001} {Z+0.5}')
            mp.until('guest on deck', lambda: abs(guest.call('state')['player']['position'][0]-(X+4.5))<0.01)
            host.command(f'/attribute {GUEST} minecraft:gravity base set 0.08')
            host.command(f"/tp @s {X+1.5} {Y+7} {Z+1.5}")
            start=host.clock()
            rotated=False
            max_lateral=0.0
            try:
                for t in range(13,101):
                    if t>13:
                        host.step_to(start+t-13)
                    v=curve.sample(host)
                    px=X+(v[1]+v[4])/2
                    pz=Z+(v[3]+v[6])/2
                    hx=(v[7]+v[10])/2-(v[1]+v[4])/2
                    hz=(v[9]+v[12])/2-(v[3]+v[6])/2
                    norm=math.hypot(hx,hz)
                    hx,hz=hx/norm,hz/norm
                    rotated |= abs(hz)>0.1
                    player=guest.call('state')['player']
                    x,y,z=player['position']
                    lx=(x-px)*hx+(z-pz)*hz
                    lz=-(x-px)*hz+(z-pz)*hx
                    max_lateral=max(max_lateral,abs(lz))
                    assert abs(y-(Y+3.0001001))<0.2 and abs(lx-3)<0.4 and abs(lz)<0.4, (t,player,px,pz,hx,hz,lx,lz)
                    if t==18:
                        host.call('key','w','down')
                    if t>=26 and t%3==2:
                        host.command(f'/tp @s {px:.6f} {Y+7} {pz+1.5:.6f}')
                        host.call('wait',3)
                assert rotated, 'Train did not enter curve'
            finally:
                host.call('key','w','up')
    print(f'Unseated guest stayed on the rotating curved train deck; maximum lateral offset was {max_lateral:.3f} blocks.')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('ctl','client','resources'):
        p.add_argument(name,type=lambda value: Path(value).resolve())
    p.add_argument('--pack',type=lambda value: Path(value).resolve())
    run(p.parse_args())
