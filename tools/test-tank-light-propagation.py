#!/usr/bin/env python3
"""Check that a lava tank lights adjacent air and removing the fluid clears it.

This checks Horizon's actual world light; the headless Java GameTest server does
not supply a meaningful propagation oracle for this scenario.
"""
import argparse
import json
from pathlib import Path
from fixture_world import fixture_world


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument('--' + key, required=True, type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument('--pack', type=Path, required=True)
    args = parser.parse_args()
    def request(world, action):
        return world.call('create-test-tank-script', json.dumps(action, separators=(',', ':')))
    def tick(world):
        for _ in range(5):
            world.step_to(world.clock() + 1)
    with fixture_world(args, 'TankLightPropagation', render=False, pack=args.pack,
                       env={'HORIZON_NO_AUDIO': '1', 'CREATE_TANK_SCRIPT_CONTROL': '1'}) as world:
        world.command('/setblock 9 170 20 create:fluid_tank')
        tick(world)
        def light():
            return request(world, {'op': 'world_light', 'pos': [10, 170, 20]})['block']
        empty = light()
        fill = request(world, {'op': 'fill', 'pos': [9, 170, 20], 'fluid': 'minecraft:lava', 'amount': 1000})
        tick(world)
        filled = light()
        world.restart()
        tick(world)
        restored = light()
        source = request(world, {'op': 'probe', 'positions': [[9, 170, 20]], 'include_signals': True})['rows'][0]
        drain = request(world, {'op': 'drain', 'pos': [9, 170, 20], 'amount': 1000})
        tick(world)
        drained = light()
    assert fill['accepted'] == 1000 and drain['amount'] == 1000, (fill, drain)
    assert empty == 0 and filled > 0 and restored > 0 and drained == 0, (empty, filled, restored, drained)
    assert source['light'] == 12, source
    print(json.dumps({'empty': empty, 'lava': filled, 'reopened': restored, 'source_after_reopen': source['light'], 'drained': drained}))


if __name__ == '__main__':
    main()
