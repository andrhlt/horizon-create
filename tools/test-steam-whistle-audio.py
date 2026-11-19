#!/usr/bin/env python3
"""Exercise whistle-only boiler heat and muted sound event/pitch transitions."""
import argparse
import math
from pathlib import Path
from fixture_world import ROOT, fixture_world


def events(host):
    path = host.socket.parent / 'ctl.log'
    rows = []
    if path.exists():
        for line in path.read_text().splitlines():
            if 'CREATE_WHISTLE_REQUEST ' not in line:
                continue
            values = line.split('CREATE_WHISTLE_REQUEST ', 1)[1].split(',')
            if len(values) == 8:
                rows.append((values[0], int(values[1]), float(values[5]), float(values[6]), values[7] == 'true'))
    return rows


def step(host, count):
    host.call('command', f'/tick step {count}')
    host.call('wait', count + 4)


def run(args):
    env = {'HORIZON_NO_AUDIO': '1', 'HORIZON_CREATE_WHISTLE_TRACE': '1'}
    with fixture_world(args, 'WhistleAudio', pack=args.pack, env=env) as host:
        for cmd in ('/tp @s 9.5 170 23.5', '/setblock 9 170 20 create:fluid_tank',
                    '/setblock 9 171 20 create:steam_whistle[facing=north,powered=false,size=medium,wall=false]',
                    '/setblock 10 171 20 minecraft:redstone_block'):
            host.call('command', cmd)
        step(host, 8)
        assert not events(host), events(host)
        host.call('command', '/setblock 9 169 20 minecraft:magma_block')
        step(host, 15)
        boiler = host.call('command', '/data get block 9 170 20')['chat'][-1]
        assert 'Whistles: 1' in boiler and 'PassiveHeat: 1b' in boiler, boiler
        rows = events(host)
        assert any(event == 'create:whistle' and source == 2 and start and abs(pitch - 1) < 1e-6
                   for event, source, volume, pitch, start in rows), rows
        host.call('command', '/setblock 9 172 20 create:steam_whistle_extension[shape=single,size=medium]')
        step(host, 6)
        rows = events(host)
        assert any(event == 'create:whistle' and not start and abs(pitch - 2 ** (-1 / 12)) < 1e-5
                   for event, source, volume, pitch, start in rows), rows
        host.call('command', '/setblock 10 171 20 minecraft:air')
        step(host, 8)
        rows = events(host)
        fades = [volume for event, source, volume, pitch, start in rows if event == 'create:whistle' and not start]
        assert len(fades) >= 3 and fades[-1] < fades[-2], fades
        host.call('command', '/setblock 9 171 20 create:steam_whistle[facing=north,powered=false,size=small,wall=false]')
        host.call('command', '/setblock 10 171 20 minecraft:redstone_block')
        step(host, 8)
        rows = events(host)
        assert any(event == 'create:whistle_high' and start and abs(pitch - 2 ** (-1 / 12)) < 1e-5
                   for event, source, volume, pitch, start in rows), rows
        host.call('command', '/setblock 10 171 20 minecraft:air')
        step(host, 1)
        host.call('command', '/setblock 10 171 20 minecraft:redstone_block')
        step(host, 6)
        assert sum(event == 'create:whistle_high' and start for event, source, volume, pitch, start in events(host)) == 2, events(host)
        print('whistle-only boiler, muted onset, tuned pitch, fade, octave and retrigger passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
