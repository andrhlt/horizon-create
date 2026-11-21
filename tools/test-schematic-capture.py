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
                args, 'SchematicCapture', render=True, pack=args.pack, env={
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
                '/item replace entity @s weapon.mainhand with create:schematic_and_quill',
            ))
            # Reject malformed and overflowing selections without creating a
            # partial export or disturbing the existing world contents.
            for invalid in (
                ('create-test-schematic-capture', 0, 100, 0),
                ('create-test-schematic-capture', 'bad', 100, 0, 0, 100, 0),
                ('create-test-schematic-capture', -2147483648, 100, 0,
                 2147483647, 100, 0),
            ):
                try:
                    control.call(*invalid)
                except RuntimeError:
                    pass
                else:
                    raise AssertionError(f'invalid capture selection was accepted: {invalid}')
                assert not output.exists(), output
            assert control.call('getblock', 0, 100, 0)['block'] == 'minecraft:stone'
            assert control.call('inventory')['held']['item'] == 'create:schematic_and_quill'
            control.call('create-test-schematic-capture', 2, 100, 1, 0, 100, 0)
            assert control.call('inventory')['held']['item'] == 'create:schematic_and_quill'
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
            # A saved schematic remains readable from the world's structure
            # directory after an ordinary server save and reopen.
            control.restart()
            control.command('/place template minecraft:capture_test 10 100 10')
            placed = control.call('getblock', 10, 100, 10)
            assert placed['block'] == 'minecraft:stone', placed
            assert control.call('getblock', 11, 100, 10)['block'].startswith('minecraft:oak_stairs[')
            assert control.call('getblock', 10, 100, 11)['block'].startswith('minecraft:chest[')
            control.commands((
                '/fill 19 99 19 23 99 23 minecraft:stone',
                '/setblock 20 100 20 minecraft:stone',
                '/setblock 21 100 20 minecraft:chest[facing=north]',
                '/data merge block 21 100 20 {CustomName:\'"quill chest"\'}',
                '/setblock 22 100 20 minecraft:structure_void',
                '/setblock 22 100 21 minecraft:stone',
                '/item replace entity @s weapon.mainhand with create:schematic_and_quill',
                '/tp @s 20.5 100 22.5',
            ))
            for _ in range(2):
                control.call('look-at', 20.5, 100.5, 20.5)
                control.call('interact', 20, 100, 20, 'up')
                control.call('look-at', 22.5, 100.5, 21.5)
                control.call('interact', 22, 100, 21, 'up')
                mp.until('Quill export item', lambda:
                         control.call('inventory')['counts'].get('create:schematic', 0) >= _ + 1)
            inventory = control.call('inventory')
            assert inventory['held']['item'] == 'create:schematic_and_quill', inventory
            assert inventory['counts'].get('create:schematic_and_quill', 0) == 1, inventory
            assert inventory['counts'].get('create:schematic', 0) == 2, inventory
            structure_dir = game_dir / 'saves/SchematicCapture/generated/create/structures'
            exported = sorted(structure_dir.rglob('schematic*.nbt'))
            assert [path.name for path in exported] == ['schematic.nbt', 'schematic_2.nbt'], exported
            control.command('/item replace entity @s weapon.mainhand with create:schematic_and_quill[minecraft:custom_name="Quill_Export"]')
            control.call('interact', 20, 100, 20, 'up')
            control.call('interact', 22, 100, 21, 'up')
            mp.until('anvil-named Quill export item', lambda:
                     control.call('inventory')['counts'].get('create:schematic', 0) == 3)
            assert len(list(structure_dir.rglob('quill_export.nbt'))) == 1
            named_inventory = control.call('inventory')
            assert named_inventory['counts'].get('create:schematic_and_quill', 0) == 1
            assert named_inventory['held']['item'] == 'create:schematic_and_quill'
            # An unsafe anvil name cannot escape the player-scoped template directory.
            control.commands((
                '/item replace entity @s weapon.mainhand with create:schematic_and_quill[minecraft:custom_name="../escape"]',
            ))
            control.call('interact', 20, 100, 20, 'up')
            control.call('interact', 22, 100, 21, 'up')
            unsafe_inventory = control.call('inventory')
            assert unsafe_inventory['counts'].get('create:schematic', 0) == 3, unsafe_inventory
            assert not list(game_dir.rglob('escape.nbt'))
            relative = exported[0].relative_to(structure_dir).with_suffix('')
            template = 'create:' + str(relative).replace('\\', '/')
            control.commands(('/setblock 32 100 30 minecraft:granite',))
            control.restart()
            control.command(f'/place template {template} 30 100 30')
            assert control.call('getblock', 30, 100, 30)['block'] == 'minecraft:stone'
            assert control.call('getblock', 31, 100, 30)['block'].startswith('minecraft:chest[')
            assert control.call('getblock', 32, 100, 30)['block'] == 'minecraft:air'
            placed_name = control.command('/data get block 31 100 30 CustomName')
            assert 'quill chest' in placed_name, placed_name
            # The Schematic Table accepts and saves template-backed schematics,
            # then moves a valid loaded item from input to output.
            control.commands((
                '/fill 39 99 19 41 99 23 minecraft:stone',
                '/setblock 40 100 20 create:schematic_table',
                '/item replace entity @s weapon.mainhand with minecraft:stone',
                '/tp @s 40.5 100 22.5',
            ))
            control.call('look-at', 40.5, 100.5, 20.5)
            control.call('interact', 40, 100, 20, 'up')
            mp.until('Schematic Table menu', lambda: control.call('state')['screen'] == 'container')
            control.command('/give @s minecraft:stone 1')
            menu_slots = control.call('menu')['slots']
            stone_source = next(entry['slot'] for entry in menu_slots
                                if (entry.get('stack') or {}).get('item') == 'minecraft:stone')
            control.call('click-slot', stone_source)
            control.call('click-slot', 300)
            mp.until('rejected Table item to stay carried', lambda:
                     (control.call('menu').get('carried') or {}).get('item') == 'minecraft:stone')
            control.call('click-slot', stone_source)
            source = next(entry['slot'] for entry in control.call('menu')['slots']
                          if (entry.get('stack') or {}).get('item') == 'create:schematic')
            control.call('click-slot', source)
            control.call('click-slot', 300)
            mp.until('Schematic Table input', lambda: any(
                entry['slot'] == 300 and (entry.get('stack') or {}).get('item') == 'create:schematic'
                for entry in control.call('menu')['slots']))
            control.command('/save-all')
            control.restart()
            control.command('/tp @s 40.5 100 22.5')
            control.call('look-at', 40.5, 100.5, 20.5)
            control.call('interact', 40, 100, 20, 'up')
            mp.until('Schematic Table input after reopen', lambda: any(
                entry['slot'] == 300 and (entry.get('stack') or {}).get('item') == 'create:schematic'
                for entry in control.call('menu')['slots']))
            load = mp.until('Schematic Table Load Template button', lambda: next(
                (widget for widget in control.call('ui')['widgets']
                 if widget.get('label') == 'Load Template' and widget.get('enabled')), None))
            control.call('click', load['id'])
            mp.until('Schematic Table loaded output', lambda: any(
                entry['slot'] == 301 and (entry.get('stack') or {}).get('item') == 'create:schematic'
                for entry in control.call('menu')['slots']))
            control.restart()
            control.command('/tp @s 40.5 100 22.5')
            control.call('look-at', 40.5, 100.5, 20.5)
            control.call('interact', 40, 100, 20, 'up')
            mp.until('Schematic Table output after reopen', lambda: any(
                entry['slot'] == 301 and (entry.get('stack') or {}).get('item') == 'create:schematic'
                for entry in control.call('menu')['slots']))
            table = control.call('menu')['slots']
            assert not any(entry['slot'] == 300 and entry['stack'] for entry in table), table
            if args.lan:
                port = control.call('lan', 'open', '0', 'commands')['port']
                guest = sessions.enter_context(mp.joined_client(
                    args, Path(tmp), f'127.0.0.1:{port}', 'SchematicTableGuest',
                    scenario='schematic-table-guest', pack=args.pack,
                    env={'HORIZON_NO_AUDIO': '1'},
                ))
                mp.until('Schematic Table guest to join', lambda: any(
                    player['name'] == 'SchematicTableGuest' and player['placed']
                    for player in control.call('lan', 'status')['guests']))
                control.commands((
                    '/item replace entity SchematicTableGuest weapon.mainhand with minecraft:stone',
                    '/tp SchematicTableGuest 40.5 100 22.5',
                ))
                guest.call('look-at', 40.5, 100.5, 20.5)
                guest.call('interact', 40, 100, 20, 'up')
                mp.until('guest Schematic Table menu', lambda: guest.call('state')['screen'] == 'container')
                mp.until('guest sees Table output', lambda: any(
                    entry['slot'] == 301 and (entry.get('stack') or {}).get('item') == 'create:schematic'
                    for entry in guest.call('menu')['slots']))
                guest.call('close')
                # Repeat the export as the guest to prove the server captures
                # the guest's selected corners and returns a usable schematic.
                control.command('/item replace entity SchematicTableGuest weapon.mainhand with create:schematic_and_quill')
                control.command('/tp SchematicTableGuest 20.5 100 22.5')
                guest.call('interact', 20, 100, 20, 'up')
                guest.call('interact', 22, 100, 20, 'up')
                mp.until('guest Quill export item', lambda:
                         guest.call('inventory')['counts'].get('create:schematic', 0) == 1)
                assert guest.call('inventory')['held']['item'] == 'create:schematic_and_quill'
                guest_export = [path for path in structure_dir.rglob('schematic.nbt')
                                if path.parent.name == 'schematictableguest']
                assert len(guest_export) == 1, guest_export
                guest.call('quit')
                mp.until('Schematic Table guest to leave', lambda: not any(
                    player['name'] == 'SchematicTableGuest'
                    for player in control.call('lan', 'status')['guests']))
            else:
                control.call('click-slot', 301)
                control.call('click-slot', 0)
                control.call('close')
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
                    port = port or control.call('lan', 'open', '0', 'commands')['port']
                    guest = sessions.enter_context(mp.joined_client(
                        args, Path(tmp), f'127.0.0.1:{port}', 'SchematicGuest',
                        scenario='schematic-java-import', pack=args.pack,
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
