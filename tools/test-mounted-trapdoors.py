#!/usr/bin/env python3
"""Replay player clicks on the two mounted Train Trapdoor variants."""
import argparse
import csv
from contextlib import ExitStack
from tempfile import TemporaryDirectory
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

train = import_module("test-simple-train")
mp = import_module("test-multiplayer")
ENV = {"HORIZON_NO_AUDIO": "1", "HORIZON_CREATE_TEST_AUDIO": "1", "HORIZON_CREATE_ELEVATOR_TRACE": "1"}


def heard(actor):
    log = actor.socket.parent / 'ctl.log'
    text = log.read_text() if log.exists() else ''
    result = []
    for line in text.splitlines():
        if 'CREATE_ELEVATOR_PLAYBACK minecraft:block.wooden_trapdoor.' not in line:
            continue
        fields = line.split('CREATE_ELEVATOR_PLAYBACK ', 1)[1].split(',')
        sound, category = fields[:2]
        volume, pitch = map(float, fields[-2:])
        if category != '4' or abs(volume - .3) > 1e-6 or not .9 <= pitch <= 1.0:
            raise AssertionError(f'unexpected trapdoor sound {fields}')
        result.append(sound.rsplit('.', 1)[-1])
    return result



def mounted_cells(host):
    x, y, z = train.X + 3, train.Y + 3, train.Z
    host.commands((
        f'/setblock {x} {y} {z} minecraft:chest',
        f'/setblock {x} {y} {z - 1} create:train_trapdoor[facing=north,half=bottom]',
        f'/setblock {x} {y} {z + 1} create:framed_glass_trapdoor[facing=north,half=bottom]',
        f'/summon minecraft:marker {x + .5} {y - 1} {z + .5} '
        '{CreateSuperGlue:1b,From:[-0.5d,0d,-1.5d],To:[0.5d,2d,1.5d]}',
    ))


def mouse_at(host, world_point):
    host.call("look-at", *world_point)
    host.call("script", script="mouse right down\nwait 2\nmouse right up\nwait 2\n")


def run(args):
    with (ROOT / "fixtures/mounted-trapdoors-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    scenario = "mounted-trapdoors-lan" if args.multiplayer else "mounted-trapdoors"
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, scenario, train.STRUCTURE, render=True,
                                   pack=args.pack, env=ENV))
        train.setup(host, before_glue=mounted_cells, take_controls=False)
        actor, who = host, '@s'
        if args.multiplayer:
            who = 'TrapdoorGuest'
            port = host.call('lan', 'open', 0, 'commands', 'force')['port']
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix='hc-mounted-trapdoors-')))
            actor = stack.enter_context(mp.joined_client(args, scratch, f'127.0.0.1:{port}', who,
                                       render=True, scenario=scenario, pack=args.pack,
                                       env=ENV))
            mp.until('guest to join', lambda: any(g['name'] == who and g['placed']
                                                   for g in host.call('lan', 'status')['guests']))
            host.command(f'/gamemode survival {who}')
            host.command(f'/tp @s {train.X - 3} {train.Y} {train.Z + 4}')
        host.commands((
            f"/attribute {who} minecraft:gravity base set 0",
            f"/item replace entity {who} hotbar.0 with minecraft:air",
        ))
        actor.call("key", "1", "tap")
        differences = []
        for row in rows:
            x, y, z = (int(row[k]) for k in ("x", "y", "z"))
            side = -1 if z < 0 else 1
            wx, wy, wz = train.X + x + 1, train.Y + y + 1, train.Z + z
            target = f'CreateTrain.Blocks[{{Pos:[I;{x},{y},{z}]}}].BlockState.Properties'
            if row["click"] == "0":
                host.command(f"/tp {who} {wx + .5} {wy} {wz + .5 + side * 1.8}")
                actor.call("wait", 6)
            else:
                target_y = wy + (.5 if row["click"] == "2" else .09)
                mouse_at(actor, (wx + .5, target_y, wz + .5))
            actual = host.command(f"/data get entity {train.ENTITY} {target}")
            expected = [f'{field}: "{row[field]}"' for field in ("open", "facing", "half")]
            if not all(field in actual for field in expected):
                differences.append((row, actual))
        assert not differences, differences
        # The empty space above a closed trapdoor is not part of its target.
        host.command(f'/tp {who} {train.X + 3.5} {train.Y + 3} {train.Z - 3} 0 20')
        actor.call('wait', 5)
        mouse_at(actor, (train.X + 3.5, train.Y + 3.8, train.Z - .5))
        north = 'CreateTrain.Blocks[{Pos:[I;2,2,-1]}].BlockState.Properties.open'
        if '"false"' not in host.command(f'/data get entity {train.ENTITY} {north}'):
            raise AssertionError('Click above the closed trapdoor toggled it')
        for listener in ([host, actor] if args.multiplayer else [host]):
            listener.call('wait', 5)
            sounds = heard(listener)
            if sounds != ['open', 'close', 'open', 'close']:
                raise AssertionError(f'Unexpected trapdoor sounds: {sounds}')
        if not args.multiplayer:
            # Reopen a save made before trapdoor targeting proxies existed.
            for z in (-1, 1):
                host.command(f'/kill @e[type=minecraft:interaction,nbt={{CreateTrainTrapdoorPos:[I;2,2,{z}]}}]')
            host.restart()
            host.step_to(host.clock() + 1)
            selector = '@e[type=minecraft:interaction,nbt={CreateTrainTrapdoorPos:[I;2,2,-1]},limit=1]'
            if 'entity data:' not in host.command(f'/data get entity {selector}'):
                raise AssertionError('Reload did not restore missing trapdoor proxies')
            host.command(f'/tp @s {train.X + 3.5} {train.Y + 3} {train.Z - 3.0} 0 20')
            host.call('wait', 5)
            mouse_at(host, (train.X + 3.5, train.Y + 3.09, train.Z - .5))
            if '"true"' not in host.command(f'/data get entity {train.ENTITY} {north}'):
                raise AssertionError('Restored trapdoor proxy did not accept a click')
        # Disassembling the carriage must remove its targeting proxies.
        selector = '@e[type=minecraft:interaction,nbt={CreateTrainTrapdoorPos:[I;2,2,-1]},limit=1]'
        if 'entity data:' not in host.command(f'/data get entity {selector}'):
            raise AssertionError('Mounted trapdoor proxy missing before disassembly')
        sx, sy, sz = train.STATION
        host.command(f'/tp @s {sx + .5} {sy} {sz + 2.5} 180 20')
        host.call('wait', 3)
        host.call('interact', *train.STATION, 'up')
        host.call('wait', 4)
        host.call('click-button', 'Disassemble Train')
        host.step_to(host.clock() + 1)
        host.call('wait', 3)
        if 'entity data:' in host.command(f'/data get entity {selector}'):
            raise AssertionError('Disassembly left a mounted trapdoor proxy')
    print(f"Mounted trapdoors matched all {len(rows)} Java observations.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    run(parser.parse_args())
