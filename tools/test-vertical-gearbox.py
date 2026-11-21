#!/usr/bin/env python3
"""Verify the original Vertical Gearbox's placement, item identity and survival recipes."""

import argparse
import csv
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world

NORMAL = 'create:gearbox'
VERTICAL = 'create:vertical_gearbox'
POSITION = (8, 102, -10)


def coords(pos):
    return ' '.join(map(str,pos))


def setup(control):
    control.commands((
        '/fill 4 100 -15 15 100 -5 minecraft:smooth_stone',
        '/fill 4 101 -15 15 107 -5 minecraft:air',
        '/gamemode survival',
    ))


def place(control, case, axis, item):
    point = (8.9, 102.5, -9.001) if case == 5 else (8.5, 102.5, -9.001)
    feet = (point[0], 101, -12.5)
    support = (8, 102, -9)
    side = 'north'
    extras = []
    if case in (2,4,6):
        support = (7, 102, -10)
        point = (7.999, 102.5, -9.5)
        feet = (11.5, 101, -9.5)
        side = 'east'
    if case in (3,5):
        extras.append('/setblock 9 102 -10 create:shaft[axis=x]')
    if case in (4,5,6):
        extras.append('/setblock 8 102 -11 create:shaft[axis=z]')
    if case == 7:
        extras.append('/setblock 8 101 -10 create:shaft[axis=y]')
    if case == 8:
        extras.extend(('/setblock 9 102 -10 create:clutch[axis=x,powered=true]',
                       '/setblock 9 103 -10 minecraft:redstone_block'))
    control.commands((
        '/fill 4 101 -15 15 107 -5 minecraft:air',
        '/clear @s',
        f'/setblock {coords(support)} minecraft:stone',
        *extras,
        f'/tp @s {coords(feet)}',
        f'/item replace entity @s hotbar.0 with {item}',
    ))
    control.call('wait',3)
    control.call('select',item)
    if case == 6:
        control.call('key','shift','down')
        control.call('wait',3)
    try:
        control.call('look-at',*point)
        control.call('wait',2)
        hit=control.call('looking-at').get('block')
        if not hit or hit['pos'] != list(support) or hit['face'] != side:
            raise RuntimeError(f'Gearbox case {case} expected the {side} of {support}, observed {hit}.')
        control.call('mouse','right','click')
        control.call('wait',3)
    finally:
        if case == 6:
            control.call('key','shift','up')
    actual=control.call('block',*POSITION)['state']
    assert actual == f'create:gearbox[axis={axis}]', (case, actual, axis)
    assert not control.call('inventory')['counts'].get(item), (case, item)
    if case == 8:
        assert control.call('block',9,102,-10)['state'] == 'create:clutch[axis=x,powered=true]'


def aim_at_gearbox(control):
    control.call('look-at',8.5,102.5,-9.5)
    control.call('wait',2)
    hit=control.call('looking-at').get('block')
    if not hit or hit['pos'] != list(POSITION):
        raise RuntimeError(f'Expected the placed Gearbox within reach, got {hit}.')


def expected_cases():
    with (ROOT / "fixtures/vertical-gearbox-java.csv").open(newline="") as source:
        reader = csv.reader(source)
        next(reader)
        cases = list(reader)
    assert len(cases) == 9
    return cases


def models(pack):
    expected = {'assets/create/models/item/vertical_gearbox.json': 'ffa001968656232b9e071819e492bec1faa0ce110e8dcd507a7ee786cc1410c1', 'assets/create/models/block/gearbox/item_vertical.json': '7d7e29d59bc56ee6179c402472b069189093d224d6ef8c0d3ebfa68a13ddfcc0'}
    with ZipFile(pack or ROOT / ".local/create.hmod") as archive:
        for name, checksum in expected.items():
            if sha256(archive.read(name)).hexdigest() != checksum:
                raise RuntimeError(f"The Vertical Gearbox model {name} differs from Java.")


def placement(args):
    models(args.pack)
    with fixture_world(args,'VerticalGearboxPlacement',render=True,pack=args.pack) as control:
        setup(control)
        for raw_case, entered, axis, item, loot, count, consumed, *_ in expected_cases():
            assert (entered, consumed, item, count) == ('true','true',loot,'1')
            place(control,int(raw_case),axis,item)
    print('Both items matched all nine original Java placements and consumed one survival item.')


def drops(args):
    expected = {}
    for _, _, axis, picked, mined, count, _, used, removed, gained in expected_cases():
        assert (picked, count, used, removed, gained) == (mined, '1', 'true', 'true', '1')
        expected[axis] = picked
    with fixture_world(args,'VerticalGearboxTools',render=True,pack=args.pack) as control:
        setup(control)
        for axis, item in sorted(expected.items()):
            control.commands((
                '/clear @s',
                '/gamemode creative',
                f'/setblock {coords(POSITION)} create:gearbox[axis={axis}]',
                '/tp @s 8.5 101 -12.5',
            ))
            control.call('wait',3)
            aim_at_gearbox(control)
            control.call('mouse','middle','click')
            control.call('wait',3)
            contents=control.call('inventory')['counts']
            assert contents.get(item)==1, ('pick',axis,item,contents)
            control.commands((
                '/clear @s',
                '/gamemode survival',
                '/item replace entity @s hotbar.0 with create:wrench',
            ))
            control.call('wait',3)
            control.call('select','create:wrench')
            control.call('key','shift','down')
            control.call('wait',4)
            try:
                aim_at_gearbox(control)
                control.call('mouse','right','click')
                control.call('wait',3)
            finally:
                control.call('key','shift','up')
            contents=control.call('inventory')['counts']
            assert control.call('block',*POSITION)['block']=='minecraft:air' and contents.get(item)==1, ('wrench', axis, contents)
            control.commands((
                '/clear @s',
                f'/setblock {coords(POSITION)} create:gearbox[axis={axis}]',
                '/item replace entity @s hotbar.0 with minecraft:iron_pickaxe',
            ))
            control.call('wait',3)
            control.call('select','minecraft:iron_pickaxe')
            control.command('/tick unfreeze')
            breaking=control.call('break',*POSITION,'--timeout',8)
            drops=control.call('entities',12,'minecraft:item')['entities']
            control.command('/tp @s 8.5 101 -9.5')
            control.call('wait',20)
            control.command('/tick freeze')
            contents=control.call('inventory')['counts']
            assert control.call('block',*POSITION)['block']=='minecraft:air' and contents.get(item)==1, ('harvest',axis,contents,breaking,drops)
    print('Creative pick, ordinary mining and survival Wrench pickup each returned the exact Java item for all three axes.')


