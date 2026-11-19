#!/usr/bin/env python3
"""Replay experience nugget uses, original recipes and a survival placement."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from math import dist, isclose
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

crafting = import_module("test-machine-crafting")
multiplayer = import_module("test-multiplayer")

NUGGET = "create:experience_nugget"
ORB = "minecraft:experience_orb"
GUEST = "ExperienceGuest"
ENV = {"HORIZON_NO_AUDIO": "1", "CREATE_EXPERIENCE_TRACE": "1"}
TRACE = "CREATE_EXPERIENCE_RELEASE "


def reference(kind):
    with (ROOT / "fixtures" / f"experience-{kind}-java.csv").open(newline="") as source:
        return list(csv.DictReader(source))


def craft_and_place(args):
    with fixture_world(args, "ExperienceCraftingPlacement", render=True, pack=args.pack, env=ENV) as host:
        host.commands((
            "/fill 8 169 22 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
            "/gamemode survival",
        ))
        for row in reference("crafting"):
            crafting.replay(host, {**row, "slots": row["inputs"].replace("|", ","), "remainder": ""})
        specs, = reference("block")
        host.commands((
            f'/item replace entity @s hotbar.0 with {specs["id"]}',
            "/setblock 12 170 24 minecraft:air",
        ))
        host.call("select", specs["id"])
        host.call("look-at", 12.5, 170, 24.5)
        host.call("interact", 12, 169, 24, "up")
        placed = host.call("block", 12, 170, 24)
        remaining = host.call("inventory")["counts"].get(specs["id"], 0)
        assert placed["state"] == specs["id"] and remaining == int(specs["item_count"]), (placed, remaining)
        for _ in range(2):
            host.step_to(host.clock() + 1)
        multiplayer.until("the experience block to emit its original light level", lambda:
                          int(host.call("light", 12, 170, 24, 12, 170, 24)["block"], 16) == int(specs["light"]))
    print("Both original experience recipes, survival placement and light level matched Java.")


def read_release(log, offset):
    lines = log.read_bytes()[offset:].decode(errors="replace").splitlines()
    return [line.split(TRACE, 1)[1].split(",") for line in lines if TRACE in line]


def orb_values(actor):
    return sorted(e["value"] for e in actor.call("entities", 12, ORB)["entities"])


def position_player(host, actor, player, pos):
    host.command(f"/tp {player} {' '.join(map(str, pos))} 33 -12")
    multiplayer.until(f"{player} to reach the throw position", lambda:
                      actor.call("state")["player"]["position"] == list(pos))
    actor.call("look", 33, -12)
    actor.call("wait", 3)


def wait_posture(host, actor, player, sneaking):
    def ready():
        state = actor.call("state")["player"]
        pose = "CROUCHING" if sneaking else "STANDING"
        if state["sneaking"] != sneaking or state["pose"] != pose:
            return False
        if actor is host:
            return True
        return any(guest["name"] == player and guest["sneaking"] == sneaking
                   for guest in host.call("lan", "status")["guests"])

    multiplayer.until(f"{player} to {'crouch' if sneaking else 'stand'}", ready)


def exercise(host, actor, player, pos, peers):
    position_player(host, actor, player, pos)
    initial_orbs = {}
    for row in reference("orb"):
        initial_orbs.setdefault((row["sneaking"], row["count"]), []).append(row)
    actual_cases = []
    for row in reference("use"):
        sneaking = row["sneaking"] == "true"
        count, remaining = int(row["count"]), int(row["remaining"])
        expected = initial_orbs[(row["sneaking"], row["count"])]
        values = sorted(int(entry["value"]) for entry in expected)
        host.command(f"/item replace entity {player} hotbar.0 with {NUGGET} {count}")
        actor.call("select", 1)
        multiplayer.until(f"{player} to receive the initial stack", lambda:
                          actor.call("inventory")["counts"].get(NUGGET, 0) == count)
        log = host.socket.parent / "ctl.log"
        offset = log.stat().st_size
        if sneaking:
            actor.call("key", "shift", "down")
        try:
            if sneaking:
                wait_posture(host, actor, player, True)
            actor.call("use-item")
            multiplayer.until(f"{player}'s release data to reach the log", lambda:
                              len(read_release(log, offset)) >= len(values))
        finally:
            if sneaking:
                actor.call("key", "shift", "up")
        if sneaking:
            wait_posture(host, actor, player, False)
        negative_values = {value for value in values if value < 0}
        if negative_values and len(peers) > 1:
            observer, = [peer for peer in peers if peer is not actor]
            if negative_values.issubset(orb_values(observer)):
                print(f"The peer observed {player}'s signed orb values {sorted(negative_values)}.", flush=True)
        multiplayer.until(f"{player} to retain {remaining} experience nuggets", lambda:
                          actor.call("inventory")["counts"].get(NUGGET, 0) == remaining)
        actual = read_release(log, offset)
        if len(actual) != len(expected):
            raise RuntimeError(f"{player}, sneak={sneaking}, count={count}: released {actual}, Java {expected}")
        look = tuple(float(row[f"look_{axis}"]) for axis in "xyz")
        baseline = (look[0] * .2, look[1] * .2 + .2, look[2] * .2)
        for want, got in zip(expected, actual, strict=True):
            keys = ("sneaking", "count", "index", "value", "merged_count")
            fields = (got[0], got[1], *got[3:6])
            if fields != tuple(want[key] for key in keys) or int(got[2]) != remaining:
                raise RuntimeError(f"{player}, sneak={sneaking}, count={count}: release row {got}, Java {want}")
            expected_position = tuple(float(want[axis]) for axis in "xyz")
            relative_position = tuple(map(float, got[6:9]))
            if dist(relative_position, expected_position) > 2e-9:
                raise RuntimeError(f"{player}, sneak={sneaking}, count={count}, orb={got[4]}: "
                                   f"position {relative_position}; Java {expected_position}")
            velocity = tuple(map(float, got[9:]))
            if not isclose(dist(velocity, baseline), 0.1, abs_tol=2e-12, rel_tol=0.0):
                raise RuntimeError(f"{player}, sneak={sneaking}, count={count}, orb={got[4]}: "
                                   f"motion {velocity} is outside Java's .1 jitter radius around {baseline}")
        actual_cases.append((sneaking, count, count - remaining, values))
        host.command(f"/kill @e[type={ORB}]")
        for peer in peers:
            multiplayer.until("the previous test orbs to despawn", lambda: not orb_values(peer))
    print(f"{player} matched {len(actual_cases)} Java use cases, {sum(len(x[3]) for x in actual_cases)} signed "
          f"orbs, spawn positions and the launch velocity envelope.")


def uses(args):
    name = "ExperienceNuggetLAN" if args.lan else "ExperienceNugget"
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, name, pack=args.pack, env=ENV))
        host.commands((
            "/fill 7 169 22 16 169 28 minecraft:stone",
            "/fill 7 170 22 16 174 28 minecraft:air",
            "/tp @s 9.5 170 26.5",
            "/gamemode survival",
        ))
        guest = None
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-experience-")))
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", GUEST,
                scenario=name, pack=args.pack, env=ENV,
            ))
            multiplayer.until("the guest to join", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            position_player(host, guest, GUEST, (12.5, 170, 26.5))
            host.command(f"/gamemode survival {GUEST}")
        peers = (host, guest) if guest else (host,)
        exercise(host, host, "@s", (9.5, 170, 26.5), peers)
        if guest:
            exercise(host, guest, GUEST, (12.5, 170, 26.5), peers)
    print("Verified throws through the actual use-item input and initial authoritative orb data.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--lan", action="store_true")
    mode.add_argument("--craft-and-place", action="store_true")
    args = parser.parse_args()
    if args.craft_and_place:
        craft_and_place(args)
    else:
        uses(args)


if __name__ == "__main__":
    main()
