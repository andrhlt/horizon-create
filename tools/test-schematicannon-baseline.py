#!/usr/bin/env python3
"""Bounded Schematicannon survival, safety, controls, LAN and reopen checks."""
import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from shutil import copy2
import json
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')
CANNON = (4, 100, 16)
SUPPLY = (4, 100, 17)
TEMPLATE = 'create:cannon_baseline'


def data(world, pos=CANNON, field=''):
    return world.command(f'/data get block {" ".join(map(str, pos))} {field}'.rstrip())


def step(world, count=1):
    target = world.clock() + count
    world.command(f'/tick step {count}')
    mp.until('frozen server steps', lambda: world.clock() == target)


def snapshot(world, pos=CANNON, field=''):
    raw = data(world, pos, field).partition('block data: ')[2]
    raw = re.sub(r'([,{])\s*([A-Za-z_][A-Za-z0-9_]*):', r'\1"\2":', raw)
    raw = re.sub(r'\[[BIL];', '[', raw)
    raw = re.sub(r'(-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)[bBsSlLfFdD](?=\s*[,}\]])', r'\1', raw)
    return json.loads(raw)


def widget(actor, label):
    buttons = actor.call('screen')['buttons']
    found = [button for button in buttons if button['label'] == label]
    assert len(found) == 1, (label, buttons)
    b = found[0]
    return b['x'] + b['w']/2, b['y'] + b['h']/2


def use_cannon(actor):
    actor.call('look-at', 4.5, 100.6, 16.5)
    mp.until('cannon under cursor', lambda: (actor.call('looking-at').get('block') or {}).get('pos') == list(CANNON))
    actor.call('mouse', 'right', 'click')


def open_screen(actor):
    use_cannon(actor)
    mp.until('Schematicannon menu', lambda: actor.call('state')['screen'] == 'container')
    mp.until('Schematicannon controls', lambda: any(
        b['label'] == 'Start' for b in actor.call('screen')['buttons']))


def click(actor, label):
    actor.call('click-at', *widget(actor, label))


def setup(world):
    world.commands((
        '/fill 2 99 13 17 99 19 minecraft:smooth_stone',
        '/setblock 10 100 10 minecraft:stone',
        '/setblock 11 100 10 minecraft:oak_slab[type=double]',
        '/setblock 12 100 10 minecraft:chest',
        '/item replace block 12 100 10 container.0 with minecraft:diamond 7',
        '/fill 13 100 10 15 100 10 minecraft:stone',
        '/setblock 10 104 10 minecraft:structure_block[mode=save]',
        f'/data merge block 10 104 10 {{name:"{TEMPLATE}",mode:"SAVE",posX:0,posY:-4,posZ:0,sizeX:6,sizeY:1,sizeZ:1,ignoreEntities:1b}}',
        '/setblock 11 104 10 minecraft:redstone_block',
        '/setblock 4 100 16 create:schematicannon',
        '/setblock 4 100 17 minecraft:chest',
        '/item replace block 4 100 17 container.0 with minecraft:oak_slab 1',
        '/item replace block 4 100 17 container.1 with minecraft:chest 1',
        '/item replace block 4 100 17 container.2 with minecraft:stone 4',
        '/setblock 10 100 16 minecraft:stone',
        '/setblock 13 100 16 minecraft:bedrock',
        '/setblock 14 100 16 minecraft:chest',
        '/item replace block 14 100 16 container.0 with minecraft:copper_ingot 5',
    ))


def equip(world, player, item):
    world.command(f'/item replace entity {player} weapon.mainhand with {item}')


