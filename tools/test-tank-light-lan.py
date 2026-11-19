#!/usr/bin/env python3
"""Observe actual LAN client block light as the host fills and drains a tank."""
import argparse
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')


def request(world, action):
    return world.call('create-test-tank-script', json.dumps(action, separators=(',', ':')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument('--' + key, required=True, type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    args = parser.parse_args()
    env = {'HORIZON_NO_AUDIO': '1', 'CREATE_TANK_SCRIPT_CONTROL': '1'}
    with fixture_world(args, 'TankLightLAN', render=True, pack=args.pack, env=env) as host:
        host.command('/setblock 9 170 20 create:fluid_tank')
        port = host.call('lan', 'open', '0', 'commands', 'force')['port']
        with TemporaryDirectory(prefix='hc-tank-light-lan-') as scratch, mp.joined_client(
            args, Path(scratch), f'127.0.0.1:{port}', 'LightGuest', render=True,
            scenario='tank-light-lan', pack=args.pack, env=env,
        ) as guest:
            mp.until('guest joined', lambda: any(p['name'] == 'LightGuest' and p['placed'] for p in host.call('lan', 'status')['guests']))
            host.command('/tp LightGuest 9.5 170 23.5')
            mp.until('guest receives tank', lambda: guest.call('block', 9, 170, 20).get('block') == 'create:fluid_tank')
            def lights():
                return [request(guest, {'op':'world_light','pos':p})['block'] for p in ([9,170,20],[10,170,20])]
            def positive(read):
                value = read()
                return value if all(n > 0 for n in value) else None
            for _ in range(5): host.step_to(host.clock()+1)
            before = lights()
            request(host, {'op':'fill','pos':[9,170,20],'fluid':'minecraft:lava','amount':1000})
            for _ in range(10): host.step_to(host.clock()+1)
            filled = mp.until('guest receives tank light', lambda: positive(lights))
            with TemporaryDirectory(prefix='hc-tank-light-late-') as late_scratch, mp.joined_client(
                args, Path(late_scratch), f'127.0.0.1:{port}', 'LateLightGuest', render=True,
                scenario='tank-light-late-lan', pack=args.pack, env=env,
            ) as late:
                mp.until('late guest joined', lambda: any(p['name'] == 'LateLightGuest' and p['placed'] for p in host.call('lan', 'status')['guests']))
                host.command('/tp LateLightGuest 9.5 170 23.5')
                mp.until('late guest receives tank', lambda: late.call('block', 9, 170, 20).get('block') == 'create:fluid_tank')
                def late_lights():
                    return [request(late, {'op':'world_light','pos':p})['block'] for p in ([9,170,20],[10,170,20])]
                late_filled = mp.until('late guest receives tank light', lambda: positive(late_lights))
            request(host, {'op':'drain','pos':[9,170,20],'amount':1000})
            for _ in range(10): host.step_to(host.clock()+1)
            drained = mp.until('guest receives tank darkening', lambda: (v if (v := lights()) == [0, 0] else None))
    assert before == [0, 0] and all(v > 0 for v in filled) and drained == [0, 0], (before, filled, drained)
    print(json.dumps({'before':before, 'lava':filled, 'late_join':late_filled, 'drained':drained}))


if __name__ == '__main__':
    main()
