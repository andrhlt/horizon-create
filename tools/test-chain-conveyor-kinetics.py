#!/usr/bin/env python3
"""Check the original conveyor endpoint speeds with persisted chain links in a headless Horizon world."""

import argparse
import csv
import importlib
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


def coords(pos):
    return " ".join(map(str, pos))


def set_link(control, pos, delta=None):
    tag = "[]" if delta is None else "[[I;" + ",".join(map(str, delta)) + "]]"
    control.command(f"/data merge block {coords(pos)} {{Connections:{tag}}}")


def speeds(control, ends):
    readings = control.commands(f"/data get block {coords(pos)}" for pos in ends)
    try:
        return tuple(float(re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)f\b", value)[1])
                     for value in readings)
    except TypeError as e:
        raise RuntimeError(f"Missing Speed in endpoint data {readings}") from e


def check(args, name, delta, expected):
    a = (8, 102, -10)
    b = tuple(p + d for p, d in zip(a, delta))
    motor = (a[0], a[1] - 1, a[2])
    frogport = (b[0], b[1] + 1, b[2] + 1)
    with fixture_world(args, f"ChainConveyor-{name}", pack=args.pack) as control:
        control.commands((
            "/fill 6 101 -12 16 105 -5 minecraft:air",
            f"/setblock {coords(a)} create:chain_conveyor",
            f"/setblock {coords(b)} create:chain_conveyor",
            f"/setblock {coords(frogport)} create:package_frogport",
            f"/setblock {coords(motor)} create:creative_motor[facing=up]",
            f"/data merge block {coords(motor)} {{ScrollValue:128}}",
        ))
        for pos, block in ((a, "chain_conveyor"), (b, "chain_conveyor"), (frogport, "package_frogport")):
            registered = control.call("block", *pos)["state"]
            if registered != f"create:{block}":
                raise RuntimeError(f"Expected {block} at {pos}, got {registered}")

        def sample(label, want):
            control.step_to(control.clock() + 1)
            actual = speeds(control, (a, b))
            if actual != want:
                raise RuntimeError(f"{name} {label}: expected {want}, got {actual}")
            print(f"{name} {label}: {actual}")

        sample("no chain", (128.0, 0.0))
        set_link(control, a, delta)
        sample("one-sided link", (128.0, 0.0))
        set_link(control, b, tuple(-d for d in delta))
        sample("connected", expected[0])
        if name == "rising_reversal":
            control.command(f"/data merge block {coords(motor)} {{ScrollValue:-128}}")
            sample("reversed", expected[12])
            control.command(f"/setblock {coords(motor)} minecraft:air")
            sample("power removed", expected[32])
            control.command(f"/setblock {coords(motor)} create:creative_motor[facing=up]")
            sample("default restart", expected[40])
            control.command(f"/data merge block {coords(motor)} {{ScrollValue:128}}")
            sample("full speed restored", expected[42])
        set_link(control, a)
        set_link(control, b)
        sample("disconnected", expected[76 if name == "straight" else 63])