def load(name):
    spec=spec_from_file_location(name,ROOT/'tools'/f'{name}.py')
    module=module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def craft(args):
    crafting=load('test-survival-crafting')
    with fixture_world(args,'VerticalGearboxRecipes',render=True,pack=args.pack) as control:
        setup(control)
        control.commands((
            '/setblock 8 102 -9 minecraft:crafting_table',
            '/tp @s 8.5 101 -12.5',
        ))
        for result, ingredients in (
            (NORMAL, (('create:cogwheel',(101,103,105,107)),('create:andesite_casing',(104,)))),
            (VERTICAL, (('create:cogwheel',(100,102,106,108)),('create:andesite_casing',(104,)))),
            (VERTICAL, ((NORMAL,(100,)),)),
            (NORMAL, ((VERTICAL,(100,)),)),
        ):
            control.command('/clear @s')
            control.commands(f'/item replace entity @s hotbar.{index} with {item} {len(slots)}'
                             for index,(item,slots) in enumerate(ingredients))
            control.call('wait',3)
            control.call('interact',8,102,-9,'north')
            for index,(_,slots) in enumerate(ingredients):
                crafting.distribute(control,index,slots)
            crafting.craft(control,result,1)
            control.call('close')
            control.call('wait',2)
            contents=control.call('inventory')['counts']
            leftovers={item: contents.get(item) for item,_ in ingredients if contents.get(item)}
            assert not leftovers, (result, leftovers, contents)
    print('Both original shaped Gearbox recipes and both one-to-one conversions crafted in survival.')


def verify_lan(args, scratch):
    guest_name = "VerticalGear"
    multiplayer=load('test-multiplayer')
    with fixture_world(args,'VerticalGearboxLAN',render=True,pack=args.pack) as host:
        setup(host)
        host.commands((
            '/setblock 8 102 -9 minecraft:stone',
            '/setblock 9 102 -10 create:clutch[axis=x,powered=true]',
            '/setblock 9 103 -10 minecraft:redstone_block',
            '/tp @s 12.5 101 -8.5',
        ))
        host.step_to(host.clock()+1)
        address=f"127.0.0.1:{host.call('lan','open','0','commands','force')['port']}"
        with multiplayer.joined_client(args,scratch,address,guest_name,render=True,scenario='vertical-gearbox',pack=args.pack) as guest:
            multiplayer.until('the survival guest to join', lambda: any(
                user['name']==guest_name and user['placed'] for user in host.call('lan','status')['guests']
            ))
            host.commands((
                f'/gamemode survival {guest_name}', f'/tp {guest_name} 8.5 101 -12.5',
                f'/item replace entity {guest_name} hotbar.0 with {VERTICAL}',
                f'/item replace entity {guest_name} hotbar.1 with create:wrench',
            ))
            multiplayer.until('guest to hold the original Vertical Gearbox and Wrench', lambda: (
                guest.call('state')['player']['position']==[8.5,101.0,-12.5]
                and guest.call('inventory')['counts'].get(VERTICAL)==1
                and guest.call('inventory')['counts'].get('create:wrench')==1
            ))
            guest.call('select',VERTICAL)
            guest.call('look-at',8.5,102.5,-9.001)
            guest.call('wait',2)
            hit=guest.call('looking-at').get('block')
            assert hit and hit['pos']==[8,102,-9] and hit['face']=='north',hit
            guest.call('mouse','right','click')
            multiplayer.until('both players to see the vertical gearbox beside the powered clutch',lambda:all(
                peer.call('block',*POSITION)['state']=='create:gearbox[axis=z]' for peer in (host,guest)
            ))
            multiplayer.until('one item to be consumed',lambda: guest.call('inventory')['counts'].get(VERTICAL,0)==0)
            guest.call('select','create:wrench')
            guest.call('key','shift','down')
            guest.call('wait',4)
            try:
                aim_at_gearbox(guest)
                guest.call('mouse','right','click')
                multiplayer.until('both players to see the wrench pickup',lambda:all(
                    peer.call('block',*POSITION)['block']=='minecraft:air' for peer in (host,guest)
                ))
            finally:
                guest.call('key','shift','up')
            multiplayer.until('the guest to receive the Vertical Gearbox item', lambda: guest.call('inventory')['counts'].get(VERTICAL)==1)
    print('A survival guest placed and recovered the original Vertical Gearbox beside a powered clutch. Both clients saw its Java axis.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--drops", dest="test", action="store_const", const=drops)
    group.add_argument("--craft", dest="test", action="store_const", const=craft)
    group.add_argument("--lan", action="store_true")
    parser.set_defaults(test=placement)
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-vgl-") as scratch:
            verify_lan(args, Path(scratch))
    else:
        args.test(args)


if __name__ == "__main__":
    main()
