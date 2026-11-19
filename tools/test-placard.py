#!/usr/bin/env python3
"""Exercise Placard placement, storage, matching pulse and retrieval in a muted world."""
import argparse
import csv
from pathlib import Path
from contextlib import ExitStack
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world
from importlib import import_module

mp = import_module('test-multiplayer')
probe = import_module('test-nozzle')


def run(args):
    env = {'HORIZON_NO_AUDIO': '1'}
    with ExitStack() as stack:
        game = stack.enter_context(fixture_world(args, 'Placard', render=not args.lan, pack=args.pack, env=env))
        actor, player = game, '@s'
        if args.lan:
            port = game.call('lan', 'open', '0', 'commands', 'force')['port']
            player = 'PlacardGuest'
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix='hc-placard-guest-')))
            actor = stack.enter_context(mp.joined_client(args, scratch, f'127.0.0.1:{port}', player, scenario='placard', pack=args.pack, render=True, env=env))
            mp.until('guest joins', lambda: any(g['name'] == player and g['placed'] for g in game.call('lan', 'status')['guests']))
        if args.lan:
            game.command('/tp @s 5.5 170 25.5')
        game.commands(('/fill 0 169 16 12 169 28 minecraft:stone',
                       '/setblock 5 170 20 minecraft:stone', f'/tp {player} 5.5 170 23.5',
                       f'/gamemode survival {player}', f'/clear {player}',
                       f'/item replace entity {player} hotbar.0 with create:placard',
                       f'/item replace entity {player} hotbar.1 with minecraft:diamond 3'))
        mp.until('inventory reaches player', lambda: mp.count(actor, 'create:placard') == 1 and mp.count(actor, 'minecraft:diamond') == 3)
        actor.call('select', 'create:placard')
        probe.aim(actor, (5.5, 170.5, 20.5), (5, 170, 20), 'south')
        actor.call('mouse', 'right', 'click')
        at = (5, 170, 21)
        mp.until('wall placard placement', lambda: 'create:placard' in probe.state(game, at))
        assert 'face=wall' in probe.state(game, at) and 'facing=south' in probe.state(game, at)
        game.command('/setblock 5 171 21 minecraft:redstone_lamp')
        actor.call('select', 'minecraft:diamond')
        probe.aim(actor, (5.5, 170.5, 21.5), at)
        actor.call('mouse', 'right', 'click')
        mp.until('stored item', lambda: 'diamond' in game.command('/data get block 5 170 21 Item'))
        assert mp.count(actor, 'minecraft:diamond') == 2
        actor.call('mouse', 'right', 'click')
        mp.until('matching item powers placard', lambda: 'powered=true' in probe.state(game, at))
        mp.until('redstone lamp receives output', lambda: 'lit=true' in probe.state(game, (5, 171, 21)))
        if args.lan:
            mp.until('guest sees powered placard', lambda: 'powered=true' in probe.state(actor, at))
        actor.call('mouse', 'left', 'click')
        mp.until('attack returns item', lambda: mp.count(actor, 'minecraft:diamond') == 3)
        with (ROOT / 'fixtures/placard-pulse-java.csv').open(newline='') as file:
            pulse = list(csv.DictReader(file))
        start = game.clock()
        for row in pulse[1:]:
            tick = int(row['tick'])
            game.step_to(start + tick)
            expected = row['powered']
            mp.until(f'Java pulse state at tick {tick}', lambda: f'powered={expected}' in probe.state(game, at))
        game.command('/setblock 5 170 20 minecraft:air')
        mp.until('placard drops when support is removed', lambda: probe.state(game, at) == 'minecraft:air')
        game.commands(('/kill @e[type=minecraft:item]', '/setblock 5 170 20 minecraft:stone',
                       '/setblock 5 170 21 create:placard[face=wall,facing=south]',
                       f'/item replace entity {player} hotbar.1 with minecraft:diamond 3'))
        mp.until('diamond stack reaches player', lambda: mp.count(actor, 'minecraft:diamond') == 3)
        actor.call('select', 'minecraft:diamond')
        probe.aim(actor, (5.5, 170.5, 21.5), at)
        actor.call('mouse', 'right', 'click')
        mp.until('item stored before support removal', lambda: 'diamond' in game.command('/data get block 5 170 21 Item'))
        game.command('/setblock 5 170 20 minecraft:air')
        mp.until('stored item drops with detached placard', lambda: mp.count(actor, 'minecraft:diamond') == 3 or any(
            item['item']['item'] == 'minecraft:diamond' for item in game.call('entities', 12, 'minecraft:item')['entities']))
    print('Placard wall placement, item storage, matching pulse, retrieval, and support removal passed.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--lan', action='store_true')
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
