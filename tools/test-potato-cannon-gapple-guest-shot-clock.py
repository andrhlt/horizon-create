#!/usr/bin/env python3
"""Check real LAN guest shot times against the Java 100-tick minimum.

Uses an opt-in server-side successful-shot trace. The client repeatedly clicks;
it may miss the first eligible server tick, so the measured interval is a
minimum-bound check, not a proof that a particular tick-100 click fired.
"""
import argparse
import os
import re
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

placement = import_module('test-package-placement')
filters, editor = placement.package.filters, placement.editor


def run(args):
    for case in args.case or ('golden', 'enchanted'):
        ammo = ('minecraft:golden_apple' if case == 'golden'
                else 'minecraft:enchanted_golden_apple')
        with TemporaryDirectory(prefix='hc-gc-') as scratch:
            with fixture_world(args, 'GappleGuestShotClock', render=True, pack=args.pack,
                               env={'HORIZON_CREATE_CANNON_TRACE': '1'}) as host:
                host.commands((
                    '/fill 5 100 0 12 100 50 minecraft:stone',
                    '/fill 5 101 0 12 106 50 minecraft:air',
                ))
                with filters.actor_for(host, args, Path(scratch)) as (actor, name):
                    host.commands((
                        f'/gamemode survival {name}',
                        f'/tp {name} 8.5 101 3.5 0 0',
                        f'/item replace entity {name} hotbar.0 with create:potato_cannon',
                        f'/item replace entity {name} hotbar.1 with {ammo} 3',
                    ))
                    actor.call('key', '1', 'tap')
                    editor.wait_for(actor, 'cannon and ammo', lambda:
                        (actor.call('inventory')['held'] or {}).get('item') == 'create:potato_cannon'
                        and actor.call('inventory')['counts'].get(ammo) == 3)
                    actor.call('wait', 10)
                    actor.call('script', script='mouse right click\nwait 1\ninventory\n' * 105)
                    log = (host.socket.parent / 'ctl.log').read_text()
                    pattern = (r'CREATE_CANNON_SHOT role=lan_actor conn=Some\((\d+)\) ammo='
                               + re.escape(ammo) + r' play_time=(\d+)')
                    shots = [(int(conn), int(tick)) for conn, tick in re.findall(pattern, log)]
                    assert len(shots) >= 2, (case, shots)
                    assert shots[0][0] == shots[1][0], (case, shots)
                    interval = shots[1][1] - shots[0][1]
                    assert interval >= 100, (case, shots, interval)
                    print(f'{case}: guest successful shots at player ticks {shots[0][1]} and '
                          f'{shots[1][1]}, interval {interval} (Java minimum 100).', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--lan', action='store_true', default=True)
    parser.add_argument('--case', action='append', choices=('golden', 'enchanted'))
    os.environ['HORIZON_NO_AUDIO'] = '1'
    run(parser.parse_args())
