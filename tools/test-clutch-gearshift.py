#!/usr/bin/env python3
"""Replay ordinary Clutch and Gearshift placement and Wrench interaction against Java."""

import argparse
from collections import Counter
import csv
import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world

BLOCKS = ("clutch", "gearshift")
FACES = {
    "down": (0, -1, 0), "up": (0, 1, 0), "north": (0, 0, -1), "south": (0, 0, 1),
    "west": (-1, 0, 0), "east": (1, 0, 0),
}
POSITION = (8, 104, -10)


def java_rows(test):
    with (ROOT / "fixtures" / f"clutch-gearshift-{test}-java.csv").open(newline="") as source:
        reader = csv.reader(source)
        next(reader)
        return list(reader)


def coords(point):
    return ' '.join(map(str, point))


def state(block, axis, power):
    return f'create:{block}[axis={axis},powered={power}]'


def verify_placement(args):
    expected = java_rows("placement")
    assert len(expected) == 14
    differences = []
    with fixture_world(args, 'PlainTransmissionPlacement', pack=args.pack) as control:
        control.commands((
            '/fill 4 100 -15 14 100 -5 minecraft:smooth_stone',
            '/gamemode survival',
        ))
        for block_index, case, axis, powered in expected:
            block = BLOCKS[int(block_index)]
            case = int(case)
            clear = '/fill 4 101 -15 14 107 -5 minecraft:air'
            if case == 5:
                target, support, face = (8, 101, -10), (8, 100, -10), 'up'
                feet, aim = (8.5, 103.0, -10.06), (8.5, 100.999, -9.5)
                extras = ['/setblock 8 102 -11 minecraft:stone']
            elif case == 6:
                target, support, face = (8, 102, -10), (7, 102, -10), 'east'
                feet, aim = (11.5, 101.0, -9.5), (7.999, 102.5, -9.5)
                extras = []
            else:
                target, support, face = (8, 102, -10), (8, 102, -9), 'north'
                feet, aim = (8.5, 101.0, -12.5), (8.5, 102.5, -9.001)
                extras = []
            if case in (1, 2, 3):
                extras.append('/setblock 9 102 -10 create:shaft[axis=x]')
            if case == 3:
                extras.append('/setblock 8 101 -10 create:shaft[axis=y]')
            if case == 4:
                extras.append('/setblock 7 102 -10 minecraft:redstone_block')
            control.commands((clear, f'/setblock {coords(support)} minecraft:stone', *extras, f'/tp @s {coords(feet)}',
                              f'/item replace entity @s hotbar.0 with create:{block}'))
            control.call('wait', 3)
            control.call('select', f'create:{block}')
            sneak = case in (2, 6)
            if sneak:
                control.call('key', 'shift', 'down')
                control.call('wait', 3)
            try:
                control.call('look-at', *aim)
                control.call('wait', 1)
                hit = control.call('looking-at').get('block')
                assert hit and hit['pos'] == list(support) and hit['face'] == face, (case, hit)
                control.call('mouse', 'right', 'click')
                control.call('wait', 3)
            finally:
                if sneak:
                    control.call('key', 'shift', 'up')
            actual = control.call('block', *target)['state']
            if actual != state(block, axis, powered):
                differences.append((block, case, state(block, axis, powered), actual))
    if differences:
        raise RuntimeError(f'{len(differences)} placement differences (Java, Horizon): {differences}')
    print('Both transmissions matched all 14 original Java hand placements, including placement into redstone.')

def pose(control, face):
    x, _, z = FACES[face]
    camera = (10.5, 105, -9.5) if face == 'up' else (8.5 + x * 3, 101, -9.5 + z * 3)
    control.command(f'/tp @s {coords(camera)}')
    control.call('wait', 3)


def wrench_sounds(control):
    return Counter({sound: count for sound, count in control.call('status')['heard'].items()
                    if sound.startswith('create:wrench_')})


