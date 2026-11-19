#!/usr/bin/env python3
"""Check a LAN guest standing on a moving train at normal tick rate."""
import argparse
import time
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import fixture_world

base = import_module('test-train-postbox-import')
probe = import_module('test-train-standing')
mp = import_module('test-multiplayer')
trip, train, conductor = base.trip, base.train, base.conductor
GUEST = 'TrainGuest'


def run(args):
    base.configure_positions()
    with TemporaryDirectory(prefix='hc-ts-', dir='/private/tmp') as scratch, fixture_world(
        args, 'TrainStandingLan', train.STRUCTURE, render=True, pack=args.pack,
        env={'HORIZON_NO_AUDIO': '1'}) as host:
        host.command('/attribute @s minecraft:gravity base set 0')
        host.command(f'/forceload add {train.X-21} {base.Z} {train.X+25} {base.Z}')
        train.setup(host, after_station=trip.place_stations, take_controls=False)
        conductor.set_held(host, host, '@s', conductor.SCHEDULE, components=trip.PROGRAM)
        conductor.click(host, host, '@s', 0)
        assert conductor.assigned(host) is not None
        port = host.call('lan', 'open', '0', 'commands', 'force')['port']
        with mp.joined_client(args, Path(scratch), f'127.0.0.1:{port}', GUEST,
                              render=True, scenario='train-standing-lan', pack=args.pack,
                              env={'HORIZON_NO_AUDIO': '1'}) as guest:
            mp.until('guest join', lambda: any(p['name'] == GUEST and p['placed'] for p in host.call('lan','status')['guests']))
            host.command(f'/gamemode survival {GUEST}')
            host.command(f'/attribute {GUEST} minecraft:gravity base set 0')
            x0, y0, z0 = train.X+3.5, base.Y+3.0001001, base.Z+0.5
            host.command(f'/tp {GUEST} {x0} {y0} {z0} 0 0')
            mp.until('guest placed on deck', lambda: abs(guest.call('state')['player']['position'][0]-x0)<0.01)
            host.command(f'/attribute {GUEST} minecraft:gravity base set 0.08')
            host.command('/tp @s 512 120 512')
            car0 = probe.carriage_x(host)
            host.command('/tick unfreeze')
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                time.sleep(0.1)
                player = guest.call('state')['player']
                x, y, z = player['position']
                car = probe.carriage_x(host)
                assert abs(y-y0)<0.2, (player,car)
                if abs(car-car0)>0.7:
                    assert abs((x-x0)-(car-car0))<0.3, (player,car,car0)
                    break
            else:
                raise AssertionError('Train did not move')
            print('LAN guest remained on the live moving train.')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('ctl','client','resources'):
        p.add_argument(name,type=lambda value: Path(value).resolve())
    p.add_argument('--pack',type=lambda value: Path(value).resolve())
    run(p.parse_args())
