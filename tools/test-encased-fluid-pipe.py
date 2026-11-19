#!/usr/bin/env python3
"""Replay original Encased Fluid Pipe ownership, states and pumped transfer."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

branched = import_module("test-branched-pipes")
entity_data = import_module("test-depot-ejector-obstacle")
multiplayer = import_module("test-multiplayer")

BLOCK = "create:encased_fluid_pipe"
PIPE = "create:fluid_pipe"
CASING = "create:copper_casing"
WRENCH = "create:wrench"
FACES = ("down", "up", "north", "south", "west", "east")
TRANSFER_PIPE = (6, 97, -10)
ENV = {"HORIZON_NO_AUDIO": "1"}
GUEST = "EncasedPipeGuest"


def java(name, *, repeat=False):
    suffix = "-repeat" if repeat else ""
    path = ROOT / "fixtures" / f"encased-fluid-pipe-{name}-java{suffix}.csv"
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def coords(pos):
    return " ".join(map(str, pos))


def encoded_state(row):
    props = {}
    if len(row["faces"]) == 1:
        props["axis"] = row["faces"]
    else:
        props.update((key, str(bit == "1").lower()) for key, bit in zip(FACES, row["faces"], strict=True))
    if row["waterlogged"] != "-":
        props["waterlogged"] = row["waterlogged"]
    return row["id"] + "[" + ",".join(f"{k}={v}" for k, v in props.items()) + "]"


def current(host, pos):
    state = host.call("block", *pos)["state"]
    item, _, properties = state.partition("[")
    entries = dict(entry.split("=", 1) for entry in properties.rstrip("]").split(",") if entry)
    faces = entries.get("axis") or "".join(str(int(entries.get(face) == "true")) for face in FACES)
    return item, faces, entries.get("waterlogged", "-")


def aim(actor, pos, height):
    x, y, z = pos
    actor.call("look-at", x + .5, y + height, z + .5)
    actor.call("wait", 3)


def use(actor, pos, item, *, sneak=False, height=.5):
    actor.call("select", item)
    if sneak:
        actor.call("key", "shift", "down")
    try:
        if sneak:
            actor.call("wait", 6)
        aim(actor, pos, height)
        target = actor.call("looking-at").get("block")
        if not target or target["pos"] != list(pos):
            raise RuntimeError(f"{item} aimed at {target}; expected {pos}")
        actor.call("mouse", "right", "click")
        actor.call("wait", 3)
    finally:
        if sneak:
            actor.call("key", "shift", "up")


def expect_state(host, pos, row, actor):
    want = row["id"], row["faces"], row["waterlogged"]
    multiplayer.until(f'{row["case"]} {row["action"]} to produce {want}',
                      lambda: current(host, pos) == want)
    if actor is not host:
        multiplayer.until(f'delivering {row["action"]} to the acting guest',
                          lambda: current(actor, pos) == want)
    data = host.command(f"/data get block {coords(pos)}")
    if row["entity_id"] not in data:
        raise RuntimeError(f"{pos} has the wrong block entity: {data}")


def inventory(actor, item):
    return actor.call("inventory")["counts"].get(item, 0)


def test_actor(stack, args, host, name):
    if not args.lan:
        return host, "@s"
    port = host.call("lan", "open", 0, "commands", "force")["port"]
    scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-encased-pipe-")))
    guest = stack.enter_context(multiplayer.joined_client(
        args, scratch, f"127.0.0.1:{port}", GUEST, scenario=name, pack=args.pack, env=ENV,
    ))
    multiplayer.until("the guest to join", lambda: any(
        player["name"] == GUEST and player["placed"]
        for player in host.call("lan", "status")["guests"]
    ))
    return guest, GUEST


def static_states(args):
    name = "EncasedPipeStateLAN" if args.lan else "EncasedPipeState"
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, name, pack=args.pack, env=ENV))
        actor, player = test_actor(stack, args, host, name)
        host.commands((
            "/fill 7 170 17 26 170 24 minecraft:stone",
            "/fill 7 171 17 26 174 24 minecraft:air",
            f"/gamemode survival {player}",
            f"/tp {player} 8.5 171 19.5",
            *(("/tp @s 8.5 171 23.5",) if args.lan else ()),
            f"/item replace entity {player} hotbar.0 with {CASING} 5",
            f"/item replace entity {player} hotbar.1 with {WRENCH}",
        ))
        default, = java("default")
        host.command(f"/setblock 8 171 21 {BLOCK}")
        multiplayer.until("the default encased pipe to load",
                          lambda: current(host, (8, 171, 21)) == (default["id"], default["faces"], "-"))
        host.command("/setblock 8 171 21 minecraft:air")

        groups = {}
        for row in java("state"):
            groups.setdefault(row["case"], {})[row["action"]] = row
        pickup = {row["case"]: row for row in java("pickup")}
        for index, (case, actions) in enumerate(groups.items()):
            pos = (9 + 3 * index, 171, 21)
            x, y, z = pos
            initial = actions["wrong_casing"]
            host.commands((
                f"/setblock {coords(pos)} {encoded_state(initial)}",
                f"/tp {player} {x + .5} {y} {z - 1.5}",
                f"/item replace entity {player} hotbar.2 with create:andesite_casing",
            ))
            multiplayer.until(f"{player} to reach {pos}", lambda:
                              abs(actor.call("state")["player"]["position"][0] - (x + .5)) < .001)
            multiplayer.until("the test casing to reach the acting player",
                              lambda: inventory(actor, "create:andesite_casing") == 1)
            use(actor, pos, "create:andesite_casing")
            expect_state(host, pos, initial, actor)
            host.commands((
                f"/setblock {x} {y + 1} {z} minecraft:air",
                f"/setblock {x} {y} {z - 1} minecraft:air",
            ))

            encased = actions["encase"]
            use(actor, pos, CASING)
            expect_state(host, pos, encased, actor)
            assert inventory(actor, CASING) == int(encased["held_count"]), case

            if "add_north_pipe" in actions:
                host.command(f"/setblock {x} {y} {z - 1} create:fluid_pipe[north=true,south=true]")
                expect_state(host, pos, actions["add_north_pipe"], actor)

            host.commands((f"/gamemode creative {player}", f"/clear {player} {PIPE}"))
            multiplayer.until("entering creative for Pick Block", lambda: actor.call("status")["creative"])
            aim(actor, pos, .75)
            actor.call("mouse", "middle", "click")
            multiplayer.until("pick block to return a regular Fluid Pipe",
                              lambda: inventory(actor, encased["clone_item"]) == 1)
            host.commands((f"/gamemode survival {player}", f"/clear {player} {PIPE}"))
            multiplayer.until("returning to survival", lambda: not actor.call("status")["creative"])
            multiplayer.until("clearing the cloned pipe from inventory", lambda: not inventory(actor, PIPE))
            use(actor, pos, WRENCH)
            expect_state(host, pos, actions["uncase"], actor)
            assert inventory(actor, CASING) == 5, case

            host.command(f"/setblock {coords(pos)} {encoded_state(initial)}")
            use(actor, pos, CASING)
            expect_state(host, pos, encased, actor)
            use(actor, pos, WRENCH, sneak=True, height=.8)
            multiplayer.until(f"{case} crouched wrench to dismantle the pipe",
                              lambda: host.call("block", *pos)["state"] == pickup[case]["id"])
            multiplayer.until(f"{player} to receive the picked Fluid Pipe",
                              lambda: inventory(actor, PIPE) == int(pickup[case]["pipes_received"]))
            assert inventory(actor, CASING) == int(pickup[case]["casing_count"]), case
    print("Five original casing, uncasing, clone and crouched pickup cases matched Java.")


def compound(text, key):
    match = re.search(rf"\b{re.escape(key)}:\s*\{{", text)
    if not match:
        return ""
    depth = 1
    for index in range(match.end(), len(text)):
        brace = text[index]
        depth += (brace == "{") - (brace == "}")
        if depth == 0:
            return text[match.end():index]
    raise RuntimeError(f"Incomplete SNBT at {key}: {text}")


def interfaces(text):
    result = []
    for face in FACES:
        port = compound(text, face)
        if not port:
            result.append(f"{face}:_")
            continue
        pressure = entity_data.vector(port, "Pressure") or (0.0, 0.0)
        flow = compound(port, "Flow")
        fluid = re.search(r'\bid: "([^"]+)"', compound(flow, "Fluid"))
        direction = re.search(r"\bIn: ([01])b", flow)
        fluid_id = fluid[1] if fluid else ""
        inbound = str(direction[1] == "1").lower() if direction else "_"
        progress = "partial" if "Progress:" in flow else "complete"
        result.append(f"{face}:{pressure[0]:.4f}:{pressure[1]:.4f}:{fluid_id}:{inbound}:{progress}")
    return "|".join(result)


def sample(host, tick, phase):
    _, _, rpm, *tanks = branched.sample(host, "split", tick)
    block, faces, _ = current(host, TRANSFER_PIPE)
    data = host.command(f"/data get block {coords(TRANSFER_PIPE)}")
    return (str(tick), phase, block, faces, f"{float(rpm):.4f}", *tanks, interfaces(data))


def compare_transfer(actual):
    attempts = []
    for repeat in (False, True):
        expected = [tuple(row.values()) for row in java("transfer", repeat=repeat)]
        attempts.append([(want, got) for want, got in zip(expected, actual, strict=True) if want != got])
    # Java picks either branch for the remainder after a network rebuild.
    # Match a complete observed Java sequence rather than masking each branch.
    misses = min(attempts, key=len)
    if misses:
        raise RuntimeError(f"{len(misses)} fluid samples differed. First: {misses[:2]}")


def transfer(args):
    actual = []
    expected = java("transfer")
    template = "gametest/fluids/3_pipe_split"
    name = "EncasedPipeTransferLAN" if args.lan else "EncasedPipeTransfer"
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, name, Path(template + ".nbt"), pack=args.pack, env=ENV))
        actor, player = test_actor(stack, args, host, name)
        host.commands((
            f"/place template create:{template} 3 96 -12",
            f"/setblock {branched.PUMP} create:mechanical_pump[facing=west,waterlogged=false]",
            f"/tp {player} 6.5 98 -8.5",
            *(("/tp @s 7.5 99 -8.5",) if args.lan else ()),
            f"/gamemode survival {player}",
            f"/item replace entity {player} hotbar.0 with {CASING} 5",
            f"/item replace entity {player} hotbar.1 with {WRENCH}",
        ))
        multiplayer.until(f"{player} to reach the pump rig", lambda:
                          abs(actor.call("state")["player"]["position"][0] - 6.5) < .001
                          and current(actor, TRANSFER_PIPE)[0] == PIPE)
        start = host.clock()
        for row in expected:
            tick = int(row["tick"])
            phase = row["phase"]
            if tick and phase == "sample":
                host.step_to(start + tick)
            elif phase == "encase":
                use(actor, TRANSFER_PIPE, CASING)
            elif phase == "uncase":
                use(actor, TRANSFER_PIPE, WRENCH, height=.75)
            actual.append(sample(host, tick, phase))
    with args.output.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(expected[0])
        writer.writerows(actual)
    compare_transfer(actual)
    print(f"Matched all {len(actual)} Java pressure/flow/tank rows, including both casing transitions.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--transfer", action="store_true")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is None:
        suffix = "-lan" if args.lan else ""
        args.output = ROOT / f".local/encased-fluid-pipe-transfer{suffix}-horizon.csv"
    (transfer if args.transfer else static_states)(args)


if __name__ == "__main__":
    main()
