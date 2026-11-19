#!/usr/bin/env python3
"""Exercise the initial Steam Whistle placement, extension and redstone slice."""
import argparse
from importlib import import_module
from pathlib import Path
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')

def state(host, pos):
    return host.call('block', *pos)['state']

def run(args):
    with fixture_world(args, 'SteamWhistle', pack=args.pack, render=False,
                       env={'HORIZON_NO_AUDIO': '1'}) as host:
        for command in ('/gamemode creative', '/setblock 9 170 20 create:fluid_tank',
                       '/setblock 9 169 23 minecraft:stone', '/tp @s 9.5 170 23.5',
                       '/item replace entity @s hotbar.0 with create:steam_whistle',
                       '/item replace entity @s hotbar.1 with create:wrench'):
            host.call('command', command)
        mp.until('player positioned', lambda: host.call('state')['player']['position'] == [9.5, 170, 23.5])
        host.call('select', 'create:steam_whistle')
        host.call('look-at', 9.5, 170.5, 20.5)
        mp.until('tank targeted', lambda: (host.call('looking-at').get('block') or {}).get('pos') == [9, 170, 20])
        host.call('mouse', 'right', 'click')
        pos = (9, 170, 21)
        mp.until('whistle placed on tank', lambda: state(host, pos).startswith('create:steam_whistle['))
        print('placed:', state(host, pos), flush=True)
        host.call('look-at', 9.5, 170.5, 21.5)
        mp.until('whistle targeted', lambda: (host.call('looking-at').get('block') or {}).get('pos') == list(pos))
        host.call('mouse', 'right', 'click')
        mp.until('first extension', lambda: 'shape=single' in state(host, (9,171,21)))
        host.call('mouse', 'right', 'click')
        mp.until('double extension', lambda: 'shape=double' in state(host, (9,171,21)))
        host.call('select', 'create:wrench')
        host.call('mouse', 'right', 'click')
        mp.until('octave changed', lambda: 'size=large' in state(host, pos))
        assert 'size=large' in state(host, (9,171,21))
        host.command('/setblock 10 170 21 minecraft:redstone_block')
        mp.until('redstone on', lambda: 'powered=true' in state(host, pos))
        host.command('/setblock 10 170 21 minecraft:air')
        mp.until('redstone off', lambda: 'powered=false' in state(host, pos))
        host.call('select', 'create:steam_whistle')
        oracle = [line.split('|') for line in
                  (ROOT / 'fixtures/steam-whistle-java.txt').read_text().splitlines()
                  if line.startswith('CREATE_WHISTLE_GROW ')]
        for row in oracle[2:]:
            step = int(row[0].split()[-1])
            host.call('mouse', 'right', 'click')
            expected = [value.replace('Block{', '').replace('}', '').replace('size=medium', 'size=large') for value in row[1:]]
            mp.until(f'Java extension step {step}', lambda: all(
                state(host, (9, 170 + index, 21)) == value
                for index, value in enumerate(expected, 1)))
        host.command('/setblock 9 173 21 minecraft:air')
        mp.until('extension disconnects', lambda: 'shape=double,' in state(host, (9,172,21))
                 and state(host, (9,174,21)) == 'minecraft:air')
        host.command('/setblock 9 172 21 minecraft:air')
        mp.until('extension disconnects', lambda: 'shape=double,' in state(host, (9,171,21)))
        host.command('/setblock 9 170 20 minecraft:air')
        mp.until('unsupported whistle and extensions removed', lambda:
                 state(host, pos) == 'minecraft:air' and state(host, (9,171,21)) == 'minecraft:air')
        for command in ('/setblock 9 170 20 create:fluid_tank',
                        '/setblock 10 171 20 minecraft:redstone_block',
                        '/setblock 9 172 23 minecraft:stone', '/tp @s 9.5 173 23.5'):
            host.call('command', command)
        mp.until('player above tank', lambda: host.call('state')['player']['position'] == [9.5, 173, 23.5])
        host.call('look-at', 9.5, 171, 20.5)
        mp.until('tank top targeted', lambda: ((hit := host.call('looking-at').get('block') or {}).get('pos') == [9,170,20]
                                               and hit.get('face') == 'up'))
        host.call('mouse', 'right', 'click')
        mp.until('floor whistle initially powered', lambda: state(host, (9,171,20)) ==
                 'create:steam_whistle[facing=north,powered=true,size=medium,wall=false]')
        print('extension growth, wrench, redstone, support, and powered floor placement passed', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