def verify(args, scratch):
    with ExitStack() as sessions:
        world_name = 'CannonBaselineLAN' if args.lan else 'CannonBaseline'
        exported = scratch / 'cannon_baseline.nbt'
        host = sessions.enter_context(fixture_world(args, world_name, render=not args.lan,
            env={'CREATE_TEST_SCHEMATIC_CAPTURE': str(exported)}))
        setup(host)
        # Redstone Structure Block SAVE is memory-only in Java/Horizon. Seed the
        # existing file through the APP-2092 production capture/export backend.
        host.call('create-test-schematic-capture', 10,100,10,15,100,10)
        game_dir = Path(host._launch[host._launch.index('--game-dir') + 1])
        saved = game_dir / f'saves/{world_name}/generated/create/structures/cannon_baseline.nbt'
        saved.parent.mkdir(parents=True, exist_ok=True)
        copy2(exported, saved)
        actor, player = host, '@s'
        if args.lan:
            port = host.call('lan', 'open', '0', 'commands', 'force')['port']
            actor = sessions.enter_context(mp.joined_client(args, scratch, f'127.0.0.1:{port}', 'CannonGuest', render=True, scenario='cannon-baseline'))
            player = 'CannonGuest'
            mp.until('placed guest', lambda: any(g['name'] == player and g['placed'] for g in host.call('lan', 'status')['guests']))
        host.commands((f'/tp {player} 4.5 100 14.5', f'/gamemode survival {player}'))
        mp.until('survival actor position', lambda: actor.call('state')['player']['position'] == [4.5,100.0,14.5])
        # Real player fuel insertion; the input stack loses exactly one item.
        equip(host, player, 'minecraft:gunpowder 2')
        mp.until('held gunpowder', lambda: (actor.call('inventory')['held'] or {}).get('item') == 'minecraft:gunpowder')
        use_cannon(actor)
        mp.until('one inserted gunpowder', lambda: 'minecraft:gunpowder' in data(host, field='Items'))
        mp.until('one retained gunpowder', lambda: mp.count(actor, 'minecraft:gunpowder') == 1)
        equip(host, player, 'minecraft:air')
        mp.until('empty hand', lambda: actor.call('inventory')['held'] is None)
        open_screen(actor)
        click(actor, 'Skip missing')
        mp.until('missing-material pause selected', lambda: 'skip_missing: 0' in data(host))
        actor.call('key', 'esc', 'tap')
        if not args.lan:
            idle = snapshot(host)
            host.restart()
            assert snapshot(host) == idle, (idle, snapshot(host))
            print('Idle reopen retained cannon options and ammo inventory.')
        blueprint = f'create:schematic[minecraft:custom_data={{Template:"{TEMPLATE}",Anchor:[I;10,100,16]}}]'
        assert actor.call('state')['gamemode'] == 'survival'
        equip(host, player, blueprint)
        mp.until('held schematic', lambda: (actor.call('inventory')['held'] or {}).get('item') == 'create:schematic')
        use_cannon(actor)
        mp.until('schematic inserted', lambda: 'create:schematic' in data(host, field='Items'))
        mp.until('schematic removed from hand', lambda: actor.call('inventory')['held'] is None)
        step(host, 2)
        assert 'Status: "missingBlock"' in data(host), data(host)
        assert 'RemainingFuel: 400' in data(host), data(host)
        open_screen(actor)
        actor.call('screenshot', ROOT / ('.local/cannon-missing-lan.png' if args.lan else '.local/cannon-missing-solo.png'))
        actor.call('key', 'esc', 'tap')
        before = data(host, SUPPLY, 'Items')
        assert 'count: 1' in before and 'minecraft:oak_slab' in before, before
        assert 'count: 4' in before and 'minecraft:stone' in before, before
        step(host, 3)
        assert data(host, SUPPLY, 'Items') == before
        print('Existing stone skipped; one slab paused atomically without spending materials or a shot.')
        # Supply exactly enough slabs, then pause an actual in-flight shot.
        host.command('/item replace block 4 100 17 container.0 with minecraft:oak_slab 2')
        step(host)
        assert 'TicksLeft:' in data(host), data(host)
        assert 'RemainingFuel: 399' in data(host), data(host)
        assert 'minecraft:oak_slab' not in data(host, SUPPLY, 'Items')
        open_screen(actor)
        click(actor, 'Pause')
        mp.until('explicit paused state', lambda: 'Status: "paused"' in data(host))
        actor.call('key', 'esc', 'tap')
        fuel_after_reopen = 399
        needs_resume = True
        if not args.lan:
            open_screen(actor)
            click(actor, 'Start')
            mp.until('active printer before save', lambda: 'State: "RUNNING"' in data(host))
            actor.call('key', 'esc', 'tap')
            active = snapshot(host)
            saved_tick = host.clock()
            host.restart()
            elapsed = host.clock() - saved_tick
            reopened = snapshot(host)
            # Startup runs the server before freezing. Permit legitimate job
            # progress and verify conservation, rather than requiring zero ticks.
            fuel_after_reopen = reopened['RemainingFuel']
            assert 397 <= fuel_after_reopen <= 399, reopened
            assert reopened['Options'] == active['Options']
            if 'Queue' in reopened:
                assert reopened['Queue'] == active['Queue']
                assert reopened['Cursor'] >= active['Cursor']
                assert reopened['Items'] == active['Items']
            else:
                assert reopened['Status'] == 'finished' and fuel_after_reopen == 397, reopened
            remaining = {item['id']: item['count'] for item in snapshot(host, SUPPLY, 'Items')}
            assert remaining.get('minecraft:oak_slab', 0) == 0, remaining
            assert remaining.get('minecraft:chest', 0) == 1 - int(fuel_after_reopen <= 398), remaining
            assert remaining.get('minecraft:stone', 0) == 4 - int(fuel_after_reopen <= 397), remaining
            needs_resume = reopened['State'] == 'RUNNING'
            if needs_resume:
                open_screen(actor)
                click(actor, 'Pause')
                mp.until('paused after active reopen', lambda: 'Status: "paused"' in data(host))
                actor.call('key', 'esc', 'tap')
            print(f'Active reopen retained the plan and exact material/ammo conservation; startup advanced {elapsed} game ticks.')
        step(host, 25)
        assert host.call('block', 11,100,16)['state'] == 'minecraft:oak_slab[type=double,waterlogged=false]'
        assert f'RemainingFuel: {fuel_after_reopen}' in data(host), data(host)
        if fuel_after_reopen == 399:
            assert host.call('block',12,100,16)['block'] == 'minecraft:air'
        if needs_resume:
            open_screen(actor)
            click(actor, 'Start')
            mp.until('resumed state', lambda: 'State: "RUNNING"' in data(host))
            actor.call('key', 'esc', 'tap')
        step(host, 65)
        final = data(host)
        assert 'Status: "finished"' in final and 'RemainingFuel: 397' in final, final
        assert 'create:empty_schematic' in final and 'id: "create:schematic"' not in final, final
        assert host.call('block',13,100,16)['block'] == 'minecraft:bedrock'
        assert host.call('block',15,100,16)['block'] == 'minecraft:stone'
        assert 'minecraft:diamond' not in data(host, (12,100,16))
        assert 'minecraft:copper_ingot' in data(host,(14,100,16)) and 'count: 5' in data(host,(14,100,16))
        supply = data(host, SUPPLY, 'Items')
        assert 'minecraft:chest' not in supply and 'count: 3' in supply and 'minecraft:stone' in supply, supply
        if args.lan:
            for x, expected in ((11,'minecraft:oak_slab'),(12,'minecraft:chest'),(13,'minecraft:bedrock'),(14,'minecraft:chest'),(15,'minecraft:stone')):
                mp.until('guest build convergence', lambda x=x, expected=expected: actor.call('block',x,100,16)['block'] == expected)
            print('Guest inserted fuel/schematic and paused/resumed the build; host and guest converged.')
        else:
            saved_final = snapshot(host)
            saved_supply = snapshot(host, SUPPLY, 'Items')
            host.restart()
            assert snapshot(host) == saved_final
            assert snapshot(host, SUPPLY, 'Items') == saved_supply
            step(host, 25)
            assert 'RemainingFuel: 397' in data(host)
            print('Completed reopen did not replay shots, duplicate blocks or consume additional inputs.')
        print('Survival build used 2 slabs, 1 chest, 1 stone and 3/400 shots; bedrock and stocked target chest survived, source diamonds were not copied.')
        # Out-of-range blueprint is rejected without consuming any supply or fuel.
        host.commands(('/setblock 4 100 16 minecraft:air',
            '/setblock 4 100 16 create:schematicannon',
            f'/data merge block 4 100 16 {{State:"RUNNING",Items:[{{Slot:0b,id:"create:schematic",count:1,components:{{"minecraft:custom_data":{{Template:"{TEMPLATE}",Anchor:[I;260,100,16]}}}}}}]}}'))
        step(host)
        assert 'targetOutsideRange' in data(host) and 'create:schematic' in data(host)
        assert data(host, SUPPLY, 'Items') == supply
        print('Exact 256-block anchor limit rejected the blueprint and retained supplies.')
        host.commands(('/setblock 4 100 16 minecraft:air',
            '/setblock 4 100 16 create:schematicannon',
            '/setblock 15 100 16 minecraft:air',
            f'/data merge block 4 100 16 {{State:"RUNNING",Items:[{{Slot:0b,id:"create:schematic",count:1,components:{{"minecraft:custom_data":{{Template:"{TEMPLATE}",Anchor:[I;10,100,16]}}}}}}]}}'))
        step(host)
        assert 'noGunpowder' in data(host), data(host)
        assert data(host, SUPPLY, 'Items') == supply
        host.command('/item replace block 4 100 17 container.3 with minecraft:gunpowder 1')
        step(host, 35)
        assert host.call('block',15,100,16)['block'] == 'minecraft:stone'
        assert 'RemainingFuel: 399' in data(host) and 'finished' in data(host), data(host)
        assert 'minecraft:gunpowder' not in data(host, SUPPLY, 'Items')
        print('Empty ammo paused without consuming material; adjacent gunpowder resumed one shot.')
        # Keep explicit air in the plan when changing replacement mode mid-job.
        host.commands((
            '/setblock 11 104 10 minecraft:air',
            '/setblock 11 100 10 minecraft:air',
            '/data merge block 10 104 10 {name:"create:cannon_clear",sizeX:2}',
            '/setblock 11 104 10 minecraft:redstone_block',
            '/setblock 4 100 16 minecraft:air',
            '/setblock 4 100 16 create:schematicannon',
            '/setblock 10 100 16 minecraft:air',
            '/setblock 11 100 16 minecraft:stone',
            '/data merge block 4 100 16 {State:"RUNNING",RemainingFuel:400,Items:[{Slot:0b,id:"create:schematic",count:1,components:{"minecraft:custom_data":{Template:"create:cannon_clear",Anchor:[I;10,100,16]}}}]}',
        ))
        step(host)
        open_screen(actor)
        click(actor, 'Replace mode')
        mp.until('clear-and-replace selected', lambda: 'replace_mode: 3' in data(host))
        actor.call('key', 'esc', 'tap')
        step(host, 35)
        assert host.call('block',10,100,16)['block'] == 'minecraft:stone'
        assert host.call('block',11,100,16)['block'] == 'minecraft:air'
        assert 'RemainingFuel: 398' in data(host) and 'finished' in data(host), data(host)
        assert snapshot(host, SUPPLY, 'Items') == [{'count': 1, 'Slot': 2, 'id': 'minecraft:stone'}]
        print('Switching replacement mode during a build retained and cleared the queued air target.')



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl','client','resources'):
        parser.add_argument(name, type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument('--lan', action='store_true')
    args = parser.parse_args()
    with TemporaryDirectory(prefix='hc-cannon-baseline-') as tmp:
        verify(args, Path(tmp))
