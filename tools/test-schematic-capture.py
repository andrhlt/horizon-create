#!/usr/bin/env python3
"""Verify the partial Schematic and Quill capture backend in an isolated world."""
import argparse
from contextlib import ExitStack
import gzip
from importlib import import_module
import io
from pathlib import Path
import shutil
import struct
import tempfile

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")


def read_nbt(path):
    stream = io.BytesIO(gzip.decompress(path.read_bytes()))
    def number(fmt):
        return struct.unpack('>' + fmt, stream.read(struct.calcsize(fmt)))[0]
    def text():
        return stream.read(number('H')).decode('utf-8')
    def payload(kind):
        if kind in (1, 2, 3, 4, 5, 6):
            return number({1:'b', 2:'h', 3:'i', 4:'q', 5:'f', 6:'d'}[kind])
        if kind == 7:
            return stream.read(number('i'))
        if kind == 8:
            return text()
        if kind == 9:
            subtype, length = number('B'), number('i')
            return [payload(subtype) for _ in range(length)]
        if kind == 10:
            result = {}
            while (subtype := number('B')):
                name = text()
                result[name] = payload(subtype)
            return result
        if kind in (11, 12):
            return [number('i' if kind == 11 else 'q') for _ in range(number('i'))]
        raise ValueError(f'Unexpected NBT tag {kind}')
    assert number('B') == 10
    text()
    root = payload(10)
    assert not stream.read()
    return root


def run(args):
    with tempfile.TemporaryDirectory(prefix='create-capture-') as tmp:
        output = Path(tmp) / 'capture.nbt'
        with ExitStack() as sessions:
            control = sessions.enter_context(fixture_world(
                args, 'SchematicCapture', pack=args.pack, env={
                    'CREATE_TEST_SCHEMATIC_CAPTURE': str(output), 'HORIZON_NO_AUDIO': '1',
                },
            ))
            control.commands((
                '/fill 0 100 0 2 100 1 minecraft:air',
                '/setblock 0 100 0 minecraft:stone',
                '/setblock 1 100 0 minecraft:oak_stairs[facing=east,half=bottom,shape=straight]',
                '/setblock 2 100 0 minecraft:structure_void',
                '/setblock 0 100 1 minecraft:chest[facing=north]',
                '/data merge block 0 100 1 {CustomName:\'"capture chest"\'}',
            ))
            control.call('create-test-schematic-capture', 2, 100, 1, 0, 100, 0)
            tag = read_nbt(output)
            assert tag['size'] == [3, 1, 2], tag
            blocks = {tuple(b['pos']): b for b in tag['blocks']}
            states = {pos: tag['palette'][block['state']] for pos, block in blocks.items()}
            assert states[(0, 0, 0)]['id'] == 'minecraft:stone', states
            assert states[(1, 0, 0)]['id'] == 'minecraft:oak_stairs', states
            assert states[(1, 0, 0)]['properties']['facing'] == 'east', states
            assert states[(2, 0, 0)]['id'] == 'minecraft:air', states
            assert (1, 0, 1) not in blocks and (2, 0, 1) not in blocks, blocks
            assert blocks[(0, 0, 1)]['nbt']['id'] == 'minecraft:chest', blocks
            assert 'capture chest' in blocks[(0, 0, 1)]['nbt']['CustomName'], blocks
            game_dir = Path(control._launch[control._launch.index('--game-dir') + 1])
            dest = game_dir / 'saves/SchematicCapture/generated/minecraft/structures/capture_test.nbt'
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(output, dest)
            control.command('/place template minecraft:capture_test 10 100 10')
            placed = control.call('getblock', 10, 100, 10)
            assert placed['block'] == 'minecraft:stone', placed
            assert control.call('getblock', 11, 100, 10)['block'].startswith('minecraft:oak_stairs[')
            assert control.call('getblock', 10, 100, 11)['block'].startswith('minecraft:chest[')
            if args.java:
                original = ROOT / 'fixtures' / 'schematic_capture-java.nbt'
                java = read_nbt(original)
                shutil.copyfile(original, dest.with_name('java_capture_test.nbt'))
                control.commands((
                    '/setblock 18 100 10 minecraft:granite',
                    '/setblock 18 100 11 minecraft:granite',
                ))
                placement = control.command('/place template minecraft:java_capture_test 16 100 10')
                assert 'Loaded template' in placement, placement
                for block in java['blocks']:
                    x, y, z = block['pos']
                    state = java['palette'][block['state']]
                    properties = state.get('Properties', {})
                    details = ','.join(f'{name}={value}' for name, value in properties.items())
                    block_id = state['Name'] + (f'[{details}]' if details else '')
                    actual = control.command(f'/execute if block {x + 16} {y + 100} {z + 10} {block_id}')
                    assert 'Test passed' in actual, (block, state, actual)
                omitted = control.command('/execute if block 18 100 11 minecraft:granite')
                assert 'Test passed' in omitted, omitted
                name = control.command('/data get block 16 100 11 CustomName')
                assert name.endswith('"capture chest"'), name
                print('Original Java schematic loaded with every placed block and property, including its named chest.')
                if args.lan:
                    port = control.call('lan', 'open', '0', 'commands')['port']
                    guest = sessions.enter_context(mp.joined_client(
                        args, Path(tmp), f'127.0.0.1:{port}', 'SchematicGuest',
                        render=True, scenario='schematic-java-import', pack=args.pack,
                        env={'HORIZON_NO_AUDIO': '1'},
                    ))
                    mp.until("the guest to join", lambda: any(
                        player['name'] == 'SchematicGuest' and player['placed']
                        for player in control.call('lan', 'status')['guests']))
                    control.commands((
                        '/setblock 16 99 14 minecraft:stone',
                        '/tp SchematicGuest 16.5 100 14.5',
                    ))
                    mp.until("the Java chest to reach the guest",
                             lambda: guest.call('block', 16, 100, 11)['block'] == 'minecraft:chest')
                    guest.call('look-at', 16.5, 100.5, 11.5)
                    guest.call('interact', 16, 100, 11, 'south')
                    mp.until("the guest to open the chest",
                             lambda: guest.call('state')['screen'] == 'container')
                    screen = guest.call('screen')
                    assert 'capture chest' in str(screen), screen
                    print('The LAN guest opened the imported chest under its Java name.')
    print('Schematic capture wrote and reloaded the selected structure.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('ctl', 'client', 'resources'):
        parser.add_argument(argument, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--java', action='store_true')
    parser.add_argument('--lan', action='store_true')
    args = parser.parse_args()
    if args.lan and not args.java:
        parser.error('--lan requires --java')
    run(args)