def verify_wrench(args):
    rotation = java_rows("wrench")
    pickups = java_rows("pickup")
    sounds = {(block, action, axis, face): Counter(cue.split('|')[0] for cue in cues.split(';') if cue)
              for block, action, axis, face, cues in java_rows("wrench-audio")}
    assert len(rotation) == 36 and len(pickups) == 2
    changes = []
    audio = {'HORIZON_NO_AUDIO': '1', 'HORIZON_CREATE_TEST_AUDIO': '1'}
    with fixture_world(args, 'PlainTransmissionWrench', pack=args.pack, env=audio) as control:
        control.commands((
            '/fill 4 100 -15 14 100 -5 minecraft:smooth_stone',
            '/fill 4 101 -15 14 107 -5 minecraft:air',
            '/setblock 10 104 -10 minecraft:stone',
            '/gamemode survival',
            '/item replace entity @s hotbar.0 with create:wrench',
        ))
        control.call('wait', 3)
        control.call('select', 'create:wrench')
        for block_index, previous, face, axis, consumed in rotation:
            block = BLOCKS[int(block_index)]
            control.command(f'/setblock {coords(POSITION)} create:{block}[axis={previous},powered=false]')
            pose(control, face)
            before = wrench_sounds(control)
            control.call('interact', *POSITION, face)
            control.call('wait', 2)
            case = (block_index, 'turn', previous, face)
            heard = wrench_sounds(control) - before
            assert heard == sounds[case], (case, sounds[case], heard)
            actual = control.call('block', *POSITION)['state']
            expected = f'create:{block}[axis={axis},powered=false]'
            if consumed != 'true' or actual != expected:
                changes.append((block, previous, face, expected, actual))
        if changes:
            raise RuntimeError(f'{len(changes)} Java and Horizon Wrench changes differ: {changes[:20]}')
        for block_index, consumed, cleared, count in pickups:
            block = BLOCKS[int(block_index)]
            control.command(f'/setblock {coords(POSITION)} create:{block}[axis=x,powered=false]')
            pose(control, 'up')
            control.call('key', 'shift', 'down')
            control.call('wait', 4)
            before = wrench_sounds(control)
            try:
                control.call('look-at', 8.5, 104.999, -9.5)
                control.call('wait', 2)
                hit = control.call('looking-at').get('block')
                assert hit and hit['pos'] == list(POSITION) and hit['face'] == 'up', hit
                control.call('mouse', 'right', 'click')
                control.call('wait', 4)
            finally:
                control.call('key', 'shift', 'up')
            actual_count = control.call('inventory')['counts'].get(f'create:{block}', 0)
            actual_block = control.call('block', *POSITION)['block']
            assert (consumed, cleared, int(count), actual_block, actual_count) == ('true', 'true', 1, 'minecraft:air', 1), (block, actual_block, actual_count)
            case = (block_index, 'remove', 'x', 'up')
            heard = wrench_sounds(control) - before
            assert heard == sounds[case], (case, sounds[case], heard)
    print('Clutch and Gearshift matched all 36 Java Wrench rotations, both survival pickups, and their sound events.')


def verify_lan(args, scratch):
    spec = spec_from_file_location("multiplayer_fixture", ROOT / "tools/test-multiplayer.py")
    multiplayer = module_from_spec(spec)
    spec.loader.exec_module(multiplayer)
    guest_name = "PlainClutch"
    pos = (8, 102, -10)
    with fixture_world(args, 'PlainClutchLAN', pack=args.pack) as host:
        host.commands((
            '/fill 4 100 -14 14 100 -5 minecraft:smooth_stone',
            '/fill 4 101 -13 14 106 -6 minecraft:air',
            '/setblock 8 102 -9 minecraft:stone',
            '/setblock 7 102 -10 minecraft:redstone_block',
            '/tp @s 12.5 101 -8.5',
        ))
        host.step_to(host.clock() + 1)
        address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
        with multiplayer.joined_client(args, scratch, address, guest_name, scenario='plain-clutch', pack=args.pack) as guest:
            multiplayer.until('the survival builder to join', lambda: any(
                user['name'] == guest_name and user['placed'] for user in host.call('lan', 'status')['guests']
            ))
            host.commands((
                f'/gamemode survival {guest_name}',
                f'/tp {guest_name} 8.5 101 -12.5',
                f'/item replace entity {guest_name} hotbar.0 with create:clutch',
                f'/item replace entity {guest_name} hotbar.1 with create:wrench',
            ))
            multiplayer.until('guest to receive tool and clutch', lambda: (
                guest.call('state')['player']['position'] == [8.5, 101.0, -12.5]
                and guest.call('inventory')['counts'].get('create:clutch') == 1
                and guest.call('inventory')['counts'].get('create:wrench') == 1
            ))
            guest.call('select', 'create:clutch')
            guest.call('look-at', 8.5, 102.5, -9.001)
            guest.call('wait', 2)
            assert guest.call('looking-at')['block']['pos'] == [8, 102, -9]
            guest.call('mouse', 'right', 'click')
            multiplayer.until('both clients to see the powered clutch', lambda: all(
                peer.call('block', *pos)['state'] == 'create:clutch[axis=z,powered=true]' for peer in (host, guest)
            ))
            multiplayer.until('guest to spend one clutch', lambda: guest.call('inventory')['counts'].get('create:clutch', 0) == 0)
            guest.call('select', 'create:wrench')
            # The north face follows the clutch axis and keeps its orientation.
            guest.call('interact', *pos, 'north')
            guest.call('key', 'shift', 'down')
            guest.call('wait', 4)
            try:
                guest.call('look-at', 8.5, 102.5, -9.999)
                guest.call('wait', 2)
                assert guest.call('looking-at')['block']['pos'] == list(pos)
                guest.call('mouse', 'right', 'click')
                multiplayer.until('both clients to see the wrench pickup', lambda: all(
                    peer.call('block', *pos)['block'] == 'minecraft:air' for peer in (host, guest)
                ))
            finally:
                guest.call('key', 'shift', 'up')
            multiplayer.until('guest to receive one clutch', lambda: guest.call('inventory')['counts'].get('create:clutch') == 1)
    print('A survival guest placed a powered Clutch and picked it back up. Both clients saw the same state.')


