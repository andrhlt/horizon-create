#!/usr/bin/env python3
"""Compare a recorded guest trace against Java captured at those exact input ticks."""
import csv
import json
from food_trace import same_f32
import sys

with open(sys.argv[1]) as f:
    rows = [json.loads(line) for line in f]
rows = [row for row in rows if row['player'] == 'FoodGuest']
starts = [i for i, row in enumerate(rows)
          if row['using'] == 0 and row['slot0_item'].startswith('create:')]
assert len(starts) == 12, f'expected twelve use starts, got {len(starts)}'
with open(sys.argv[2]) as f:
    java = list(csv.DictReader(f))
for index in range(6):
    start, restart = starts[2 * index:2 * index + 2]
    actual = rows[start:restart + 36]
    food = rows[start]['slot0_item'].split(':')[1]
    scenario = ('release', 'swap')[index % 2]
    expected = [row for row in java if row['food'] == food and row['scenario'] == scenario]
    assert len(actual) == len(expected), (food, scenario, len(actual), len(expected))
    for tick, (a, e) in enumerate(zip(actual, expected, strict=True)):
        selected, count = int(e['selected']), int(e['count'])
        remaining = 0 if a['using'] is None else a['duration'] - a['using']
        assert int(e['tick']) == tick and a['tick'] == actual[0]['tick'] + tick
        assert (a['selected'], a['slot0_item'], a['slot0_count'], remaining, a['hunger']) == (
            selected, e['item'], count, int(e['use_remaining']), int(e['hunger'])), (food, scenario, tick, a, e)
        assert (a['item'], a['count']) == ((e['item'], count) if selected == 0 else ('minecraft:air', 0))
        assert same_f32(a['saturation'], e['saturation'])
    print(f'{food} {scenario}: {len(actual)} consecutive ticks matched exactly')
