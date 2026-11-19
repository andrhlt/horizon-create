#!/usr/bin/env python3
"""Check two unseated LAN guests remain on a straight train through a reversal."""
import argparse
import re
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import fixture_world

train=import_module('test-simple-train')
mp=import_module('test-multiplayer')
X,Y,Z=train.X,train.Y,train.Z
GUESTS=(('RideOne',1.0),('RideTwo',3.0))


def sample(host):
    speed, raw = host.commands((f'/data get entity {train.ENTITY} CreateTrain.Speed',
                                f'/data get entity {train.ENTITY} CreateTrain.WheelPointsXYZ'))
    match=re.search(f'({train.NUMBER})d$',speed)
    values=[float(v) for v in re.findall(f'({train.NUMBER})d',raw)]
    assert match and len(values)==12,(speed,raw)
    return float(match.group(1)), X+(values[0]+values[3])*0.5


def run(args):
    with TemporaryDirectory(prefix='hc-rev-',dir='/private/tmp') as scratch, ExitStack() as stack:
        host=stack.enter_context(fixture_world(args,'TrainReversalStanding',train.STRUCTURE,render=True,
                                               pack=args.pack,env={'HORIZON_NO_AUDIO':'1'}))
        host.command('/attribute @s minecraft:gravity base set 0')
        train.setup(host)
        host.command('/attribute @s minecraft:gravity base set 0')
        port=host.call('lan','open','0','commands','force')['port']
        guests=[]
        for name,offset in GUESTS:
            guest=stack.enter_context(mp.joined_client(args,Path(scratch),f'127.0.0.1:{port}',name,
                                                       render=False,scenario='train-reversal',pack=args.pack,
                                                       env={'HORIZON_NO_AUDIO':'1'}))
            mp.until(f'{name} joined',lambda:any(p['name']==name and p['placed'] for p in host.call('lan','status')['guests']))
            host.command(f'/gamemode survival {name}')
            host.command(f'/attribute {name} minecraft:gravity base set 0')
            x=X+1.5+offset
            host.command(f'/tp {name} {x} {Y+3.0001001} {Z+0.5}')
            mp.until(f'{name} placed',lambda:abs(guest.call('state')['player']['position'][0]-x)<0.01)
            host.command(f'/attribute {name} minecraft:gravity base set 0.08')
            guests.append((name,guest,offset))
        host.command(f'/tp @s {X+1.5} {Y+7} {Z+1.5}')
        start=host.clock()
        forward=backward=False
        try:
            for tick in range(13,151):
                if tick>13: host.step_to(start+tick-13)
                speed,pivot=sample(host)
                forward |= speed>0.05
                backward |= speed< -0.02
                for name,guest,offset in guests:
                    player=guest.call('state')['player']
                    x,y,z=player['position']
                    assert abs(x-pivot-offset)<0.3 and abs(y-(Y+3.0001001))<0.2 and abs(z-(Z+0.5))<0.3,(tick,name,player,pivot,speed)
                if tick==18: host.call('key','w','down')
                if tick==60:
                    host.call('key','w','up')
                    host.call('key','s','down')
                if tick==145: host.call('key','s','up')
                if tick>=26 and tick%3==2:
                    host.command(f'/tp @s {pivot:.6f} {Y+7} {Z+1.5}')
                    host.call('wait',3)
        finally:
            host.call('key','w','up')
            host.call('key','s','up')
        assert forward and backward,(forward,backward)
    print('Both unseated LAN guests stayed on their deck blocks through forward travel and reversal.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('ctl','client','resources'): p.add_argument(name,type=lambda value:Path(value).resolve())
    p.add_argument('--pack',type=lambda value:Path(value).resolve())
    run(p.parse_args())
