#!/usr/bin/env python3
"""Exercise attaching and detaching a Linked Controller on a vanilla lectern."""
import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

probe = import_module('test-nozzle')
mp = import_module('test-multiplayer')
toolbox = import_module('test-toolbox-crafting')
ITEM = 'create:linked_controller'
FREQUENCIES = 'create:linked_controller_items'
SOUND_TRACE = 'CREATE_LECTERN_SOUND '
AT = (5, 170, 20)
WIRE = (7, 170, 20)


def assert_signal(host, strength):
    start = host.clock()
    for step in range(1, 7):
        host.step_to(start + step)
    state = probe.state(host, WIRE)
    assert f"power={strength}" in state, state


def replay(host, actor, player):
    host.commands((
        '/fill 0 169 16 12 169 28 minecraft:stone',
        f'/tp {player} 5.5 170 23.5',
        f'/gamemode survival {player}',
        f'/clear {player}',
        '/setblock 5 170 20 minecraft:lectern[facing=east,has_book=false,powered=false]',
        '/setblock 6 170 20 minecraft:comparator[facing=west]',
        '/setblock 7 170 20 minecraft:redstone_wire',
        '/setblock 8 170 22 create:redstone_link[facing=up,receiver=false,powered=false]',
        '/data merge block 8 170 22 {FrequencyFirst:{id:"minecraft:diamond",count:1},FrequencyLast:{id:"minecraft:emerald",count:1}}',
        f'/item replace entity {player} hotbar.0 with {ITEM}[minecraft:custom_name="Fixture Controller",minecraft:custom_data={{marker:17}}]',
    ))
    mp.until('controller in inventory', lambda: mp.count(actor, ITEM) == 1)
    actor.call('select', ITEM)
    probe.aim(actor, (8.5, 170.2, 22.5), (8, 170, 22))
    actor.call('mouse', 'right', 'click')
    actor.call('wait', 4)
    actor.call('key', 'w', 'down')
    actor.call('wait', 2)
    actor.call('key', 'w', 'up')
    mp.until('frequency pair was saved to the controller',
             lambda: 'emerald' in host.command(f'/data get entity {player} SelectedItem'))
    original = next(s for s in actor.call('inventory')['hotbar'] if s.get('item') == ITEM)
    expected = {FREQUENCIES: toolbox.stack_components(original)[FREQUENCIES]}
    probe.aim(actor, (5.5, 170.7, 20.5), AT)
    actor.call('mouse', 'right', 'click')
    mp.until('controller attached', lambda: probe.state(host, AT).startswith('create:lectern_controller'))
    mounted = probe.state(host, AT)
    assert 'facing=east' in mounted and 'has_book=true' in mounted, mounted
    mp.until('controller consumed', lambda: mp.count(actor, ITEM) == 0)
    data = host.command('/data get block 5 170 20 ControllerData')
    assert 'diamond' in data and 'emerald' in data, data
    assert_signal(host, 15)

    actor.call('key', 'shift', 'down')
    try:
        actor.call('wait', 4)
        probe.aim(actor, (5.5, 170.7, 20.5), AT)
        actor.call('mouse', 'right', 'click')
        actor.call('wait', 4)
    finally:
        actor.call('key', 'shift', 'up')
    mp.until('controller detached', lambda: probe.state(host, AT).startswith('minecraft:lectern'))
    state = probe.state(host, AT)
    assert 'facing=east' in state and 'has_book=false' in state, state
    def detached_controller():
        return next((e for e in actor.call('entities', 12, 'minecraft:item')['entities']
                     if e['item']['item'] == ITEM), None)
    mp.until('controller dropped next to the lectern', detached_controller)
    drop = detached_controller()
    assert drop['pos'] == [5.75, 171.0, 20.5], drop
    assert toolbox.stack_components(drop['item']) == expected, drop
    assert mp.count(actor, ITEM) == 0
    for _ in range(24):
        if mp.count(actor, ITEM) == 1:
            break
        if entity := detached_controller():
            x, y, z = entity['pos']
            host.command(f'/tp {player} {x} {y} {z}')
        host.step_to(host.clock() + 1)
    mp.until('controller collected after the pickup delay', lambda: mp.count(actor, ITEM) == 1)
    host.command(f'/tp {player} 5.5 170 23.5')
    mp.until('player returned to test position',
             lambda: actor.call('state')['player']['position'] == [5.5, 170.0, 23.5])
    recovered = next(s for s in actor.call('inventory')['hotbar'] if s.get('item') == ITEM)
    assert toolbox.stack_components(recovered) == expected, (expected, recovered)
    assert_signal(host, 0)

    host.command('/setblock 5 170 20 minecraft:lectern[facing=west,has_book=true,powered=false]')
    mp.until('book lectern synchronized', lambda: 'has_book=true' in probe.state(actor, AT))
    actor.call('select', ITEM)
    probe.aim(actor, (5.5, 170.7, 20.5), AT)
    actor.call('mouse', 'right', 'click')
    actor.call('wait', 4)
    state = probe.state(host, AT)
    assert 'minecraft:lectern' in state and 'has_book=true' in state, state
    assert mp.count(actor, ITEM) == 1


