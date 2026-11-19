#!/usr/bin/env python3
"""Compare survival guest creative-tank honey/chocolate buckets with Java."""
import argparse
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument('--' + name, required=True, type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    args = parser.parse_args()
    rows = [json.loads(line) for line in (ROOT / 'fixtures/tank-scripts/java/container-buckets.jsonl').read_text().splitlines()]
    with fixture_world(args, 'TankContainerBucketsLAN', render=True, pack=args.pack, env={'HORIZON_NO_AUDIO':'1'}) as host:
        host.commands(('/setblock 9 170 20 create:creative_fluid_tank', '/setblock 9 169 23 minecraft:stone'))
        port = host.call('lan', 'open', '0', 'commands', 'force')['port']
        with TemporaryDirectory(prefix='hc-tank-container-lan-') as scratch, mp.joined_client(
            args, Path(scratch), f'127.0.0.1:{port}', 'ContainerGuest', render=True,
            scenario='tank-container-buckets-lan', pack=args.pack, env={'HORIZON_NO_AUDIO':'1'},
        ) as guest:
            mp.until('guest joined', lambda: any(p['name'] == 'ContainerGuest' and p['placed'] for p in host.call('lan', 'status')['guests']))
            host.commands(('/gamemode survival ContainerGuest', '/tp ContainerGuest 9.5 170 23.5'))
            mp.until('guest positioned', lambda: guest.call('state')['player']['position'] == [9.5, 170, 23.5])
            host.step_to(host.clock() + 1)
            guest.call('look-at', 9.5, 170.5, 20.5)
            mp.until('guest targets tank', lambda: (guest.call('looking-at').get('block') or {}).get('pos') == [9,170,20])
            def select_when_received(item):
                try:
                    guest.call('select', item)
                    return True
                except RuntimeError as error:
                    if 'not in the inventory' not in str(error):
                        raise
                    return False
            for lane, fluid in ((2, 'honey'), (3, 'chocolate')):
                insert = next(r for r in rows if r.get('label') == f'{lane}-insert')
                extract = next(r for r in rows if r.get('label') == f'{lane}-extract')
                held_rows = [r for r in rows if r['type'] == 'use_item' and r['pos'] == [lane * 6, 0, 0]]
                host.commands(('/clear ContainerGuest', f'/item replace entity ContainerGuest hotbar.0 with create:{fluid}_bucket'))
                mp.until('guest receives filled bucket', lambda: select_when_received(f'create:{fluid}_bucket'))
                mp.until('guest holds filled bucket', lambda: f'id: "create:{fluid}_bucket"' in host.command('/data get entity ContainerGuest SelectedItem'))
                guest.call('mouse', 'right', 'click')
                def contents(expected):
                    tag = host.command('/data get block 9 170 20')
                    return tag if ((f'id: "{expected["fluid"]}"' in tag and f'amount: {expected["amount"]}' in tag) if expected['amount'] else 'TankContent: {Fluid:' not in tag) else None
                mp.until('tank receives fluid', lambda: contents(insert))
                selected = host.command('/data get entity ContainerGuest SelectedItem')
                assert f'id: "{held_rows[0]["held"]["id"]}"' in selected and 'count: 1' in selected, selected
                host.commands(('/item replace entity ContainerGuest hotbar.0 with minecraft:bucket', '/item replace entity ContainerGuest hotbar.1 with minecraft:air'))
                mp.until('guest receives empty bucket', lambda: select_when_received('minecraft:bucket'))
                mp.until('guest holds empty bucket', lambda: 'id: "minecraft:bucket"' in host.command('/data get entity ContainerGuest SelectedItem'))
                guest.call('mouse', 'right', 'click')
                mp.until('tank clears', lambda: contents(extract))
                returned = held_rows[1]['inventory'][0]['item']['id']
                mp.until('guest receives Java returned bucket', lambda: f'id: "{returned}"' in host.command('/data get entity ContainerGuest Inventory'))
                selected = host.command('/data get entity ContainerGuest SelectedItem')
                assert f'id: "{held_rows[1]["held"]["id"]}"' in selected and 'count: 1' in selected, selected
    print('Survival guest honey and chocolate creative-tank contents, held buckets, and returned items matched Java.')


if __name__ == '__main__':
    main()
