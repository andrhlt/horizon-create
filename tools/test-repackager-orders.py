#!/usr/bin/env python3
"""Check fragmented order assembly and isolation in an independent world."""
import argparse
from importlib import import_module
import json
from pathlib import Path
from fixture_world import ROOT, fixture_world

packager = import_module('test-packager-redstone')
BARREL = (7, 105, -12)
MACHINE = (8, 105, -12)
POWER = (8, 105, -11)

def put(world, slot, order, fragment, final, item):
    world.command(f'/item replace block 7 105 -12 container.{slot} with create:cardboard_package_12x12')
    meta = f'{{order_id:{order},link_index:0,is_final_link:1b,fragment_index:{fragment},is_final:{int(final)}b}}'
    world.command(f'/data modify block 7 105 -12 Items[{slot}].components."create:package_order_data" set value {meta}')
    contents = f'[{{slot:0,item:{{id:"minecraft:{item}",count:2}}}}]'
    world.command(f'/data modify block 7 105 -12 Items[{slot}].components."create:package_contents" set value {contents}')

def field(world, path):
    reply = world.command(f'/data get block 8 105 -12 {path}')
    return reply.partition(' has the following block data: ')[2]


def check_merged_package(world, reference):
    queue = 'QueuedExitingPackages'
    packet = f'{queue}[0].item_stack.components'
    assert not field(world, f'{queue}[1]'), field(world, queue)
    assert int(field(world, f'{queue}[0].count')) == reference['package_count']
    assert int(field(world, f'{packet}."create:package_order_data".order_id')) == reference['merged_order']
    contents = f'{packet}."create:package_contents"'
    for slot, (item, count) in enumerate(reference['package_contents']):
        assert json.loads(field(world, f'{contents}[{slot}].item.id')) == item
        assert int(field(world, f'{contents}[{slot}].item.count')) == count
    assert not field(world, f'{contents}[{len(reference["package_contents"])}]'), field(world, contents)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--pack', type=Path)
    args = parser.parse_args()
    reference = json.loads((ROOT / 'fixtures/repackager-orders-java.json').read_text())
    with fixture_world(args, 'RepackagerOrders', pack=args.pack) as world:
        world.commands(('/fill 5 104 -15 13 104 -9 minecraft:smooth_stone',
                        '/fill 5 105 -15 13 109 -9 minecraft:air',
                        '/setblock 7 105 -12 minecraft:barrel',
                        '/setblock 8 105 -12 create:repackager[facing=east]'))
        put(world, 0, 77, 0, False, 'iron_ingot')
        put(world, 1, 88, 0, False, 'redstone')
        world.command('/setblock 8 105 -11 minecraft:redstone_block')
        incomplete = packager.block_data(world, BARREL)
        assert all(f'order_id: {order}' in incomplete for order in reference['incomplete_orders']), incomplete
        assert 'HeldBox:' not in packager.block_data(world, MACHINE)
        assert not field(world, 'QueuedExitingPackages[0]')
        world.commands(('/setblock 8 105 -11 minecraft:air',
                        '/setblock 8 105 -12 minecraft:air',
                        '/setblock 8 105 -12 create:repackager[facing=east]'))
        put(world, 2, 77, 1, True, 'gold_ingot')
        world.command('/setblock 8 105 -11 minecraft:redstone_block')
        barrel = packager.block_data(world, BARREL)
        state = packager.block_data(world, MACHINE)
        assert f'order_id: {reference["merged_order"]}' not in barrel, barrel
        assert f'order_id: {reference["remaining_order"]}' in barrel, barrel
        assert 'QueuedExitingPackages:' in state, state
        check_merged_package(world, reference)
        print('Incomplete and unrelated orders, queued package count and ordered contents matched the Java probe.', flush=True)
        world.commands(('/setblock 8 105 -11 minecraft:air',
                        '/setblock 8 105 -12 minecraft:air',
                        '/setblock 7 105 -12 minecraft:air',
                        '/setblock 7 105 -12 minecraft:barrel',
                        '/setblock 8 105 -12 create:repackager[facing=east]'))
        put(world, 0, 99, 0, True, 'iron_ingot')
        context = '{ordered_stacks:{entries:[]},ordered_crafts:[{count:1,pattern:{entries:[{item_stack:{},count:0},{item_stack:{id:"minecraft:iron_ingot",count:1},count:1}]}}]}'
        world.command(f'/data modify block 7 105 -12 Items[0].components."create:package_order_data".order_context set value {context}')
        world.command('/setblock 8 105 -11 minecraft:redstone_block')
        state = packager.block_data(world, MACHINE)
        barrel = packager.block_data(world, BARREL)
        assert 'order_id: 99' not in barrel, barrel
        assert state.count('create:package_contents') == 2 and 'ordered_crafts:' in state and 'order_id: 99' in state, state
        assert 'slot: 1' in state, state
        print('Sparse pattern kept its original slot.', flush=True)


if __name__ == '__main__':
    main()
