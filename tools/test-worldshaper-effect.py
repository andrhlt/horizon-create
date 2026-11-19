#!/usr/bin/env python3
"""Check actual Worldshaper shots on the local client and optional LAN guest."""
import argparse
import ast
import re
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')
selection = import_module('test-worldshaper-selection')


def run(args):
    env = {'HORIZON_NO_AUDIO': '1', 'HORIZON_CREATE_TEST_AUDIO': '1',
           'CREATE_WORLDSHAPER_EFFECT_TRACE': '1'}
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, 'WorldshaperEffect', render=True,
                                                    pack=args.pack, env=env))
        actor, player = host, '@s'
        observers = [host]
        if args.lan:
            player = 'ShaperFXGuest'
            port = host.call('lan', 'open', '0', 'commands')['port']
            scratch = Path(sessions.enter_context(TemporaryDirectory(prefix='hc-shaper-effects-')))
            if args.left:
                home = scratch / player
                home.mkdir(parents=True)
                (home / 'options.txt').write_text('mainHand:"left"\n')
            actor = sessions.enter_context(mp.joined_client(args, scratch, f'127.0.0.1:{port}',
                player, scenario='worldshaper-effect', pack=args.pack, env=env, render=True))
            mp.until('guest joins', lambda: any(p['name'] == player and p['placed']
                                                for p in host.call('lan', 'status')['guests']))
            observers.append(actor)
            host.commands(('/gamemode spectator @s', '/tp @s 11.5 170 26.5'))
        host.commands((
            '/fill 6 169 20 14 169 28 minecraft:stone',
            '/fill 6 170 20 14 175 28 minecraft:air',
            f'/gamemode survival {player}',
            f'/tp {player} 10.5 170 25.5',
            '/setblock 10 170 22 minecraft:stone',
        ))
        mp.until('actor arrives', lambda: actor.call('state')['player']['position'] == [10.5, 170.0, 25.5])
        if args.offhand:
            saved = (ROOT / 'fixtures/worldshaper_fill-components-java.snbt').read_text().strip()
            host.commands((
                '/setblock 14 170 27 minecraft:barrel',
                f'/data merge block 14 170 27 {{Items:[{{Slot:0b,id:"{selection.ITEM}",count:1,components:{saved}}}]}}',
                f'/item replace entity {player} weapon.offhand from block 14 170 27 container.0',
                f'/item replace entity {player} hotbar.0 with minecraft:air',
            ))
            mp.until('configured off-hand arrives', lambda: 'create:shaper_brush_params' in str(actor.call('inventory')))
            actor.call('look-at', 10.5, 170.4, 22.5)
            mp.until('target is aimed at', lambda: (actor.call('looking-at').get('block') or {}).get('pos') == [10, 170, 22])
            actor.call('mouse', 'right', 'click')
            mp.until('Fill places its cell', lambda: host.call('block', 10, 170, 23)['block'] == 'minecraft:stone')
        else:
            selection.fill(host, actor, player, False, False)
        for observer in observers:
            log = observer.socket.parent / 'ctl.log'
            def trace():
                return log.read_text(errors='replace') if log.exists() else ''
            mp.until('the Worldshaper shot effects', lambda: 'CREATE_WORLDSHAPER_EFFECT shot ' in trace())
            lines = [line for line in trace().splitlines() if 'CREATE_WORLDSHAPER_EFFECT shot ' in line]
            assert len(lines) == 1, lines
            match = re.search(r'shot (\[[^]]+\]) (\[[^]]+\])', lines[0])
            assert match, lines[0]
            start, end = (ast.literal_eval(value) for value in match.groups())
            eye = [10.5, 171.62, 25.5]
            assert sum((start[i] - eye[i]) * (end[i] - eye[i]) for i in range(3)) > 0, (start, end)
            main = str(not args.offhand).lower()
            pitch = '0.9' if args.offhand else '0.1'
            assert f'main={main} rods=10 fireworks=10' in lines[0], lines[0]
            assert f'sound=minecraft:block.note_block.basedrum pitch={pitch}' in lines[0], lines[0]
            if args.left or args.offhand:
                own = str(observer is actor).lower()
                assert f'CREATE_WORLDSHAPER_EFFECT recoil self={own} main={main}' in trace(), trace()
        if args.left:
            assert 'CREATE_WORLDSHAPER_EFFECT barrel left=true' in (host.socket.parent / 'ctl.log').read_text(errors='replace')
    print(f'Worldshaper shot delivered one beam, 10 End Rods, 10 fireworks, and {"off" if args.offhand else "main"}-hand cue to each client.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--lan', action='store_true')
    parser.add_argument('--left', action='store_true', help='use a left-handed LAN guest')
    parser.add_argument('--offhand', action='store_true', help='fire from the off hand')
    args = parser.parse_args()
    if args.left and not args.lan:
        parser.error('--left requires --lan')
    run(args)
