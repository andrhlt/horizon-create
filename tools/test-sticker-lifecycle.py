#!/usr/bin/env python3
"""Exercise Sticker client/LAN lifecycle convergence; not Java packet-timing parity."""
import argparse
from contextlib import ExitStack
import gzip
import hashlib
from importlib import import_module
import json
import os
from pathlib import Path
from shutil import copy2, rmtree
import struct
import tempfile
import zlib

from fixture_world import ROOT

mp = import_module('test-multiplayer')
POS = (9, 95, -9)
SOURCE = '9 95 -10'
OUT = ROOT / '.local/sticker-completion/lifecycle'
ENV = {'CREATE_STICKER_TRACE': '1', 'CREATE_STICKER_TEST': '1', 'HORIZON_NO_AUDIO': '1'}
ONE = 1065353216


def ticks(client):
    rows = []
    path = client.socket.parent / 'ctl.log'
    if not path.exists():
        return rows
    prefix = f'CREATE_STICKER_TICK '
    location = '[9, 95, -9] '
    for line in path.read_text(errors='replace').splitlines(keepends=True):
        if not line.endswith('\n'):
            continue
        if not line.startswith(prefix) or location not in line:
            continue
        time, value = line[len(prefix):].split(location, 1)
        previous, current, target, events, extended, attached = value.split()
        rows.append({'time': int(time), 'previous': int(previous), 'value': int(current),
                     'target': int(target), 'events': int(events),
                     'extended': extended == 'true', 'attached': attached == 'true'})
    return rows


def endpoint(client, extended, start=0):
    expected = ONE if extended else 0
    def ready():
        rows = ticks(client)
        if len(rows) <= start:
            return None
        row = rows[-1]
        return rows[start:] if row['extended'] == extended and all(row[key] == expected for key in ('previous', 'value', 'target')) else None
    return mp.until(f'{client.socket.parent.name} endpoint extended={extended}', ready)


def record(receipts, name, client, extended, start=0, *, initialized=False):
    rows = endpoint(client, extended, start)
    if initialized:
        expected = ONE if extended else 0
        assert rows[0]['value'] == expected and rows[0]['target'] == expected, (name, rows[:3])
    (OUT / f'{name}.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    receipts.append({'case': name, 'extended': extended, 'ticks': len(rows),
                     'initialized_at_endpoint': initialized, 'events': [row['events'] for row in rows if row['events']]})
    return rows


def present(client, extended):
    value = client.call('block', *POS)
    return value.get('loaded') and value.get('block') == 'create:sticker' and f'extended={str(extended).lower()}' in value['state']


def locate(command, name):
    command(f'gamemode creative {name}')
    command(f'tp {name} 9.5 95 -5.5')


