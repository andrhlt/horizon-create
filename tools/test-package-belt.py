#!/usr/bin/env python3
"""Compare physical Package pickup and transport on a horizontal Belt."""
import argparse
from collections import defaultdict
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

landing = import_module("test-package-depot")
placement = landing.placement
package = placement.package
START = (5, 104, -12)
END = (11, 104, -12)
MOTOR = (5, 104, -13)
STANDING = (8.5, 104, -9.5)
GUEST_VIEW = (8.5, 104, -13.5)
BASE = (8.5, 104.8125, -11.5)
AT = (8.72, 106.5625, -11.33)
xyz = placement.editor.xyz


def read_block(host, at, path, default):
    replies = host.call("command", f"/data get block {xyz(at)} {path}")["chat"]
    for reply in replies:
        if "block data: " in reply:
            return reply.split("block data: ", 1)[1]
    return default


def read_speed(host):
    return float(read_block(host, START, "Speed", "0").removesuffix("f"))


def settle_speed(host, expected):
    for _ in range(20):
        host.step_to(host.clock() + 1)
        if read_speed(host) == expected:
            return
    raise RuntimeError(f"The Belt did not settle to {expected} RPM ({read_speed(host)}).")


def connect(host):
    host.commands((
        "/fill 4 104 -14 12 109 -9 minecraft:air",
        f"/setblock {xyz(START)} create:shaft[axis=z]",
        f"/setblock {xyz(END)} create:shaft[axis=z]",
        "/give @s create:belt_connector",
    ))
    host.call("tp", *STANDING)
    host.call("select", "create:belt_connector")
    for _ in range(4):
        if "create:belt_connector" in host.command("/data get entity @s SelectedItem"):
            break
        host.call("wait", 1)
    else:
        raise RuntimeError("The host did not equip the Belt Connector.")
    for _ in range(3):
        host.call("interact", *START)
        if "CreateBeltFirstShaft" in host.command("/data get entity @s SelectedItem"):
            break
    else:
        raise RuntimeError("The first Belt shaft was never selected.")
    for _ in range(5):
        host.step_to(host.clock() + 1)
    host.call("interact", *END)
    for index, x in enumerate(range(START[0], END[0] + 1)):
        part = "start" if index == 0 else "end" if x == END[0] else "middle"
        state = host.call("block", x, START[1], START[2])["state"]
        if not state.startswith("create:belt[") or f"part={part}" not in state:
            raise RuntimeError(f"The connector did not place {part} at x={x}: {state}")


def seed(host, scenario):
    connect(host)
    rpm = 48 if scenario.lower().endswith("reverse") else -48
    host.command(f"/setblock {xyz(MOTOR)} create:creative_motor[facing=south]{{ScrollValue:{rpm}}}")
    settle_speed(host, rpm)
    # Removal of the source stops both original motion directions.
    if scenario.startswith("stopped"):
        host.command(f"/setblock {xyz(MOTOR)} minecraft:air")
        settle_speed(host, 0)
    host.call("command", f"/kill {landing.fire.SELECTOR}")
    placement.editor.wait_for(host, "the previous loose Package to leave", lambda: not placement.witness(host))
    cargo = '"create:package_contents":[{slot:6,item:{id:"minecraft:clay_ball",count:3}}]'
    stack = ('{id:"create:cardboard_package_10x8",count:1,components:{'
             f'"create:package_address":"Belt fixture",{cargo}' + '}}')
    options = (f"{{Silent:1b,PersistenceRequired:1b,Health:5f,Fire:-1s,equipment:{{mainhand:{stack}}},"
               "Motion:[0d,-0.12d,0d],Rotation:[47f,0f]}")
    host.command(f"/summon create:package {xyz(AT)} {options}")
    placement.editor.wait_for(host, "the new Belt Package to arrive", lambda: len(placement.witness(host)) == 1)
    return placement.witness(host)[0]["id"]


def run_case(host, actor, scenario, rows):
    entity = seed(host, scenario)
    peers = (host,) if actor is host else (host, actor)
    start = host.clock()
    for row in rows:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        removed = row["removed"] == "true"
        for peer in peers:
            placement.editor.wait_for(peer, f"the loose Package presence in {scenario} at tick {tick}",
                                      lambda: (landing.body(peer, entity) is None) == removed)
        if not removed:
            pos = tuple(value - origin for value, origin in zip(landing.entity_vector(host, "Pos"), BASE, strict=True))
            motion = landing.entity_vector(host, "Motion")
            yaw = landing.entity_vector(host, "Rotation", "f")[0]
            for actual, fields in ((pos, ("x", "y", "z")), (motion, ("vx", "vy", "vz")), ((yaw,), ("yaw",))):
                want = tuple(float(row[key]) for key in fields)
                assert placement.same(actual, want, 2e-6), (scenario, row, fields, actual)
        assert read_speed(host) == float(row["rpm"]), (scenario, tick, read_speed(host), row)
        encoded = row["stack_hex"]
        raw = read_block(host, START, "Inventory.Items[0]", "{}")
        carried = package.parse(re.sub(r"(?<=\d)f(?=[,}])", "", raw))
        if not encoded:
            assert not carried, (scenario, tick, carried)
            continue
        order = read_block(host, START, "Inventory.PositiveOrder", "0").removesuffix("b")
        assert (order == "1") == (row["positive_order"] == "true"), (scenario, tick, order, row)
        java_stack = package.parse(bytes.fromhex(encoded).decode())
        stack = {key: value for key, value in carried["Item"].items() if key not in ("Slot", "slot")}
        assert stack == java_stack, (scenario, tick, carried, java_stack)
        for key, column in (("Pos", "belt_pos"), ("PrevPos", "belt_prev"), ("InsertedAt", "segment"),
                            ("InsertedFrom", "direction")):
            assert abs(float(carried[key]) - float(row[column])) < 2e-6, (scenario, tick, key, carried, row)
    print(f"{scenario}: {len(rows)} frames", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--case", action="append")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    grouped = defaultdict(list)
    with (ROOT / "fixtures/package-belt-java.csv").open(newline="") as data:
        for row in csv.DictReader(data):
            grouped[row["case"]].append(row)
    assert len(grouped) == 4 and sum(map(len, grouped.values())) == 108
    scenarios = args.case or tuple(grouped)
    world = "PackageBeltGuest" if args.lan else "PackageBeltHost"
    with TemporaryDirectory(prefix="hc-package-belt-") as scratch:
        with fixture_world(args, world, render=True, pack=args.pack) as host:
            host.commands((
                "/fill 4 100 -16 16 100 -4 minecraft:obsidian",
                "/fill 4 101 -16 16 112 -4 minecraft:air",
                "/fill 4 103 -14 12 103 -9 minecraft:obsidian",
            ))
            with package.filters.actor_for(host, args, Path(scratch) if args.lan else None) as (actor, name):
                if actor is not host:
                    placement.teleport(host, actor, name, GUEST_VIEW)
                for scenario in scenarios:
                    run_case(host, actor, scenario, grouped[scenario])
    print(f"Matched {sum(len(grouped[s]) for s in scenarios)} Java Package Belt frames.", flush=True)


if __name__ == "__main__":
    main()
