#!/usr/bin/env python3
"""Replay the original pulse extender, repeater, and timer circuits."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
stone = import_module("test-stone-palettes")
BATCH = (
    ("extender_default", "pulse_extender", 2),
    ("extender_five", "pulse_extender", 5),
    ("repeater_default", "pulse_repeater", 2),
    ("repeater_seven", "pulse_repeater", 7),
    ("timer_default", "pulse_timer", 20),
    ("timer_two_inverted", "pulse_timer", 2),
)
POSITIONS = tuple((8, 120 + i * 4, -8) for i in range(len(BATCH)))


def coords(pos):
    return " ".join(map(str, pos))


def views(control, tick):
    tags = control.commands(f"/data get block {coords(pos)}" for pos in POSITIONS)
    checks = iter(control.commands(
        query
        for (_, block, _), (x, y, z) in zip(BATCH, POSITIONS, strict=True)
        for query in (
            *(f"/execute if block {x} {y} {z} create:{block}[{key}=true]"
              for key in ("powered", "powering", "inverted")),
            *(f"/execute if block {wx} {y} {wz} minecraft:redstone_wire[power={level}]"
              for wx, wz in ((x - 1, z), (x, z - 1)) for level in (0, 15)),
        )
    ))
    for (name, _, _), nbt in zip(BATCH, tags, strict=True):
        results = [next(checks) for _ in range(7)]
        if any(result not in ("Test passed", "Test failed") for result in results):
            raise RuntimeError(f"Unexpected authority reply for {name}: {results}")
        flags = [result == "Test passed" for result in results]
        if flags[3] == flags[4] or flags[5] == flags[6]:
            raise RuntimeError(f"{name} has a missing wire or unexpected intermediate strength: {results}")
        wire_power = [str(15 if full else 0) for full in (flags[4], flags[6])]
        timers = [re.search(rf"\b{key}: (-?\d+)", nbt) for key in ("State", "ScrollValue")]
        if None in timers:
            raise RuntimeError(f"Missing original timer values in {name}. {nbt}")
        yield [name, str(tick), *(str(flag).lower() for flag in flags[:3]),
               *(timer[1] for timer in timers), *wire_power]


def setup(world):
    world.commands((
        "/fill 5 119 -10 11 143 -6 minecraft:air",
        "/tp @s 10.5 122 -8.5",
        *(command for (name, block, interval), (x, y, z) in zip(BATCH, POSITIONS, strict=True)
          for command in (
              f"/fill {x - 1} {y - 1} {z - 1} {x} {y - 1} {z} minecraft:smooth_stone",
              f"/setblock {x} {y} {z} create:{block}[facing=east,inverted={str(name.endswith('inverted')).lower()}]{{State:0,ScrollValue:{interval}}}",
              f"/setblock {x - 1} {y} {z} minecraft:redstone_wire",
              f"/setblock {x} {y} {z - 1} minecraft:redstone_wire",
          )),
    ))


def replay(world, guest, expected):
    results = []
    start = world.clock()
    for tick in range(len(expected) // len(BATCH)):
        if tick:
            world.step_to(start + tick)
        if tick in (4, 9, 13, 14, 30, 36):
            source = "minecraft:redstone_block" if tick in (4, 13, 30) else "minecraft:air"
            world.commands(f"/setblock {x + 1} {y} {z} {source}" for x, y, z in POSITIONS)
        results.extend(views(world, tick))
        if guest and tick % 4 == 0:
            want = {name: out for name, _, _, out, *_ in results[-len(BATCH):]}
            for (name, _, _), at in zip(BATCH, POSITIONS, strict=True):
                mp.until(f"guest sees {name} output at tick {tick}", lambda:
                         stone.state_properties(guest.call("block", *at)["state"]).get("powering") == want[name])
    differences = [(want, got) for want, got in zip(expected, results, strict=True) if want != got]
    return differences, results


def main():
    parser = argparse.ArgumentParser()
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--write-trace", type=Path)
    args = parser.parse_args()
    fixture = ROOT / "fixtures/brass-diode-pulses-java.csv"
    with fixture.open() as source:
        reader = csv.reader(source)
        header = next(reader)
        expected = list(reader)
    with ExitStack() as stack:
        scenario = "BrassDiodesLAN" if args.lan else "BrassDiodes"
        world = stack.enter_context(fixture_world(args, scenario, pack=args.pack))
        setup(world)
        guest = None
        if args.lan:
            name = "DiodeGuest"
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            directory = Path(stack.enter_context(TemporaryDirectory(prefix="hc-diode-")))
            guest = stack.enter_context(mp.joined_client(
                args, directory, f"127.0.0.1:{port}", name, scenario="brass-diodes", pack=args.pack,
            ))
            mp.until("the guest to join", lambda: any(
                player["name"] == name and player["placed"] for player in world.call("lan", "status")["guests"]
            ))
            world.command(f"/tp {name} 10.5 120 -8.5")
            mp.until("guest sees the diode row", lambda:
                     guest.call("block", *POSITIONS[-1])["block"] == "create:pulse_timer")
        differences, results = replay(world, guest, expected)
    if args.write_trace:
        with args.write_trace.open("w", newline="") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(results)
    print(f"Compared {len(results)} original diode rows, {len(differences)} differences.", flush=True)
    for difference in differences[:12]:
        print(difference, flush=True)
    raise SystemExit(bool(differences))


if __name__ == "__main__":
    main()