def verify_recipes(args):
    expected = json.loads((ROOT / 'fixtures/clutch-gearshift-recipes-java.json').read_text())['recipes']
    with ZipFile(args.pack or ROOT / '.local/create.hmod') as archive:
        for block, java in expected.items():
            ingredients = [entry['item'] if 'item' in entry else f"#{entry['tag']}"
                           for entry in java['ingredients']]
            actual = json.loads(archive.read(f'data/create/recipe/crafting/kinetics/{block}.json'))
            assert actual == java | {'ingredients': ingredients}, (block, actual)
    def contents(world, pos):
        data = world.command(f'/data get block {coords(pos)} Items')
        result = {}
        for slot in re.findall(r'\{[^{}]*\bSlot:[^{}]+\}', data):
            item = re.search(r'\bid: "([^"]+)"', slot)[1]
            count = int(re.search(r'\bcount: (\d+)', slot)[1])
            result[item] = result.get(item, 0) + count
        return result

    with fixture_world(args, 'ClutchGearshiftRecipes', pack=args.pack) as world:
        world.commands((
            '/fill 4 100 -15 14 100 -5 minecraft:smooth_stone',
            '/fill 4 101 -15 14 106 -5 minecraft:air',
            '/tp @s 11.5 101 -9.5',
        ))
        for z, (block, java) in zip((-12, -7), expected.items(), strict=True):
            crafter, chest, signal = (8, 102, z), (9, 102, z), (8, 102, z - 1)
            ingredients = [entry.get('item', 'minecraft:redstone') for entry in java['ingredients']]
            world.commands((
                f'/setblock {coords(crafter)} minecraft:crafter[orientation=east_up]',
                f'/setblock {coords(chest)} minecraft:chest',
                f'/item replace block {coords(crafter)} container.6 with {ingredients[0]}',
                f'/item replace block {coords(crafter)} container.2 with {ingredients[1]}',
            ))
            for with_redstone in (False, True):
                if with_redstone:
                    world.command(f'/item replace block {coords(crafter)} container.4 with {ingredients[2]}')
                world.command(f'/setblock {coords(signal)} minecraft:redstone_block')
                start = world.clock()
                for tick in range(1, 9):
                    world.step_to(start + tick)
                world.command(f'/setblock {coords(signal)} minecraft:air')
                result = java['result']
                remaining = {} if with_redstone else dict.fromkeys(ingredients[:2], 1)
                expected_outputs = {result['id']: result['count']} if with_redstone else {}
                actual = (contents(world, crafter), contents(world, chest))
                assert actual == (remaining, expected_outputs), (block, with_redstone, actual)
    print('The headless Crafter matched both Java recipes and rejected each recipe without redstone.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--wrench", action="store_true")
    mode.add_argument("--lan", action="store_true")
    mode.add_argument("--recipes", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-pcl-") as scratch:
            verify_lan(args, Path(scratch))
    elif args.wrench:
        verify_wrench(args)
    elif args.recipes:
        verify_recipes(args)
    else:
        verify_placement(args)


if __name__ == "__main__":
    main()
