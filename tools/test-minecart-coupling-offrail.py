#!/usr/bin/env python3
"""Compare a coupled pair leaving a short rail with pinned Java."""
import argparse
import csv
import importlib.util
import re
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "multiplayer", Path(__file__).with_name("test-multiplayer.py")
)
multiplayer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multiplayer)
GUEST = "CouplingGuest"
FIELDS = [
    f"{tag}_{value}"
    for tag in ("a", "b", "base")
    for value in ("x", "y", "vx", "vy")
]


def sample(world, tag):
    data = world.command(f"/data get entity @e[type=minecraft:minecart,tag={tag},limit=1]")
    values = []
    for key in ("Pos", "Motion"):
        match = re.search(key + r": \[([-0-9.eE]+)d, ([-0-9.eE]+)d, ([-0-9.eE]+)d\]", data)
        if not match:
            raise RuntimeError(f"Missing {key}: {data}")
        values.extend((float(match.group(1)), float(match.group(2))))
    return values


@contextmanager
def player_pair(world, args):
    positions = (12.5, 15.5) if args.both_off else (8.5, 11.5)
    if not args.lan:
        world.commands((
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:minecart_coupling 2",
        ))
        world.call("select", "create:minecart_coupling")
        for x in positions:
            world.command(f"/tp @s {x} 170 22.5")
            world.call("look-at", x, 170.2, 24.5)
            world.call("wait", 4)
            world.call("mouse", "right", "click")
            world.call("wait", 3)
        yield
        return

    network = world.call("lan", "open", "0", "commands", "force")
    with TemporaryDirectory(prefix="hc-offrail-") as scratch:
        with multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{network['port']}", GUEST,
            render=True, scenario="multiplayer-minecart-offrail", pack=args.pack,
        ) as guest:
            multiplayer.until(
                "guest to join",
                lambda: any(p["name"] == GUEST and p["placed"] for p in world.call("lan", "status")["guests"]),
            )
            world.commands((
                f"/gamemode survival {GUEST}",
                f"/item replace entity {GUEST} hotbar.0 with create:minecart_coupling 2",
                f"/tp {GUEST} 8.5 170 22.5",
            ))
            multiplayer.until("guest to hold couplings", lambda: multiplayer.count(guest, "create:minecart_coupling") == 2)
            guest.call("select", "create:minecart_coupling")
            for x in positions:
                world.command(f"/tp {GUEST} {x} 170 22.5")
                multiplayer.until("guest to reach cart", lambda: guest.call("state")["player"]["position"] == [x, 170.0, 22.5])
                guest.call("look-at", x, 170.2, 24.5)
                guest.call("wait", 4)
                guest.call("mouse", "right", "click")
                guest.call("wait", 3)
            multiplayer.until("one coupling consumed", lambda: multiplayer.count(guest, "create:minecart_coupling") == 1)
            yield


def run(args):
    fixture = "minecart-coupling-both-offrail-java.csv" if args.both_off else "minecart-coupling-offrail-java.csv"
    with (ROOT / "fixtures" / fixture).open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not 1 <= args.ticks <= len(rows):
        raise ValueError("invalid tick count")
    rows = rows[:args.ticks]

    with fixture_world(args, "MinecartOffRail", pack=args.pack, render=not args.lan) as world:
        commands = [
            "/fill 4 169 20 24 169 34 minecraft:stone",
            "/fill 4 170 20 24 173 34 minecraft:air",
            "/fill 4 170 24 12 170 24 minecraft:rail[shape=east_west]",
            "/fill 4 170 32 12 170 32 minecraft:rail[shape=east_west]",
            '/summon minecraft:minecart 8.5 170.0625 24.5 {UUID:[I;0,0,0,1],Motion:[0.3d,0d,0d],Tags:["offrail_a"]}',
            '/summon minecraft:minecart 11.5 170.0625 24.5 {UUID:[I;0,0,0,2],Motion:[0.3d,0d,0d],Tags:["offrail_b"]}',
            '/summon minecraft:minecart 11.5 170.0625 32.5 {UUID:[I;0,0,0,3],Motion:[0.3d,0d,0d],Tags:["offrail_base"]}',
        ]
        if args.both_off:
            commands = [command.replace(" 8.5 170.0625", " 12.5 170.0625").replace(" 11.5 170.0625", " 15.5 170.0625") for command in commands]
        world.commands(commands)
        for z in (24, 32):
            if "shape=east_west" not in world.call("block", 12, 170, z)["state"]:
                raise RuntimeError("last rail wrong")
            if "minecraft:air" not in world.call("block", 13, 170, z)["state"]:
                raise RuntimeError("rail continues")
        for i, tag in enumerate(("offrail_a", "offrail_b", "offrail_base"), 1):
            uuid = world.command(f"/data get entity @e[type=minecraft:minecart,tag={tag},limit=1] UUID")
            if f"[I; 0, 0, 0, {i}]" not in uuid:
                raise RuntimeError(f"Wrong UUID: {uuid}")

        with player_pair(world, args):
            link = world.command("/data get entity @e[type=minecraft:marker,tag=create_minecart_coupling,limit=1] CreateMinecartCoupling")
            if "Length: 3.0f" not in link:
                raise RuntimeError(f"Missing link: {link}")
            for row in rows:
                actual = sum((sample(world, tag) for tag in ("offrail_a", "offrail_b", "offrail_base")), [])
                target = [float(row[key]) for key in FIELDS]
                start = 8 if args.base_only else 0
                end = 8 if args.pair_only else len(FIELDS)
                if any(abs(a - b) > 0.00001 for a, b in zip(actual[start:end], target[start:end])):
                    raise RuntimeError(f"Tick {row['tick']} differs from Java: {actual} vs {target}")
                if int(row["tick"]) != len(rows) - 1:
                    world.step_to(world.clock() + 1)

    scope = "standalone" if args.base_only else "pair" if args.pair_only else "pair and standalone"
    mode = "guest LAN" if args.lan else "solo"
    print(f"Matched {len(rows)} off-rail Java ticks for {scope} in {mode}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--base-only", action="store_true")
    group.add_argument("--pair-only", action="store_true")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--both-off", action="store_true")
    parser.add_argument("--ticks", type=int, default=81)
    run(parser.parse_args())
