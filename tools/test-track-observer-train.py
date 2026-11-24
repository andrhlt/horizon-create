#!/usr/bin/env python3
"""Verify train detection, cargo filtering, guest configuration, and observer persistence."""
import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

train = import_module('test-simple-train')
multiplayer = import_module('test-multiplayer')

parser = argparse.ArgumentParser()
for name in ('ctl', 'client', 'resources'):
    parser.add_argument(name, type=lambda value: Path(value).resolve())
parser.add_argument('--pack', type=Path)
cases = parser.add_mutually_exclusive_group()
cases.add_argument('--filter-accept', action='store_true')
cases.add_argument('--filter-reject', action='store_true')
parser.add_argument('--lan', action='store_true')
args = parser.parse_args()

filter_item = 'minecraft:iron_ingot'
cargo_item = 'minecraft:gold_ingot' if args.filter_reject else filter_item
scenario = 'Track-observer-train' + ('-accept' if args.filter_accept else '-reject' if args.filter_reject else '') + ('-lan' if args.lan else '')

with TemporaryDirectory(prefix='hc-track-observer-') as scratch, fixture_world(
    args, scenario, train.STRUCTURE, render=True, pack=args.pack, env={'HORIZON_NO_AUDIO': '1'},
) as world, ExitStack() as clients:
    ox, oy, oz = train.X - 5, train.Y, train.Z + 3

    def observer(control):
        control.commands((
            f'/setblock {ox} {oy} {oz} create:track_observer{{TargetTrack:[I;0,0,-3],TargetDirection:0b}}',
            f'/setblock {ox + 1} {oy} {oz} minecraft:redstone_wire',
        ))
        if args.filter_reject or (args.filter_accept and not args.lan):
            control.command(f'/data merge block {ox} {oy} {oz} {{Filter:{{id:"{filter_item}",count:1}}}}')

    def cargo(control):
        if args.filter_accept or args.filter_reject or args.lan:
            cx, cy, cz = train.X + 2, train.Y + 2, train.Z
            control.command(f'/setblock {cx} {cy} {cz} minecraft:chest')
            control.command(f'/item replace block {cx} {cy} {cz} container.0 with {cargo_item} 1')

    train.setup(world, after_station=observer, station_discovery_ticks=8,
                before_glue=cargo if args.filter_accept or args.filter_reject or args.lan else None)
    if args.filter_accept or args.filter_reject or args.lan:
        carriage = world.command(f'/data get entity {train.ENTITY} CreateTrain.Blocks')
        assert f'id: "{cargo_item}"' in carriage, f'Assembled train did not retain {cargo_item}: {carriage}'

    guest = None
    if args.lan:
        world.command('/tick unfreeze')
        address = f"127.0.0.1:{world.call('lan', 'open', '0', 'commands', 'force')['port']}"
        guest = clients.enter_context(multiplayer.joined_client(
            args, Path(scratch), address, 'TrackObsGuest', render=True,
            scenario='track-observer-filter', pack=args.pack,
            launch_timeout=120,
        ))
        guest_name = 'TrackObsGuest'
        multiplayer.until('the Track Observer guest to join', lambda: any(
            player['name'] == guest_name and player['placed']
            for player in world.call('lan', 'status')['guests']
        ))
        world.command(f'/gamemode survival {guest_name}')
        world.command(f'/item replace entity {guest_name} hotbar.0 with {filter_item} 1')
        world.command(f'/item replace entity {guest_name} hotbar.1 with minecraft:gold_ingot 1')
        world.command(f'/tp {guest_name} {ox + .5} {oy + 2.5} {oz + .5}')

        def guest_filter(item, slot, select_item=None):
            guest.call('select', select_item or item or slot)
            guest.call('look-at', ox + .5, oy + .873, oz + .5)
            guest.call('wait', 1)
            hit = guest.call('looking-at').get('block')
            assert hit and hit['pos'] == [ox, oy, oz] and hit['face'] == 'up', hit
            # Send one held-button interval in a single control script.  The
            # standalone `mouse ... click` command can be observed as two
            # server-side interactions (sample, then empty hand) on LAN.
            guest.call('script', script='mouse right down\nwait 2\nmouse right up')

            def host_filter():
                data = world.command(f'/data get block {ox} {oy} {oz}')
                matches = (f'id: "{item}"' in data) if item else (
                    'id: "minecraft:iron_ingot"' not in data
                    and 'id: "minecraft:gold_ingot"' not in data
                )
                return data if matches else False

            return multiplayer.until(f'the host observer filter to become {item or "empty"}', host_filter)

        for item, slot in ((filter_item, 1), ('minecraft:gold_ingot', 2)):
            state = guest_filter(item, slot)
            print(f'Guest set {item}; host observer data: {state}', flush=True)

        state = guest_filter(None, 3)  # An empty survival hotbar slot clears the filter.
        print(f'Guest cleared the filter; host observer data: {state}', flush=True)
        # After clearing, select the known hotbar slot explicitly; item-ID
        # selection can leave the guest hand empty after the clear dispatch.
        state = guest_filter(filter_item, 1, select_item=1)
        counts = guest.call('inventory')['counts']
        assert counts.get(filter_item) == counts.get('minecraft:gold_ingot') == 1, counts
        print(f'Guest set, changed, and cleared the filter; both held items remained. Final state: {state}', flush=True)
        world.command('/tick freeze')

    world.call('key', 'w', 'down')
    last = None
    seen = set()
    active_reopened = False
    for i in range(130):
        world.step_to(world.clock() + 1)
        state = world.call('block', ox, oy, oz)['state']
        wire = world.call('block', ox + 1, oy, oz)['state']
        active = 'powered=true' in state
        assert f'power={15 if active else 0}' in wire, (state, wire)
        if active != last:
            sample = train.sample(world)
            print(f'tick={i + 1} observer={state} wire={wire} train={sample}', flush=True)
            last = active
        if guest is not None:
            multiplayer.until('guest observer state to converge with host', lambda:
                guest.call('block', ox, oy, oz)['state'] == state
            )
        if active and not active_reopened and args.filter_accept:
            world.call('key', 'w', 'up')
            world.restart()
            state = world.call('block', ox, oy, oz)['state']
            wire = world.call('block', ox + 1, oy, oz)['state']
            saved = world.command(f'/data get block {ox} {oy} {oz}')
            assert 'powered=true' in state and 'power=15' in wire, (state, wire)
            assert 'TargetTrack: [I; 0, 0, -3]' in saved and f'id: "{filter_item}"' in saved, saved
            world.call('key', 'w', 'down')
            active_reopened = True
        seen.add(active)
    world.call('key', 'w', 'up')
    print('final train', train.sample(world), flush=True)
    if args.filter_reject:
        assert seen == {False}, seen
    else:
        assert seen == {False, True}, seen
    if args.filter_accept:
        assert active_reopened, 'The accepted cargo did not survive an active save/reopen.'

    if args.lan:
        clients.pop_all().close()
        guest = None
    if args.filter_accept or args.filter_reject or args.lan:
        world.restart()
        saved = world.command(f'/data get block {ox} {oy} {oz}')
        assert 'TargetTrack: [I; 0, 0, -3]' in saved, saved
        assert f'id: "{filter_item}"' in saved, saved
        assert 'powered=false' in world.call('block', ox, oy, oz)['state'], world.call('block', ox, oy, oz)
        print('Observer targeting and cargo filter survived idle save/reopen.', flush=True)
    print(f'Train observer filter case passed; power states observed: {sorted(seen)}.', flush=True)
