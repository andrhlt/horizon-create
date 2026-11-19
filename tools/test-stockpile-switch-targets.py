#!/usr/bin/env python3
"""Compare Stockpile Switch fluid and signed pulley settings with Java."""

import argparse
from contextlib import contextmanager
import csv
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


CASES = ((8, -53, -8), (13, -53, -8))
ACTOR = "StockpileTargets"
spec = spec_from_file_location("editor", ROOT / "tools/test-stockpile-switch-editor.py")
editor = module_from_spec(spec)
spec.loader.exec_module(editor)


def container(case):
    x, y, z = CASES[case]
    return (x, y, z + 1)


def set_water(host, amount):
    host.command(f'/data merge block {editor.xyz(container(0))} '
                 f'{{TankContent:{{Fluid:{{id:"minecraft:water",amount:{amount}}}}}}}')


def set_offset(host, amount):
    host.command(f"/data merge block {editor.xyz(container(1))} {{Offset:{amount}.0f}}")


def setup(host):
    host.commands((
        "/fill 7 -53 -13 15 -48 -6 minecraft:air",
        "/fill 7 -54 -13 15 -54 -6 minecraft:smooth_stone",
        f"/setblock {editor.xyz(container(0))} create:fluid_tank",
        f"/setblock {editor.xyz(container(1))} create:rope_pulley",
        *(f"/setblock {editor.xyz(pos)} create:stockpile_switch[target=wall,facing=south]" for pos in CASES),
        "/tp @s 11.5 -53 -10.5",
        "/gamemode survival @s",
    ))
    set_water(host, 2000)


@contextmanager
def control_actor(host, args, scratch):
    if scratch is None:
        yield host, "@s"
        return
    multiplayer = editor.load_multiplayer()
    address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
    with multiplayer.joined_client(
        args, scratch, address, ACTOR, render=True, scenario="stockpile-targets", pack=args.pack,
    ) as guest:
        multiplayer.until("the guest to join the low Y sensors", lambda: any(
            player["name"] == ACTOR and player["placed"] for player in host.call("lan", "status")["guests"]
        ))
        host.command(f"/gamemode survival {ACTOR}")
        yield guest, ACTOR


def open_editor(host, actor, name, case):
    x, y, z = CASES[case]
    host.command(f"/tp {name} {x + 0.5} {y} {z - 3.5}")
    editor.wait_for(actor, "the player to reach the selected sensor", lambda:
        actor.call("state")["player"]["position"][:3] == [x + 0.5, float(y), z - 3.5]
    )
    actor.call("look-at", x + .73, y + .76, z + .1)
    actor.call("wait", 3)
    hit = actor.call("looking-at").get("block")
    assert hit and hit["pos"] == list(CASES[case]), hit
    actor.call("mouse", "right", "click")
    editor.wait_for(actor, "the Stockpile Switch editor", lambda: actor.call("state")["screen"] == "mod")
    editor.wait_for(actor, "the four non-item controls", lambda: len(actor.call("screen")["buttons"]) == 4)


def read(host, case):
    return host.command(f"/data get block {editor.xyz(CASES[case])}")


def settings_applied(host, case, lower, upper, invert):
    data = read(host, case)
    return (
        editor.field(data, "OffBelowAmount"), editor.field(data, "OnAboveAmount"), editor.field(data, "Inverted", 0),
    ) == (lower, upper, invert)


def configure(host, actor, name, *, invert):
    for case in range(len(CASES)):
        open_editor(host, actor, name, case)
        if invert:
            actor.call("click-at", *editor.widget(actor, "Invert Signal"))
        elif case == 0:
            editor.scroll(actor, "≥ 1 Buckets", 1, 2)
            editor.scroll(actor, "≤ 0 Buckets", 1)
            editor.widget(actor, "≥ 3 Buckets")
            editor.widget(actor, "≤ 1 Buckets")
        else:
            editor.scroll(actor, "≥ -53y", -1, 2)
            # Moving the upper threshold below the lower one moves both fields.
            editor.scroll(actor, "≤ -56y", -1, 5)
            editor.widget(actor, "≥ -55y")
            editor.widget(actor, "≤ -61y")
        editor.confirm(actor)
        lower, upper = (1000, 3000) if case == 0 else (-61, -55)
        editor.wait_for(host, "the selected units and thresholds to apply", lambda:
            settings_applied(host, case, lower, upper, invert)
        )


def compare(host, case, row):
    _, _, _, min_amount, amount, max_amount, lower, upper, inverted, raw, output, level, max_y = row
    assert max_y == str(CASES[1][1])
    data = read(host, case)
    for key, expected, default in (
        ("CurrentMinAmount", int(min_amount), None),
        ("CurrentAmount", int(amount), None),
        ("CurrentMaxAmount", int(max_amount), None),
        ("OffBelowAmount", int(lower), 64),
        ("OnAboveAmount", int(upper), 128),
        ("Inverted", int(inverted == "true"), 0),
        ("Powered", int(raw == "true"), 0),
        ("PoweredAfterDelay", int(output == "true"), 0),
    ):
        assert editor.field(data, key, default) == expected, (row[0], case, key, expected, data)
    query = f"/execute if block {editor.xyz(CASES[case])} create:stockpile_switch[level={level},powered={output}]"
    assert host.command(query).startswith("Test passed"), (row[0], case, query, data)


def verify(args, scratch):
    with (ROOT / "fixtures/stockpile-switch-targets-java.csv").open(newline="") as source:
        rows = list(csv.reader(source))
    assert len(rows) == 86
    with fixture_world(args, "StockpileSwitchTargets", render=True, pack=args.pack) as host:
        setup(host)
        with control_actor(host, args, scratch) as (actor, name):
            start = host.clock()
            for tick in range(1, 43):
                host.step_to(start + tick)
                if tick in (4, 25):
                    configure(host, actor, name, invert=tick == 25)
                    assert host.clock() == start + tick
                if tick == 13:
                    set_water(host, 4000)
                    set_offset(host, 10)
                if tick == 27:
                    set_water(host, 500)
                    set_offset(host, 0)
                for case in range(len(CASES)):
                    row = rows[2 * tick + case]
                    assert tuple(map(int, row[:2])) == (tick, case)
                    compare(host, case, row)
    actor = "Guest" if scratch else "Host"
    print(f"{actor} matched all 84 Java tank and rope threshold samples, including buckets and negative pulley heights.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-stpt-") as scratch:
            verify(args, Path(scratch))
    else:
        verify(args, None)


if __name__ == "__main__":
    main()
