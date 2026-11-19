#!/usr/bin/env python3
"""Run one tank action script against the production core or a headless Horizon.

Fill is fixture setup, not a player/bucket assertion. Golden JSONL comes from
capture-tank-script-java.py; every emitted record is compared without rebasing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from fixture_world import ROOT, fixture_world


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def compare(actual, expected):
    if len(actual) != len(expected):
        raise AssertionError(f'record count: actual {len(actual)}, Java {len(expected)}')
    for index, (observed, java) in enumerate(zip(actual, expected, strict=True)):
        if observed != java:
            raise AssertionError(f'record {index}: actual {observed}; Java {java}')


def horizon(args, script):
    origin = (9, 170, 20)
    def absolute(pos):
        return [a + b for a, b in zip(origin, pos, strict=True)]
    def relative(pos):
        return [a - b for a, b in zip(pos, origin, strict=True)] if pos is not None else None
    actions = script['actions']
    tick, index = 0, 0
    rows = []
    with fixture_world(args, 'TankScript', render=False, pack=args.pack,
                       env={'HORIZON_NO_AUDIO': '1', 'CREATE_TANK_SCRIPT_CONTROL': '1'}) as world:
        while index < len(actions):
            action = actions[index]
            op = action['op']
            if op in ('place', 'remove'):
                commands = []
                while index < len(actions) and actions[index]['op'] in ('place', 'remove'):
                    item = actions[index]
                    at = ' '.join(map(str, absolute(item['pos'])))
                    state = ('create:creative_fluid_tank' if item.get('block') == 'creative' else 'create:fluid_tank') if item['op'] == 'place' else 'minecraft:air destroy'
                    commands.append(f'/setblock {at} {state}')
                    index += 1
                world.commands(commands)
                continue
            if op == 'tick':
                for _ in range(action['count']):
                    world.step_to(world.clock() + 1)
                    tick += 1
            elif op == 'use_item':
                at = absolute(action['pos'])
                item = action['item']
                component = item.get('components', {})
                suffix = '[' + ','.join(f'{key}={json.dumps(value, separators=(",", ":"))}' for key, value in component.items()) + ']' if component else ''
                world.call('command', '/clear @s')
                for command in (f"/gamemode {action['mode']}",
                                f"/item replace entity @s weapon.mainhand with {item['id']}{suffix} {item.get('count', 1)}",
                                f'/tp @s {at[0] + 0.5} {at[1]} {at[2] - 2.5}'):
                    world.call('command', command)
                world.call('interact', *at, 'north')
                observed = world.call('create-test-tank-script', '{"op":"inventory"}')
                rows.append({'type': 'use_item', 'tick': tick, 'pos': action['pos'], 'held': observed['held'], 'inventory': observed['inventory']})
            elif op == 'wrench':
                at = absolute(action['pos'])
                world.command('/item replace entity @s weapon.mainhand with create:wrench')
                world.command(f'/tp @s {at[0] + 0.5} {at[1]} {at[2] - 2.5}')
                world.call('interact', *at, 'north')
            elif op in ('fill', 'drain', 'configure', 'probe'):
                request = dict(action)
                request['include_components'] = script.get('include_components', False)
                request['include_shape'] = script.get('include_shape', False)
                request['include_signals'] = script.get('include_signals', False)
                request['include_block_light'] = script.get('include_block_light', False)
                if op != 'probe':
                    request['pos'] = absolute(action['pos'])
                else:
                    request['positions'] = [absolute(pos) for pos in action['positions']]
                response = world.call('create-test-tank-script', json.dumps(request, separators=(',', ':')))
                if op == 'fill':
                    rows.append({'type': 'fill', 'tick': tick, 'pos': action['pos'], 'accepted': response['accepted']})
                elif op == 'drain':
                    row = {'type': 'drain', 'tick': tick, 'pos': action['pos'], 'fluid': response['fluid'], 'amount': response['amount']}
                    if script.get('include_components'):
                        row['components'] = response['components']
                    rows.append(row)
                elif op == 'configure':
                    rows.append({'type': 'configure', 'tick': tick, 'pos': action['pos']})
                else:
                    for observed in response['rows']:
                        observed['pos'] = relative(observed['pos'])
                        observed['controller'] = relative(observed['controller'])
                        rows.append({'type': 'probe', 'label': action['label'], 'tick': tick, **observed})
            elif op == 'setblock':
                at = ' '.join(map(str, absolute(action['pos'])))
                world.command(f"/setblock {at} {action['state']}")
            elif op == 'clone':
                start, end, dest = (' '.join(map(str, absolute(action[key]))) for key in ('from', 'to', 'dest'))
                mode = 'move' if action.get('mode') == 'move' else 'normal'
                world.commands([f'/clone {start} {end} {dest} replace {mode}'])
            else:
                raise ValueError(f'unsupported tank operation: {op}')
            index += 1
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backend', choices=('core', 'horizon'))
    parser.add_argument('script', type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument('--expected', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timing', type=Path)
    parser.add_argument('--repeat', type=int, default=1)
    parser.add_argument('--executable', type=Path, default=ROOT / '.local/tank-replay-target/release/create-tank-replay')
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument('--' + key, type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    args = parser.parse_args()
    if args.repeat < 1 or (args.backend != 'core' and args.repeat != 1):
        parser.error('--repeat must be positive and is supported only by core')
    script = json.loads(args.script.read_text())
    expected_path = args.expected or ROOT / 'fixtures/tank-scripts/java' / (args.script.stem + '.jsonl')
    metadata = json.loads(expected_path.with_suffix('.metadata.json').read_text())
    if metadata['script_sha256'] != hashlib.sha256(args.script.read_bytes()).hexdigest():
        raise AssertionError('script changed since Java capture; recapture the oracle')
    if metadata['revision'] != 'ac0c444d9828da3453ae8cc65338e8de063286fb':
        raise AssertionError('unexpected Java reference revision')
    recorded_patch = expected_path.parent / 'runners' / (metadata['patch_sha256'] + '.patch')
    if not recorded_patch.exists():
        recorded_patch = ROOT / 'tools/java-tank-script.patch'
    if metadata['patch_sha256'] != hashlib.sha256(recorded_patch.read_bytes()).hexdigest():
        raise AssertionError('recorded Java runner is missing or changed; restore it or recapture the oracle')
    started = time.perf_counter()
    core_timing = None
    if args.backend == 'core':
        result = subprocess.run([str(args.executable), str(args.script), '--repeat', str(args.repeat)],
                                text=True, capture_output=True, check=True)
        actual = [json.loads(line) for line in result.stdout.splitlines()]
        core_timing = json.loads(result.stderr.strip().splitlines()[-1])
    else:
        if any(getattr(args, key) is None for key in ('ctl', 'client', 'resources')):
            parser.error('horizon requires --ctl, --client and --resources')
        actual = horizon(args, script)
    elapsed = time.perf_counter() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in actual))
    compare(actual, read_jsonl(expected_path))
    timing = {'backend': args.backend, 'script': args.script.name, 'seconds': elapsed,
              'records': len(actual), 'repetitions': args.repeat, 'core': core_timing,
              'java_revision': metadata['revision'], 'script_sha256': metadata['script_sha256'],
              'java_patch_sha256': metadata['patch_sha256'],
              'runtime': str(args.client) if args.backend == 'horizon' else str(args.executable)}
    if args.timing:
        args.timing.parent.mkdir(parents=True, exist_ok=True)
        args.timing.write_text(json.dumps(timing, indent=2) + '\n')
    print(json.dumps(timing), flush=True)


if __name__ == '__main__':
    main()