def check_break(host, actor, player):
    host.command('/setblock 5 170 20 minecraft:lectern[facing=east,has_book=false,powered=false]')
    mp.until('empty lectern synchronized', lambda: 'has_book=false' in probe.state(actor, AT))
    original = next(s for s in actor.call('inventory')['hotbar'] if s.get('item') == ITEM)
    actor.call('select', ITEM)
    probe.aim(actor, (5.5, 170.7, 20.5), AT)
    actor.call('mouse', 'right', 'click')
    mp.until('controller mounted for mining', lambda: probe.state(host, AT).startswith('create:lectern_controller'))
    mp.until('mount to consume the controller', lambda: mp.count(actor, ITEM) == 0)
    host.command(f'/item replace entity {player} hotbar.1 with minecraft:netherite_axe')
    mp.until('axe reached the player', lambda: mp.count(actor, 'minecraft:netherite_axe') == 1)
    actor.call('select', 'minecraft:netherite_axe')
    probe.aim(actor, (5.5, 170.7, 20.5), AT)
    actor.call('mouse', 'left', 'down')
    try:
        for _ in range(100):
            host.step_to(host.clock() + 1)
            if probe.state(host, AT) == 'minecraft:air':
                break
        else:
            raise AssertionError('The axe did not break the mounted lectern.')
    finally:
        actor.call('mouse', 'left', 'up')

    def drops():
        return [e['item'] for e in actor.call('entities', 12, 'minecraft:item')['entities']]
    mp.until('lectern and controller drops', lambda:
             {drop['item'] for drop in drops()} == {ITEM, 'minecraft:lectern'})
    dropped = drops()
    assert sorted((drop['item'], drop['count']) for drop in dropped) == [
        (ITEM, 1), ('minecraft:lectern', 1)], dropped
    restored = next(drop for drop in dropped if drop['item'] == ITEM)
    assert toolbox.stack_components(restored) == {FREQUENCIES: toolbox.stack_components(original)[FREQUENCIES]}, restored
    assert_signal(host, 0)
    print('Mining dropped one vanilla lectern and one controller with the mounted frequency pairs.')


def check_clone(host, actor, player):
    host.commands((
        '/setblock 5 170 20 create:lectern_controller[facing=east,has_book=true,powered=false]',
        f'/gamemode creative {player}',
        f'/clear {player}',
    ))
    mp.until('mounted lectern reached the player',
             lambda: probe.state(actor, AT).startswith('create:lectern_controller'))
    probe.aim(actor, (5.5, 170.7, 20.5), AT)
    actor.call('mouse', 'middle', 'click')
    mp.until('pick-block returned a vanilla lectern', lambda: mp.count(actor, 'minecraft:lectern') == 1)
    assert mp.count(actor, ITEM) == 0
    print('Pick-block returned a vanilla lectern.')


def run(args):
    env = {'HORIZON_NO_AUDIO': '1'}
    if args.sounds:
        env['HORIZON_CREATE_LECTERN_TRACE'] = '1'
    with ExitStack() as scope:
        host = scope.enter_context(fixture_world(
            args, 'LecternControllerLan' if args.lan else 'LecternController',
            render=not args.lan, pack=args.pack, env=env,
        ))
        actor, player = host, '@s'
        if args.lan:
            port = host.call('lan', 'open', '0', 'commands', 'force')['port']
            player = 'LecternGuest'
            scratch = Path(scope.enter_context(TemporaryDirectory(prefix='hc-lectern-guest-')))
            actor = scope.enter_context(mp.joined_client(
                args, scratch, f'127.0.0.1:{port}', player, render=True,
                scenario='lectern-controller', pack=args.pack, env=env,
            ))
            mp.until('the guest to join', lambda: any(
                guest['name'] == player and guest['placed']
                for guest in host.call('lan', 'status')['guests']
            ))
        replay(host, actor, player)
        if args.sounds:
            log = host.socket.parent / 'ctl.log'
            def played():
                return [line.split(SOUND_TRACE)[1] for line in log.read_text().splitlines()
                        if SOUND_TRACE + 'create:controller_' in line]
            mp.until('both Lectern sound events were queued', lambda: len(played()) >= 2)
            assert played() == [
                'create:controller_put,4,5.5,170.5,20.5,1,1',
                'create:controller_take,4,5.5,170.5,20.5,1,1',
            ], played()
            print('The server queued the original attach and detach cues.')
        if args.break_drops:
            check_break(host, actor, player)
            check_clone(host, actor, player)
    print('Lectern attachment, components, comparator 15→0, detach, and book lectern passed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--lan', action='store_true')
    parser.add_argument('--break-drops', action='store_true')
    parser.add_argument('--sounds', action='store_true')
    run(parser.parse_args())