def check_player(args):
    multiplayer = importlib.import_module("test-multiplayer")
    chain = "minecraft:iron_chain"
    a, b = (8, 102, -10), (15, 102, -10)
    slot = "weapon.offhand" if args.offhand else "hotbar.0"
    insufficient, connected = 1, 13
    if args.offhand:
        with (ROOT / "fixtures/chain-conveyor-offhand-java.csv").open() as stream:
            states = {row["action"]: row for row in csv.DictReader(stream) if row["scenario"] == "straight"}
        insufficient, connected = (int(states[test]["offhand_count"]) for test in ("insufficient", "connected"))
        assert all(state["main_empty"] == "true" for state in states.values())

    def connect(host, actor, name):
        def count():
            if not args.offhand:
                return multiplayer.count(actor, chain)
            hand = host.command(f"/data get entity {name} equipment.offhand").partition("entity data: ")[2]
            match = re.search(r"\bcount:\s*(\d+)", hand)
            return int(match[1]) if chain in hand and match else 0

        def select(pos):
            x, y, z = pos
            player_pos = [x + 0.5, y + 1.0, z + 1.5]
            host.command(f"/tp {name} {coords(player_pos)}")
            multiplayer.until("player to reach the conveyor", lambda:
                actor.call("state")["player"]["position"] == player_pos and
                actor.call("block", *pos)["block"] == "create:chain_conveyor")
            if not args.offhand:
                actor.call("select", chain)
            actor.call("look-at", x + 0.5, y + 0.95, z + 0.5)
            aim = actor.call("state")["looking_at"]
            assert aim["kind"] == "block" and aim["block"]["pos"] == list(pos), aim
            click = actor.call("use-item")
            assert count() != 0, (
                aim, click, host.command(f"/clear {name} {chain} 0"),
                host.call("block", x, y + 1, z), actor.call("state")["looking_at"],
            )
            return click

        def has_link(at):
            tag = host.command(f"/data get block {coords(at)}")
            return "Connections:" in tag

        host.command(f"/gamemode survival {name}")
        host.command(f"/item replace entity {name} {slot} with {chain}")
        multiplayer.until("one chain in player inventory", lambda: count() == 1)
        clicks = (select(a), select(b))
        host.step_to(host.clock() + 1)
        assert count() == insufficient, (actor.call("inventory"), clicks)
        assert not any(map(has_link, (a, b)))
        assert speeds(host, (a, b)) == (128.0, 0.0)

        host.command(f"/item replace entity {name} {slot} with {chain} 16")
        multiplayer.until("sixteen chains in player inventory", lambda: count() == 16)
        select(a)
        select(b)
        multiplayer.until("both endpoints connected and three chains spent", lambda:
            all(map(has_link, (a, b))) and count() == connected)
        host.step_to(host.clock() + 1)
        assert speeds(host, (a, b)) == (128.0, 128.0)
        if args.offhand:
            main = host.command(f"/data get entity {name} equipment.mainhand").partition("entity data: ")[2]
            assert not main or main == "{}" or 'id: "minecraft:air"' in main, main
        print(f"{name}: one chain refused; sixteen established both links and left {connected}.")

        clicks = (select(a), select(b))
        host.step_to(host.clock() + 1)
        assert count() == connected, ("duplicate connection consumed additional chain", clicks)

    label = "LAN" if args.lan else "Solo"
    if args.offhand:
        label += "Offhand"
    with fixture_world(args, f"ChainConveyorPlayer-{label}", pack=args.pack) as host:
        host.commands((
            "/fill 6 102 -11 17 105 -6 minecraft:air",
            "/fill 6 101 -11 17 101 -6 minecraft:stone",
            "/setblock 8 102 -9 minecraft:stone",
            "/setblock 15 102 -9 minecraft:stone",
            f"/setblock {coords(a)} create:chain_conveyor",
            f"/setblock {coords(b)} create:chain_conveyor",
            "/setblock 8 101 -10 create:creative_motor[facing=up]",
            "/data merge block 8 101 -10 {ScrollValue:128}",
        ))
        if not args.lan:
            connect(host, host, "@s")
            return
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-conveyor-guest-") as scratch:
            with multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", "ConveyorGuest",
                scenario="chain-conveyor-connect", pack=args.pack,
            ) as guest:
                multiplayer.until("guest to enter the world", lambda: any(
                    entry["name"] == "ConveyorGuest" and entry["placed"]
                    for entry in host.call("lan", "status")["guests"]
                ))
                connect(host, guest, "ConveyorGuest")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--player", action="store_true", help="use survival player interaction")
    parser.add_argument("--lan", action="store_true", help="use a headless guest for player interaction")
    parser.add_argument("--offhand", action="store_true", help="connect the two wheels with an empty main hand")
    args = parser.parse_args()
    if args.player or args.lan or args.offhand:
        check_player(args)
        return
    expected = {}
    with (ROOT / "fixtures/chain-conveyor-world-java.csv").open() as csv_file:
        for row in csv.DictReader(csv_file):
            expected.setdefault(row["scenario"], {})[int(row["tick"])] = (
                float(row["a_rpm"]), float(row["b_rpm"]),
            )
    with (ROOT / "fixtures/chain-conveyor-connection-java.csv").open() as csv_file:
        for row in csv.DictReader(csv_file):
            if row["action"] == "connected":
                name = row["scenario"]
                check(args, name, tuple(map(int, row["edge"].split(":"))), expected[name])


if __name__ == "__main__":
    main()
