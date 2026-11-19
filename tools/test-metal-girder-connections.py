#!/usr/bin/env python3
"""Replay changes to plain and encased Metal Girder connection flags."""
import argparse
import csv
from itertools import zip_longest
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

GIRDER = "create:metal_girder"
ENCASED = "create:metal_girder_encased_shaft"


def pos(position):
    return " ".join(map(str, position))


def origin(index):
    return 8, 101, -20 + index * 6


def neighbor(index, first):
    x, y, z = origin(index)
    delta = 1 if first else -1
    return (x, y + delta, z) if index == 2 else (x, y, z + delta)


def setup(control):
    control.commands((
        "/fill 4 100 -24 14 105 -5 minecraft:air",
        f"/setblock {pos(origin(0))} {GIRDER}[axis=x,x=true]",
        f"/setblock {pos(origin(1))} {GIRDER}[axis=x,x=true,waterlogged=true]",
        f"/setblock {pos(origin(2))} {ENCASED}[axis=x,waterlogged=true]",
    ))


def act(control, tick, index):
    at = neighbor(index, tick in (3, 8))
    states = (f"{GIRDER}[axis=z,z=true]", f"{ENCASED}[axis=x]", f"{GIRDER}[axis=y,top=true,bottom=true]")
    placed = states[index] if tick in (3, 6) else "minecraft:air"
    control.command(f"/setblock {pos(at)} {placed}")


def sample(control, tick, index):
    state = control.call("block", *origin(index))["state"]
    expected_block = ENCASED if index == 2 else GIRDER
    if not state.startswith(expected_block + "["):
        raise RuntimeError(f"Tick {tick}: scenario {index} center disappeared: {state}")
    p = dict(re.findall(r"([a-z_]+)=([a-z]+)", state))
    return (str(tick), str(index), p["axis"], *(p.get(key, "false") for key in ("x", "z", "top", "bottom", "waterlogged")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/metal-girder-connections-horizon.csv")
    args = parser.parse_args()
    with (ROOT / "fixtures/metal-girder-connections-java.csv").open() as stream:
        header, *expected = list(csv.reader(stream))
    actual = []
    with fixture_world(args, "GirderConnections", pack=args.pack) as control:
        setup(control)
        start = control.clock()
        for tick in range(1, 15):
            control.step_to(start + tick)
            for index in range(3):
                actual.append(sample(control, tick, index))
                if tick in (3, 6, 8, 11):
                    act(control, tick, index)
    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want, got) for want, got in zip_longest(map(tuple, expected), actual) if want != got]
    if differences:
        raise RuntimeError(f"{len(differences)} differences; first six: {differences[:6]}")
    print(f"Dynamic girder attachments and disconnections matched all {len(actual)} Java rows.")


if __name__ == "__main__":
    main()
