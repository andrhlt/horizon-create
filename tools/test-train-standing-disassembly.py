#!/usr/bin/env python3
"""Check two unseated guests through train disassembly and reassembly."""
import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import fixture_world

train=import_module('test-simple-train')
mp=import_module('test-multiplayer')
X,Y,Z=train.X,train.Y,train.Z
GUESTS=(('RideOne',X+2.5),('RideTwo',X+4.5))


def check(guest, expected, phase):
    state=guest.call('state')['player']
    pos=state['position']
    assert all(abs(a-b)<0.18 for a,b in zip(pos,expected)),(phase,state,expected)
    assert state['health']>0 and not state['flying'],(phase,state)
    return state


def run(args):
    with TemporaryDirectory(prefix='hc-dis-',dir='/private/tmp') as scratch, ExitStack() as stack:
        host=stack.enter_context(fixture_world(args,'TrainStandingDisassembly',train.STRUCTURE,render=True,
                                               pack=args.pack,env={'HORIZON_NO_AUDIO':'1'}))
        host.command('/attribute @s minecraft:gravity base set 0')
        train.setup(host)
        host.command('/attribute @s minecraft:gravity base set 0')
        port=host.call('lan','open','0','commands','force')['port']
        guests=[]
        for name,x in GUESTS:
            guest=stack.enter_context(mp.joined_client(args,Path(scratch),f'127.0.0.1:{port}',name,
                                                       render=False,scenario='train-standing-disassembly',
                                                       pack=args.pack,env={'HORIZON_NO_AUDIO':'1'}))
            mp.until(f'{name} joined',lambda:any(p['name']==name and p['placed'] for p in host.call('lan','status')['guests']))
            host.command(f'/gamemode survival {name}')
            host.command(f'/attribute {name} minecraft:gravity base set 0')
            expected=(x,Y+3.0001001,Z+0.5)
            host.command(f'/tp {name} {x} {expected[1]} {expected[2]} 0 0')
            mp.until(f'{name} placed',lambda:abs(guest.call('state')['player']['position'][0]-x)<0.01)
            host.command(f'/attribute {name} minecraft:gravity base set 0.08')
            guests.append((name,guest,expected))
        host.step_to(host.clock()+1)
        for name,guest,expected in guests:
            check(guest,expected,'before disassembly')
        sx,sy,sz=train.STATION
        host.command(f'/tp @s {sx+0.5} {sy} {sz+2.5} 180 20')
        host.call('wait',3)
        host.call('interact',*train.STATION,'up')
        host.call('wait',4)
        host.call('click-button','Disassemble Train')
        host.step_to(host.clock()+1)
        host.call('wait',3)
        host.call('key','esc','tap')
        assert 'assembling=true' in host.call('block',*train.STATION)['state']
        for name,guest,expected in guests:
            assert host.call('block',int(expected[0]),Y+2,Z)['block']=='minecraft:oak_planks'
            assert host.call('block',int(expected[0]),Y+3,Z)['block']=='minecraft:air'
            check(guest,expected,'after disassembly')
        # Small lateral input stays on the deck and verifies no passenger is trapped.
        for name,guest,expected in guests:
            host.command(f'/attribute {name} minecraft:movement_speed base set 0.01')
            guest.call('key','w','down')
            host.step_to(host.clock()+1)
            guest.call('key','w','up')
            host.command(f'/attribute {name} minecraft:movement_speed base set 0')
            pos=guest.call('state')['player']['position']
            assert abs(pos[2]-expected[2])>0.005 and abs(pos[2]-expected[2])<0.35,(name,pos,expected)
        expected_after=[(name,guest,tuple(guest.call('state')['player']['position'])) for name,guest,_ in guests]
        host.call('interact',*train.STATION,'up')
        host.call('wait',4)
        host.call('click-button','Assemble Train')
        host.step_to(host.clock()+1)
        host.call('wait',3)
        host.call('key','esc','tap')
        assert 'assembling=false' in host.call('block',*train.STATION)['state']
        for name,guest,expected in expected_after:
            check(guest,expected,'after reassembly')
        for _ in range(3): host.step_to(host.clock()+1)
        for name,guest,expected in expected_after:
            check(guest,expected,'after reassembly settles')
    print('Two unseated guests stayed free on the deck through disassembly and reassembly.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('ctl','client','resources'): p.add_argument(name,type=lambda value:Path(value).resolve())
    p.add_argument('--pack',type=lambda value:Path(value).resolve())
    run(p.parse_args())
