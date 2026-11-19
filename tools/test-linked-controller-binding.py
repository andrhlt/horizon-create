#!/usr/bin/env python3
"""Bind a handheld controller to a Redstone Link and inspect its saved frequencies."""
import argparse
from contextlib import ExitStack
from tempfile import TemporaryDirectory
import re
from importlib import import_module
from pathlib import Path
from fixture_world import ROOT, fixture_world

probe = import_module('test-nozzle')
mp = import_module('test-multiplayer')
AT = (5, 170, 20)


def run(args):
    env = {'HORIZON_NO_AUDIO': '1'}
    with ExitStack() as scope:
        world = scope.enter_context(fixture_world(args, 'LinkedControllerBinding', render=not args.lan,
                                                  pack=args.pack, env=env))
        actor, player = world, '@s'
        other = None
        if args.lan:
            port = world.call('lan', 'open', '0', 'commands', 'force')['port']
            player = 'ControllerGuest'
            scratch = Path(scope.enter_context(TemporaryDirectory(prefix='hc-controller-guest-')))
            actor = scope.enter_context(mp.joined_client(args, scratch, f'127.0.0.1:{port}', player,
                                                        render=True, scenario='controller-binding',
                                                        pack=args.pack, env=env))
            mp.until('guest joined', lambda: any(g['name'] == player and g['placed']
                     for g in world.call('lan', 'status')['guests']))
            if args.mounted:
                other_dir = Path(scope.enter_context(TemporaryDirectory(prefix='hc-lectern-other-')))
                other = scope.enter_context(mp.joined_client(args, other_dir, f'127.0.0.1:{port}', 'OtherGuest',
                                                            render=True, scenario='lectern-other',
                                                            pack=args.pack, env=env))
                mp.until('second guest joined', lambda: any(g['name'] == 'OtherGuest' and g['placed']
                         for g in world.call('lan', 'status')['guests']))
        world.commands((
            '/fill 0 169 16 12 169 28 minecraft:stone',
            f'/tp {player} 5.5 170 23.5',
            f'/clear {player}',
            '/setblock 5 170 20 create:redstone_link[facing=up,receiver=false,powered=false]',
            '/data merge block 5 170 20 {FrequencyFirst:{id:"minecraft:diamond",count:1},FrequencyLast:{id:"minecraft:emerald",count:1}}',
            f'/item replace entity {player} hotbar.0 with create:linked_controller[minecraft:custom_data={{marker:17}}]',
            f'/item replace entity {player} hotbar.1 with minecraft:stone',
        ))
        actor.call('select', 'create:linked_controller')
        probe.aim(actor, (5.5, 170.2, 20.5), AT)
        actor.call('mouse', 'right', 'click')
        actor.call('wait', 4)
        actor.call('key', 'w', 'down')
        actor.call('wait', 2)
        actor.call('key', 'w', 'up')
        def bound():
            data = world.command(f'/data get entity {player} SelectedItem')
            return all(value in data for value in ('linked_controller_items', 'diamond', 'emerald', 'marker'))
        mp.until('controller frequencies saved', bound)
        data = world.command(f'/data get entity {player} SelectedItem')
        print('first binding:', data, flush=True)
        assert re.search(r'slot:\s*0', data) and re.search(r'slot:\s*1', data), data
        world.command('/data merge block 5 170 20 {FrequencyFirst:{id:"minecraft:gold_ingot",count:1},FrequencyLast:{id:"minecraft:iron_ingot",count:1}}')
        probe.aim(actor, (5.5, 170.2, 20.5), AT)
        actor.call('mouse', 'right', 'click')
        actor.call('wait', 4)
        actor.call('key', 'a', 'down')
        actor.call('wait', 2)
        actor.call('key', 'a', 'up')
        def second_bound():
            data = world.command(f'/data get entity {player} SelectedItem')
            return all(value in data for value in ('diamond', 'emerald', 'gold_ingot', 'iron_ingot'))
        mp.until('other button preserves first binding', second_bound)
        data = world.command(f'/data get entity {player} SelectedItem')
        print('second binding:', data, flush=True)
        assert re.search(r'slot:\s*4', data) and re.search(r'slot:\s*5', data), data

        if args.binding_only:
            return

        world.commands((
            '/setblock 8 170 20 create:redstone_link[facing=up,receiver=true,powered=false]',
            '/data merge block 8 170 20 {FrequencyFirst:{id:"minecraft:diamond",count:1},FrequencyLast:{id:"minecraft:emerald",count:1}}',
            '/setblock 9 170 20 minecraft:redstone_wire',
        ))
        world.step_to(world.clock() + 1)
        world.call('wait', 2)
        def receiver():
            return world.command('/data get block 8 170 20 Receive')
        def step():
            target = world.clock() + 1
            world.step_to(target)
            world.call('wait', 2)
            assert world.clock() == target, 'render wait advanced world time'
        assert receiver().endswith('0'), receiver()
        actor.call('look-at', 5.5, 220, 23.5)
        actor.call('mouse', 'right', 'click')
        actor.call('wait', 4)
        actor.call('key', 'w', 'down')
        actor.call('wait', 3)
        mp.until('immediate received strength', lambda: receiver().endswith('15'))
        assert 'power=0' in world.call('block', 9, 170, 20)['state']
        if args.timing:
            print('press before tick:', receiver(), world.call('block', 8, 170, 20)['state'], world.call('block', 9, 170, 20)['state'], flush=True)
        step()
        if args.timing:
            print('press after tick:', receiver(), world.call('block', 8, 170, 20)['state'], world.call('block', 9, 170, 20)['state'], flush=True)
        assert receiver().endswith('15'), receiver()
        wire = world.call('block', 9, 170, 20)['state']
        assert 'power=15' in wire, wire
        actor.call('key', 'w', 'up')
        actor.call('wait', 3)
        if args.timing:
            print('release before tick:', receiver(), world.call('block', 8, 170, 20)['state'], world.call('block', 9, 170, 20)['state'], flush=True)
        step()
        if args.timing:
            print('release after tick:', receiver(), world.call('block', 8, 170, 20)['state'], world.call('block', 9, 170, 20)['state'], flush=True)
        assert receiver().endswith('0'), receiver()
        wire = world.call('block', 9, 170, 20)['state']
        assert 'power=15' in wire, wire
        assert 'powered=true' in world.call('block', 8, 170, 20)['state']
        step()
        wire = world.call('block', 9, 170, 20)['state']
        if args.timing:
            print('release after second tick:', receiver(), world.call('block', 8, 170, 20)['state'], wire, flush=True)
        assert 'power=0' in wire, wire
        assert 'powered=false' in world.call('block', 8, 170, 20)['state']
        actor.call('key', 'w', 'down')
        actor.call('wait', 3)
        step()
        assert receiver().endswith('15'), receiver()
        actor.call('key', '2', 'tap')
        actor.call('wait', 5)
        step()
        assert receiver().endswith('0'), receiver()
        assert 'power=15' in world.call('block', 9, 170, 20)['state']
        step()
        assert 'power=0' in world.call('block', 9, 170, 20)['state']
        actor.call('key', 'w', 'up')
        print('receiver and wire: 0 -> 15 -> 0; changing held item stops input', flush=True)
        if args.mounted:
            world.commands((
                f'/tp {player} 5.5 170 21.5',
                '/setblock 5 170 20 minecraft:lectern[facing=north,has_book=false,powered=false]',
            ))
            actor.call('select', 'create:linked_controller')
            probe.aim(actor, (5.5, 170.7, 20.5), AT)
            actor.call('mouse', 'right', 'click')
            actor.call('wait', 5)
            mp.until('controller mounted', lambda: 'create:lectern_controller' in world.call('block', *AT)['state'])
            if args.stale:
                world.command('/data merge block 5 170 20 {User:[I;1,2,3,4]}')
            actor.call('select', 'minecraft:stone')
            probe.aim(actor, (5.5, 170.7, 20.5), AT)
            actor.call('mouse', 'right', 'click')
            actor.call('wait', 5)
            def lectern_data():
                return world.command('/data get block 5 170 20')
            mp.until('mounted user recorded', lambda: 'User:' in lectern_data())
            owner = lectern_data()
            if args.stale:
                assert '[I; 1, 2, 3, 4]' not in owner, owner
            if other:
                world.command('/tp OtherGuest 4.5 170 20.5')
                other.call('wait', 5)
                probe.aim(other, (5.5, 170.7, 20.5), AT)
                other.call('mouse', 'right', 'click')
                other.call('wait', 5)
                assert lectern_data() == owner, (owner, lectern_data())
                other.call('key', 'w', 'down')
                other.call('wait', 3)
                step()
                assert receiver().endswith('0'), receiver()
                other.call('key', 'w', 'up')
                if args.dimensions:
                    world.command('/execute in minecraft:the_nether run tp OtherGuest 0 100 0')
                    mp.until('other guest enters Nether', lambda: other.call('status').get('dimension') == 'minecraft:the_nether')
                    step()
                    assert lectern_data() == owner, (owner, lectern_data())
                    world.command('/execute in minecraft:overworld run tp OtherGuest 4.5 170 20.5')
                    mp.until('other guest returns', lambda: other.call('status').get('dimension') == 'minecraft:overworld')
                    other.call('wait', 5)
            if args.owner_dimension:
                if not args.lan:
                    raise ValueError('--owner-dimension requires --lan')
                world.command('/execute in minecraft:the_nether run tp ControllerGuest 0 100 0')
                mp.until('owner enters Nether', lambda: actor.call('status').get('dimension') == 'minecraft:the_nether')
                step()
                assert 'User:' not in lectern_data(), lectern_data()
                print('owner dimension change cleared the original Lectern', flush=True)
                return
            actor.call('key', 'w', 'down')
            mp.until('mounted input received', lambda: receiver().endswith('15'))
            step()
            assert 'power=15' in world.call('block', 9, 170, 20)['state']
            if args.mounted_disconnect:
                if not args.lan:
                    raise ValueError('--mounted-disconnect requires --lan')
                actor.call('quit')
                mp.until('mounted guest disconnected', lambda: not any(g['name'] == player and g['placed']
                         for g in world.call('lan', 'status')['guests']))
                step()
                assert 'User:' not in lectern_data(), lectern_data()
                for _ in range(28):
                    step()
                assert receiver().endswith('15'), receiver()
                step()
                assert receiver().endswith('0'), receiver()
                assert 'power=15' in world.call('block', 9, 170, 20)['state']
                step()
                assert 'power=0' in world.call('block', 9, 170, 20)['state']
                print('mounted disconnect: owner cleared, input timed out at 30 ticks', flush=True)
                return
            actor.call('key', 'w', 'up')
            actor.call('wait', 3)
            step()
            assert receiver().endswith('0'), receiver()
            step()
            assert 'power=0' in world.call('block', 9, 170, 20)['state']
            actor.call('key', 'escape', 'tap')
            mp.until('mounted user released', lambda: 'User:' not in lectern_data())
            if other:
                probe.aim(other, (5.5, 170.7, 20.5), AT)
                other.call('mouse', 'right', 'click')
                other.call('wait', 5)
                mp.until('second user acquires lectern', lambda: 'User:' in lectern_data() and lectern_data() != owner)
                other.call('key', 'w', 'down')
                mp.until('second user input received', lambda: receiver().endswith('15'))
                other.call('key', 'w', 'up')
                other.call('key', 'escape', 'tap')
                mp.until('second user released', lambda: 'User:' not in lectern_data())
            print('mounted lectern: exclusive use, input, release and exit passed', flush=True)
        if args.timeout:
            if not args.lan:
                raise ValueError('--timeout requires --lan')
            actor.call('select', 'create:linked_controller')
            actor.call('look-at', 5.5, 220, 23.5)
            actor.call('mouse', 'right', 'click')
            actor.call('wait', 4)
            actor.call('key', 'w', 'down')
            mp.until('timeout input received', lambda: receiver().endswith('15'))
            actor.call('quit')
            mp.until('guest disconnected', lambda: not any(g['name'] == player and g['placed']
                     for g in world.call('lan', 'status')['guests']))
            for _ in range(29):
                step()
            assert receiver().endswith('15'), receiver()
            step()
            assert receiver().endswith('0'), receiver()
            assert 'power=15' in world.call('block', 9, 170, 20)['state']
            step()
            assert 'power=0' in world.call('block', 9, 170, 20)['state']
            print('timeout: receive drops after 30 ticks, wire after 31', flush=True)
    print('Linked Controller binding saved both frequency stacks.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--lan', action='store_true')
    parser.add_argument('--timing', action='store_true', help='print pre- and post-tick signal samples')
    parser.add_argument('--timeout', action='store_true', help='test 30-tick expiry by disconnecting the LAN guest')
    parser.add_argument('--mounted', action='store_true', help='test Lectern user, wireless input and exit')
    parser.add_argument('--stale', action='store_true', help='seed a stale saved Lectern user')
    parser.add_argument('--mounted-disconnect', action='store_true', help='disconnect a mounted LAN user while transmitting')
    parser.add_argument('--dimensions', action='store_true', help='tick another guest in the Nether during mounted use')
    parser.add_argument('--owner-dimension', action='store_true', help='move mounted owner to another dimension')
    parser.add_argument('--binding-only', action='store_true')
    run(parser.parse_args())