def duplicate(command, clients, value, receipts):
    starts = [len(ticks(client)) for client in clients]
    command(f'data merge block 9 95 -9 {{StickerLifecycleProbe:{value}}}')
    for client, start in zip(clients, starts):
        def received():
            rows = ticks(client)[start:]
            return rows if any(row['events'] & 4 for row in rows) else None
        rows = mp.until(f'{client.socket.parent.name} unchanged-target update {value}', received)
        assert all(row['value'] == ONE and row['target'] == ONE for row in rows), rows
        assert not any(row['events'] & 3 for row in rows), rows
        name = f'notification-{value}-{client.socket.parent.name}'
        (OUT / f'{name}.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        receipts.append({'case': name, 'notification_received': True, 'no_attach_detach': True})


def saved_runtime_absent(home):
    paths = list(home.rglob('*.mca'))
    assert paths, 'No saved Anvil regions to inspect'
    chunks = 0
    for path in paths:
        region = path.read_bytes()
        for index in range(1024):
            entry = region[index * 4:index * 4 + 4]
            offset = int.from_bytes(entry[:3], 'big') * 4096
            if not offset:
                continue
            length = struct.unpack_from('>I', region, offset)[0]
            kind = region[offset + 4]
            data = region[offset + 5:offset + 4 + length]
            if kind == 2:
                data = zlib.decompress(data)
            elif kind == 1:
                data = gzip.decompress(data)
            else:
                assert kind == 3, (path, kind)
            assert b'CreateStickerAnimation' not in data, ('Client piston runtime serialized', path)
            chunks += 1
    assert chunks > 0
    return {'regions': len(paths), 'chunks': chunks, 'client_animation_marker_absent': True}


def run(args, scratch):
    receipts = []
    with ExitStack() as stack:
        address, command = stack.enter_context(mp.dedicated(args, scratch, scenario='sticker-lifecycle'))
        alice = stack.enter_context(mp.joined_client(args, scratch / 'first', address, 'StickerHost', scenario='sticker-lifecycle', env=ENV))
        locate(command, 'StickerHost')
        mp.until('host loads experiment chunk', lambda: alice.call('block', *POS).get('loaded'))
        command('fill 5 94 -13 13 94 -3 minecraft:stone')
        command('setblock 9 95 -9 create:sticker[facing=up,extended=true]')
        command('setblock 9 96 -9 minecraft:stone')
        mp.until('host initial extended Sticker', lambda: present(alice, True))
        record(receipts, 'host-initial-extended', alice, True, initialized=True)
        start = len(ticks(alice))
        command(f'setblock {SOURCE} minecraft:redstone_block')
        record(receipts, 'host-first-retract', alice, False, start)
        command(f'setblock {SOURCE} minecraft:air')
        bob = stack.enter_context(mp.joined_client(args, scratch / 'late', address, 'StickerGuest', scenario='sticker-lifecycle', env=ENV))
        locate(command, 'StickerGuest')
        mp.until('late guest current retracted state', lambda: present(bob, False))
        record(receipts, 'late-guest-retracted', bob, False, initialized=True)
        clients = [alice, bob]
        for extended in (True, False, True):
            starts = [len(ticks(client)) for client in clients]
            command(f'setblock {SOURCE} minecraft:redstone_block')
            for client, start in zip(clients, starts):
                mp.until('replicated Sticker state', lambda client=client: present(client, extended))
                rows = record(receipts, f'pulse-{len(receipts)}-{client.socket.parent.name}', client, extended, start)
                assert any(row['events'] & (1 if extended else 2) for row in rows), rows
            command(f'setblock {SOURCE} minecraft:air')
            for client in clients:
                mp.until('falling edge preserves extension', lambda client=client: present(client, extended) and 'powered=false' in client.call('block', *POS)['state'])
        for client in clients:
            mp.until('settled endpoint before duplicate packet probes', lambda client=client: len(rows := ticks(client)) >= 4 and all(row['events'] == 0 and row['value'] == ONE and row['target'] == ONE for row in rows[-4:]))
        duplicate(command, clients, 1, receipts)
        duplicate(command, clients, 2, receipts)
        command('data remove block 9 95 -9 StickerLifecycleProbe')
        # Keep the guest watching while the host genuinely unloads and reloads its chunk.
        command('tp StickerHost 1033.5 95 1015.5')
        mp.until('host unloads Sticker chunk', lambda: not alice.call('block', *POS).get('loaded'), 20)
        before = len(ticks(alice))
        locate(command, 'StickerHost')
        mp.until('host reloads extended Sticker chunk', lambda: present(alice, True))
        record(receipts, 'host-chunk-reload', alice, True, before, initialized=True)
        # A new client process with the same player identity reconnects to the same server.
        bob.call('quit')
        mp.until('guest quits', lambda: not bob.socket.exists(), 10)
        bob2 = stack.enter_context(mp.joined_client(args, scratch / 'rejoin', address, 'StickerGuest', scenario='sticker-lifecycle-rejoin', env=ENV))
        locate(command, 'StickerGuest')
        mp.until('rejoining guest saved extended state', lambda: present(bob2, True))
        record(receipts, 'guest-reconnect', bob2, True, initialized=True)
    copy2(ROOT / '.local/sticker-lifecycle-server.log', OUT / 'server-first.log')
    receipts.append({'case': 'saved-world', **saved_runtime_absent(scratch / 'server')})
    # The helper installs packs in a new directory. Clear only that disposable
    # installation so it can reopen the same saved server world and player data.
    rmtree(scratch / 'server/horizon-mods')
    with ExitStack() as stack:
        address, command = stack.enter_context(mp.dedicated(args, scratch, scenario='sticker-lifecycle-restart'))
        for name in ('StickerHost', 'StickerGuest'):
            client = stack.enter_context(mp.joined_client(args, scratch / 'restarted', address, name, scenario='sticker-lifecycle-restart', env=ENV))
            locate(command, name)
            mp.until('restarted server saved Sticker state', lambda client=client: present(client, True))
            record(receipts, f'world-restart-{name}', client, True, initialized=True)
    pack_hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in scratch.rglob('create.hmod') if path.parent.name == 'horizon-mods'}
    assert len(pack_hashes) == 1, ('Content pack changed between lifecycle phases', pack_hashes)
    (OUT / 'summary.json').write_text(json.dumps({'client': str(args.client), 'resources': str(args.resources), 'pack_sha256': next(iter(pack_hashes)), 'headless': True, 'scope': 'Horizon endpoint initialization, replicated transitions, notifications and persistence; not Java packet-delivery tick parity', 'checks': receipts}, indent=2) + '\n')
    print('Two headless clients passed Sticker initialization, pulses, unchanged-target notifications, late join, chunk reload, reconnect and saved-world restart; client animation was not serialized.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument(key, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    os.environ.update(ENV)
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sl-') as tmp:
        run(args, Path(tmp))


if __name__ == '__main__':
    main()
