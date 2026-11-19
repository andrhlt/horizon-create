#!/usr/bin/env python3
"""Display the name of a player-assembled train passing a Track Observer."""
import argparse
from contextlib import ExitStack
from tempfile import TemporaryDirectory
from importlib import import_module
from pathlib import Path
from fixture_world import ROOT, fixture_world

train = import_module('test-simple-train')
mp = import_module('test-multiplayer')


def run(args):
    with ExitStack() as sessions:
        world = sessions.enter_context(fixture_world(args, 'ObservedTrainDisplay', train.STRUCTURE, render=True,
                       pack=args.pack, env={'HORIZON_NO_AUDIO': '1'}))
        x, y, z = train.X - 5, train.Y, train.Z + 3
        def observer(control):
            control.commands((
                f'/setblock {x} {y} {z} create:track_observer{{TargetTrack:[I;0,0,-3],TargetDirection:0b}}',
                f'/setblock {x+1} {y} {z} create:display_link[facing=east]{{TargetOffset:[I;2,0,0],Source:{{Id:"create:observed_train_name",Label:""}}}}',
                f'/setblock {x+3} {y} {z} create:nixie_tube',
            ))
        train.setup(world, after_station=observer)
        if args.lan:
            port = world.call('lan', 'open', '0', 'commands')['port']
            scratch = Path(sessions.enter_context(TemporaryDirectory(prefix='hc-observed-train-')))
            guest = sessions.enter_context(mp.joined_client(args, scratch, f'127.0.0.1:{port}', 'TrainView',
                render=True, scenario='observed-train-display', pack=args.pack, env={'HORIZON_NO_AUDIO': '1'}))
            mp.until('guest joins', lambda: any(p['name'] == 'TrainView' and p['placed'] for p in world.call('lan', 'status')['guests']))
            world.commands(('/op TrainView', f'/tp TrainView {x+1.5} {y} {z+2.5}'))
            mp.until('guest sees display link', lambda: guest.call('block', x+1, y, z)['block'] == 'create:display_link')
            guest.call('interact', x+1, y, z, 'south')
            mp.until('train-name source button', lambda: any(button.get('label') == 'Detected Train Name'
                for button in guest.call('screen').get('buttons', [])))
            guest.call('click-button', 'Detected Train Name')
            guest.call('key', 'escape', 'tap')
        world.call('key', 'w', 'down')
        seen, last = set(), None
        for tick in range(130):
            world.step_to(world.clock() + 1)
            active = 'powered=true' in world.call('block', x, y, z)['state']
            if active != last:
                data = world.command(f'/data get block {x+3} {y} {z} CustomText')
                print(f'tick={tick+1} active={active} text={data}', flush=True)
                if active:
                    assert 'Unnamed Train' in data, data
                elif True in seen:
                    assert 'Unnamed Train' not in data, data
                last = active
            seen.add(active)
        world.call('key', 'w', 'up')
        assert seen == {False, True}, seen
    print('An assembled moving train displayed its Java default name and cleared after observation.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--lan', action='store_true', help='configure the source from a LAN guest')
    run(parser.parse_args())
