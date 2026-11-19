#!/usr/bin/env python3
"""Verify a player-assembled moving train powers a track observer."""
import argparse
from pathlib import Path
from importlib import import_module
from fixture_world import fixture_world
train = import_module('test-simple-train')

parser = argparse.ArgumentParser()
for name in ('ctl', 'client', 'resources'):
    parser.add_argument(name, type=lambda value: Path(value).resolve())
parser.add_argument('--pack', type=Path)
args = parser.parse_args()
with fixture_world(args, 'Track-observer-train', train.STRUCTURE, render=True, pack=args.pack, env={'HORIZON_NO_AUDIO':'1'}) as world:
    def observer(world):
        x, y, z = train.X - 5, train.Y, train.Z
        world.commands((f'/setblock {x} {y} {z+3} create:track_observer{{TargetTrack:[I;0,0,-3],TargetDirection:0b}}', f'/setblock {x+1} {y} {z+3} minecraft:redstone_wire'))
    train.setup(world, after_station=observer)
    x,y,z = train.X - 5, train.Y, train.Z + 3
    world.call('key', 'w', 'down')
    last = None
    seen = set()
    for i in range(130):
        world.step_to(world.clock()+1)
        state = world.call('block', x,y,z)['state']
        wire = world.call('block', x+1,y,z)['state']
        active = 'powered=true' in state
        assert f'power={15 if active else 0}' in wire, (state, wire)
        if active != last:
            sample = train.sample(world)
            print(f'tick={i+1} observer={state} wire={wire} train={sample}', flush=True)
            last = active
        seen.add(active)
    world.call('key', 'w', 'up')
    print('final train', train.sample(world), flush=True)
    assert seen == {False, True}, seen
