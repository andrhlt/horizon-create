#!/usr/bin/env python3
"""Compare top-face package use packets with Java; live mouse taps are separate."""
import argparse
import csv
import json
import os
from importlib import import_module
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from fixture_world import ROOT, install_pack, last_command_message

placement = import_module("test-package-placement")
parse = placement.package.parse


def command(value, record=False):
    return {"op": "cmd", "cmd": value, "record": record}


def replay(args):
    with (ROOT / "fixtures/package-place-java.csv").open(newline="") as source:
        rows = [row for row in csv.DictReader(source) if row["face"] == "up"]
    assert len(rows) == 6
    operations = [command(value) for value in (
        "/fill 4 100 -16 16 100 -4 minecraft:smooth_stone",
        "/fill 4 101 -16 16 112 -4 minecraft:air",
        "/setblock 8 104 -12 minecraft:stone",
        "/setblock 6 104 -12 minecraft:stone",
        "/setblock 9 101 -12 minecraft:barrel",
        "/tp @s 6.5 105 -11.5 -90 39",
    )]
    for index, row in enumerate(rows):
        stack = (f'{{id:"{row["item"]}",count:1,components:{{"create:package_address":"{row["address"]}",'
                 '"create:package_contents":[{slot:0,item:{id:"minecraft:stone",count:3}}]}}')
        operations.extend((
            command(f'/gamemode {row["gamemode"].lower()} @s'),
            command(f'/data merge block 9 101 -12 {{Items:[{{Slot:0b,{stack[1:]}]}}'),
            command('/item replace entity @s hotbar.0 from block 9 101 -12 container.0'),
            {"op": "use_block", "pos": [8, 104, -12], "face": 1, "sequence": index * 2 + 1},
            command('/data get entity @e[type=create:package,limit=1] Pos', True),
            command('/data get entity @e[type=create:package,limit=1] equipment.mainhand', True),
            command('/data get entity @s SelectedItem', True),
            command('/item replace entity @s hotbar.0 from block 9 101 -12 container.0'),
            {"op": "use_block", "pos": [8, 104, -12], "face": 1, "sequence": index * 2 + 2},
            command('/data get entity @s SelectedItem', True),
            command('/execute if entity @e[type=create:package]', True),
            command('/kill @e[type=create:package]'),
        ))
    with TemporaryDirectory(prefix="hc-package-authority-") as scratch:
        game = Path(scratch)
        install_pack(game, args.pack)
        script, output = game / "script.jsonl", game / "output.jsonl"
        script.write_text(''.join(json.dumps(op) + '\n' for op in operations))
        result = subprocess.run(
            (str(args.client), '--headless', '--resources', str(args.resources), '--game-dir', str(game),
             '--home', str(game), '--world', 'PackagePlacementAuthority', '--render-distance', '4'),
            cwd=game, env=os.environ | {'HORIZON_COMMAND_SCRIPT': str(script),
                 'HORIZON_COMMAND_OUTPUT': str(output), 'HORIZON_NO_AUDIO': '1',
                 'HORIZON_NO_DISCORD': '1', 'HORIZON_HARNESS_TIMEOUT': '30',
                 'HORIZON_CREATE_PACKAGE_TRACE': '1'}, capture_output=True, text=True, timeout=50)
        if result.returncode:
            raise RuntimeError(f'Authority harness failed: {result.stderr[-5000:]}')
        records = [json.loads(line) for line in output.read_text().splitlines()]
    traces = [line.split(placement.TRACE, 1)[1].split(',') for line in result.stderr.splitlines()
              if placement.TRACE in line]
    assert len(records) == len(rows) * 5, len(records)
    assert len(traces) == len(rows), traces
    for index, (row, trace) in enumerate(zip(rows, traces, strict=True)):
        pos, stored, initial, repeat, count = records[index * 5:index * 5 + 5]
        stack = parse(last_command_message(stored).split('entity data: ', 1)[1])
        held = parse(last_command_message(repeat).split('entity data: ', 1)[1])
        expected = tuple(origin + float(row[axis]) for origin, axis in zip(placement.CENTER, 'xyz', strict=True))
        expected_frame = (*expected, float(row['width']), float(row['height']))
        assert row['result'] == 'SUCCESS' and row['repeat'] == 'PASS', row
        assert trace[1] == row['item'] and placement.same(tuple(map(float, trace[2:])), expected_frame), (row, trace)
        assert last_command_message(pos).endswith(f'[{expected[0]}d, {expected[1]}d, {expected[2]}d]'), (row, pos)
        assert stack == held == {'id': row['item'], 'count': 1, 'components': {
            'create:package_address': row['address'],
            'create:package_contents': [{'slot': 0, 'item': {'id': 'minecraft:stone', 'count': 3}}],
        }}, (row, stack, held)
        assert bool(initial['results'][-1][0]) == bool(int(row['held'])), (row, initial)
        assert int(row['repeat_held']) == 1 and count['results'][-1] == [True, int(row['placed'])], (row, count)
    print(f'Matched {len(rows)} Java top-face placement and rejected-repeat authority cases.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    replay(parser.parse_args())
