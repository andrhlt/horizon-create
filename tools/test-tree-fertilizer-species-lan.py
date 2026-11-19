#!/usr/bin/env python3
"""Compare a LAN guest's Acacia fertilizer use with Java."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module('test-multiplayer')
tree = import_module('test-multiplayer-tree-fertilizer')


def run(args):
    with (ROOT / 'fixtures/tree_fertilizer_species-java.csv').open() as source:
        row = next(row for row in csv.DictReader(source) if row['sapling'] == 'minecraft:acacia_sapling')
    with fixture_world(args, 'Acacia Fertilizer LAN', pack=args.pack,
                       env={'HORIZON_NO_AUDIO': '1'}) as host:
        port = host.call('lan', 'open', 0, 'commands', 'force')['port']
        with TemporaryDirectory(prefix='hc-acacia-lan-') as scratch, multiplayer.joined_client(
            args, Path(scratch), f'127.0.0.1:{port}', tree.GUEST, render=True,
            scenario='acacia-fertilizer-lan', pack=args.pack, env={'HORIZON_NO_AUDIO': '1'},
        ) as guest:
            multiplayer.until('guest to join', lambda: any(
                player['name'] == tree.GUEST and player['placed']
                for player in host.call('lan', 'status')['guests']
            ))
            host.commands((
                f'/gamemode survival {tree.GUEST}',
                '/fill 6 169 20 14 169 28 minecraft:dirt',
                '/fill 6 170 20 14 185 28 minecraft:air',
                f'/setblock 10 170 22 {row["sapling"]}[stage=0]',
            ))
            tree.give_and_aim(host, guest, (10.5, 170.0, 25.5), (10, 170, 22))
            for observer in (host, guest):
                multiplayer.until('acacia base on both clients', lambda:
                    observer.call('block', 10, 170, 22)['block'] == row['base'])
            tree.assert_consumed(host, guest, row)
    print('LAN guest Acacia base and fertilizer consumption matched Java.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=lambda path: Path(path).resolve(strict=True), default=ROOT / ".local/create.hmod")
    run(parser.parse_args())
