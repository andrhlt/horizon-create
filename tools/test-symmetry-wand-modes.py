#!/usr/bin/env python3
"""Exercise Java-derived multi-plane targets, settings UI, costs, mining and reopen."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')
ui = import_module('test-worldshaper-screen')
mining = import_module('test-symmetry-wand-break')
WAND = 'create:wand_of_symmetry'


def configure(host, actor, player, mode, orientation):
    host.command(f'/tp {player} 10.5 170 25.5')
    mp.until('configuration position',lambda:actor.call('state')['player']['position']==[10.5,170.0,25.5])
    actor.call('select',WAND)
    mp.until('wand selected on server',lambda:'wand_of_symmetry' in host.command(f'/data get entity {player} SelectedItem'))
    actor.call('look',0,-90)
    actor.call('key','shift','down')
    try:
        mp.until('actual crouching pose',lambda:actor.call('state')['player']['sneaking'])
        # Keep Shift down through four network ticks, as the Worldshaper UI rig does.
        actor.call('wait',4)
        actor.call('mouse','right','click')
        mp.until('settings screen',lambda:actor.call('state')['screen']=='mod')
    except RuntimeError:
        print('editor failure',actor.call('state'),host.command(f'/data get entity {player} SelectedItem'),flush=True)
        raise
    finally:
        actor.call('key','shift','up')
    names=['Single Plane','Double Plane','Triple Plane']
    desired=1 if mode < 2 else 2
    current=mp.until('mode selector',lambda:next((b['label'].split(': ',1)[1] for b in actor.call('screen')['buttons'] if b['label'].startswith('Mirror Type:')),None))
    delta=desired-names.index(current)
    if delta:
        actor.call('scroll-at',*ui.widget(actor,'Mirror Type:'),delta)
        mp.until('chosen mode',lambda:any(b['label']==f'Mirror Type: {names[desired]}' for b in actor.call('screen')['buttons']))
    current=next(b['label'].split(': ',1)[1] for b in actor.call('screen')['buttons'] if b['label'].startswith('Orientation:'))
    current=int(current in ('YZ','Diagonal'))
    if current!=orientation:
        actor.call('scroll-at',*ui.widget(actor,'Orientation:'),orientation-current)
    actor.call('click-at',*ui.widget(actor,'Confirm'))
    kind='cross_plane' if mode<2 else 'triple_plane'
    mp.until('saved configuration',lambda:all(part in host.command(f'/data get entity {player} SelectedItem') for part in (kind,f'orientation_index: {orientation}')))
    mp.until('settings closed',lambda:actor.call('state')['screen']=='playing')
    mp.until('sneak released',lambda:not actor.call('state')['player']['sneaking'])
    actor.call('look',45 if orientation else 0,0);actor.call('wait',4)
    actor.call('interact',10,169,22,'up')
    mp.until('enabled configured origin',lambda:all(part in host.command(f'/data get entity {player} SelectedItem') for part in (kind,f'orientation_index: {orientation}','position: [10.0d, 170.0d, 22.0d]','"create:symmetry_wand_enable": 1b')))


def run(args, scratch):
    rows = list(csv.DictReader((ROOT / 'fixtures/symmetry_wand_modes-java.csv').open()))
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, 'SymmetryModes', render=not args.lan,
                                                    pack=args.pack, env={'HORIZON_NO_AUDIO': '1'}))
        actor, player = host, '@s'
        port = None
        if args.lan:
            port = host.call('lan', 'open', '0', 'commands', 'force')['port']
            player = 'SymmetryModes'
            actor = sessions.enter_context(mp.joined_client(args, scratch, f'127.0.0.1:{port}', player,
                render=True, scenario='symmetry-modes', pack=args.pack, env={'HORIZON_NO_AUDIO':'1'}))
            mp.until('guest joined', lambda: any(g['name'] == player and g['placed'] for g in host.call('lan','status')['guests']))
        host.commands((f'/gamemode survival {player}', '/fill 3 169 14 18 169 30 minecraft:stone',
                       f'/tp {player} 10.5 170 25.5',
                       f'/item replace entity {player} hotbar.0 with {WAND}[minecraft:custom_data={{marker:17}}]',
                       f'/effect give {player} minecraft:haste 240 8 true', '/tick unfreeze'))
        mp.until('wand arrived', lambda: mp.count(actor, WAND) == 1)
        actor.call('select', WAND)
        # Shift-use is the ordinary Java configuration entry point.
        actor.call('look', 0, -90)
        actor.call('key','shift','down'); actor.call('wait',4)
        actor.call('mouse','right','click')
        mp.until('wand editor', lambda: actor.call('state')['screen'] == 'mod')
        actor.call('key','shift','up')
        mp.until('wand controls', lambda: any(b['label'].startswith('Mirror Type:') for b in actor.call('screen')['buttons']))
        actor.call('screenshot', ROOT / ('.local/symmetry-settings-lan.png' if args.lan else '.local/symmetry-settings.png'))
        actor.call('scroll-at', *ui.widget(actor, 'Mirror Type:'), 1)
        mp.until('double-plane control',lambda:any(b['label']=='Mirror Type: Double Plane' for b in actor.call('screen')['buttons']))
        actor.call('scroll-at', *ui.widget(actor, 'Orientation:'), 1)
        actor.call('click-at', *ui.widget(actor, 'Confirm'))
        mp.until('authoritative double-plane setting', lambda: all(part in host.command(f'/data get entity {player} SelectedItem') for part in ('cross_plane','orientation_index: 1','marker: 17')))
        actor.call('look', 45, 0); actor.call('wait',4)
        actor.call('interact',10,169,22,'up')
        mp.until('origin stored', lambda: 'position: [10.0d, 170.0d, 22.0d]' in host.command(f'/data get entity {player} SelectedItem'))
        # The oracle's source offset is (2,1,3), translated to this origin.
        for mode, kind, orientation in ((0,'cross_plane',0),(1,'cross_plane',1),(2,'triple_plane',0)):
            configure(host,actor,player,mode,orientation)
            targets = [(10+int(r['x']),169+int(r['y']),22+int(r['z'])) for r in rows if int(r['mode']) == mode]
            for blocked, supply in ((False, 16), (True, 16), (False, 2)):
                host.commands(('/fill 3 170 14 18 173 30 minecraft:air',
                    f'/tp {player} 12.5 170 27.5',
                    f'/item replace entity {player} hotbar.1 with minecraft:stone {supply}'))
                if blocked:
                    host.command('/setblock ' + ' '.join(map(str, targets[0])) + ' minecraft:bedrock')
                mp.until('stone arrived', lambda: mp.count(actor,'minecraft:stone') == supply)
                actor.call('select','minecraft:stone'); actor.call('interact',12,169,25,'up')
                mp.until('source placed',lambda: host.call('block',12,170,25)['block']=='minecraft:stone')
                copies = min(len(targets) - int(blocked), supply - 1)
                placed_targets = [target for i,target in enumerate(targets) if not (blocked and i==0)][:copies]
                for i, target in enumerate(targets):
                    expected = 'minecraft:bedrock' if blocked and i == 0 else ('minecraft:stone' if target in placed_targets else 'minecraft:air')
                    mp.until(f'mode {mode} target {target}', lambda target=target,expected=expected: host.call('block',*target)['block']==expected)
                mp.until('exact survival cost', lambda: mp.count(actor,'minecraft:stone') == supply-1-copies)
                host.command(f'/item replace entity {player} hotbar.2 with minecraft:iron_pickaxe')
                mp.until('pick arrived',lambda: mp.count(actor,'minecraft:iron_pickaxe')==1)
                actor.call('select','minecraft:iron_pickaxe')
                before = mining.total_cobble(host,actor)
                actor.call('break',12,170,25,'--timeout',20)
                for i,target in enumerate(targets):
                    expected='minecraft:bedrock' if blocked and i==0 else 'minecraft:air'
                    mp.until('mirrored mining',lambda target=target,expected=expected: host.call('block',*target)['block']==expected)
                mp.until('mining wear',lambda: mining.damage(host,player)==1+copies)
                mp.until('mining loot',lambda: mining.total_cobble(host,actor)==before+1+copies)
                print(f'mode={mode} blocked={blocked} supply={supply}: {copies} copies, costs, loot and wear passed',flush=True)
        # Asymmetric states catch the diagonal rotation/mirror order, beyond stone geometry.
        host.command(f'/gamemode creative {player}')
        for mode,kind,orientation in ((0,'cross_plane',0),(1,'cross_plane',1),(2,'triple_plane',0)):
            configure(host,actor,player,mode,orientation)
            host.commands(('/fill 3 170 14 18 173 30 minecraft:air',
                f'/tp {player} 12.5 170 27.5',
                f'/item replace entity {player} hotbar.1 with minecraft:oak_stairs'))
            mp.until('stairs arrived',lambda:mp.count(actor,'minecraft:oak_stairs')==1)
            actor.call('select','minecraft:oak_stairs'); actor.call('look',180,0); actor.call('wait',4)
            actor.call('interact',12,169,25,'up')
            mp.until('north-facing source stairs',lambda:'facing=north' in host.call('block',12,170,25)['state'])
            for row in (r for r in rows if int(r['mode'])==mode):
                target=(10+int(row['x']),169+int(row['y']),22+int(row['z']))
                mp.until('Java stair transform',lambda target=target,row=row: all(
                    part in host.call('block',*target)['state'] for part in (f"facing={row['facing']}",f"shape={row['shape']}")))
            print(f'mode={mode}: Java stair state transforms passed',flush=True)
        host.command(f'/gamemode survival {player}')
        # Static/instantaneous family: before/after save of disabled and enabled settings.
        actor.call('select',WAND); actor.call('look',0,-90); actor.call('use-item')
        mp.until('disabled',lambda:'"create:symmetry_wand_enable": 0b' in host.command(f'/data get entity {player} SelectedItem'))
        def reopen(actor):
            if args.lan:
                actor.call('quit')
                mp.until('guest disconnected',lambda:not any(g['name']==player and g['placed'] for g in host.call('lan','status')['guests']))
            host.restart()
            if args.lan:
                port=host.call('lan','open','0','commands','force')['port']
                actor=sessions.enter_context(mp.joined_client(args,scratch,f'127.0.0.1:{port}',player,
                    render=True,scenario='symmetry-modes-rejoin',pack=args.pack,env={'HORIZON_NO_AUDIO':'1'}))
                mp.until('guest rejoined',lambda:any(g['name']==player and g['placed'] for g in host.call('lan','status')['guests']))
            # LAN force mode follows the Creative host when reconnecting.
            host.call('command',f'/gamemode survival {player}')
            mp.until('saved wand arrived',lambda:mp.count(actor,WAND)==1)
            actor.call('select',WAND)
            mp.until('saved wand selected',lambda:'wand_of_symmetry' in host.command(f'/data get entity {player} SelectedItem'))
            return actor

        before=host.command(f'/data get entity {player} SelectedItem')
        actor=reopen(actor)
        assert host.command(f'/data get entity {player} SelectedItem') == before
        host.command(f'/tp {player} 10.5 170 25.5')
        mp.until('activation reach',lambda:actor.call('state')['player']['position']==[10.5,170.0,25.5])
        actor.call('look',0,0); actor.call('interact',10,169,22,'up')
        mp.until('enabled',lambda:'"create:symmetry_wand_enable": 1b' in host.command(f'/data get entity {player} SelectedItem'))
        before=host.command(f'/data get entity {player} SelectedItem')
        actor=reopen(actor)
        assert host.command(f'/data get entity {player} SelectedItem') == before
        host.commands(('/fill 3 170 14 18 173 30 minecraft:air',
                       f'/tp {player} 12.5 170 27.5',
                       f'/item replace entity {player} hotbar.1 with minecraft:stone 16'))
        mp.until('post-reopen supplies',lambda:mp.count(actor,'minecraft:stone')==16)
        actor.call('select','minecraft:stone');actor.call('interact',12,169,25,'up')
        mp.until('saved triple-plane operation',lambda:mp.count(actor,'minecraft:stone')==8)
        print('disabled/enabled origin and settings persisted and resumed mirroring',flush=True)



if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('ctl','client','resources'):
        parser.add_argument(name,type=lambda value:Path(value).resolve())
    parser.add_argument('--pack',type=lambda value:Path(value).resolve())
    parser.add_argument('--lan',action='store_true')
    with TemporaryDirectory(prefix='hc-symmetry-modes-') as scratch:
        run(parser.parse_args(),Path(scratch))
