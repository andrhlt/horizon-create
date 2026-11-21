#!/usr/bin/env python3
"""Check filtered Smart Observer storage, power, and settings across a cold reopen."""

import argparse
import csv
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

observer = import_module("test-smart-observer-filter")
multiplayer = import_module("test-multiplayer")
CHEST = (9, 102, -8)
LAMPS = tuple((x, y + 1, z) for x, y, z in observer.POS)
GUEST = "ObserverGuest"
FILTER = ("minecraft:stone", 3)


def setup(host):
    host.commands((
        "/fill 4 100 -14 15 100 -5 minecraft:smooth_stone",
        "/fill 4 101 -14 15 108 -5 minecraft:air",
        "/setblock 8 102 -8 minecraft:chest[facing=north,type=left]",
        "/setblock 9 102 -8 minecraft:chest[facing=north,type=right]",
        "/setblock 13 102 -8 minecraft:barrel",
        "/item replace block 8 102 -8 container.0 with minecraft:dirt 8",
        "/item replace block 13 102 -8 container.0 with minecraft:dirt 8",
        *(f"/setblock {observer.editor.xyz(pos)} {observer.state('south', 'wall')}"
          for pos in observer.POS),
        *(f"/setblock {observer.editor.xyz(pos)} minecraft:redstone_lamp" for pos in LAMPS),
    ))
    assert "type=left" in host.call("block", 8, 102, -8)["state"]
    assert "type=right" in host.call("block", *CHEST)["state"]


@contextmanager
def actor_for(host, args, scratch, phase):
    if scratch is None:
        yield host, "@s"
        return
    port = host.call("lan", "open", "0", "commands", "force")["port"]
    phase_dir = scratch / phase
    phase_dir.mkdir()
    with multiplayer.joined_client(
        args, phase_dir, f"127.0.0.1:{port}", GUEST,
        render=True, scenario=f"smart-observer-{phase}", pack=args.pack,
    ) as guest:
        multiplayer.until("the Observer guest to join", lambda: any(
            player["name"] == GUEST and player["placed"]
            for player in host.call("lan", "status")["guests"]
        ))
        host.command(f"/tp {GUEST} 11.5 101 -11.5")
        yield guest, GUEST


def state_matches(control, lane, powered):
    return all(
        f"{key}={str(powered).lower()}" in control.call("block", *pos)["state"]
        for key, pos in (("powered", observer.POS[lane]), ("lit", LAMPS[lane]))
    )


def verify_power(host, actor, lane, powered):
    for peer in (host,) if host is actor else (host, actor):
        multiplayer.until(
            f"lane {lane} Observer and lamp to be {'on' if powered else 'off'}",
            lambda: state_matches(peer, lane, powered),
        )


def step(host, ticks):
    start = host.clock()
    for tick in range(1, ticks + 1):
        host.step_to(start + tick)


def set_far_chest(host, item, count):
    pos = observer.editor.xyz(CHEST)
    result = host.command(f"/item replace block {pos} container.0 with {item}")
    assert "Replaced 1 slot" in result, result
    assert far_chest_count(host) == count


def far_chest_count(host):
    stored = host.command(f"/data get block {observer.editor.xyz(CHEST)}")
    return observer.editor.field(stored, "count", 0)


def verify_java_sample(host, expected):
    data = observer.filters.read(host, observer.POS[0])
    actual = {
        "filter_count": str(observer.filters.filter_data(data)[1]),
        "far_count": str(far_chest_count(host)),
        "turn_off": str(observer.editor.field(data, "TurnOff", 0)),
        "powered": str("powered=true" in host.call("block", *observer.POS[0])["state"]).lower(),
        "lit": str("lit=true" in host.call("block", *LAMPS[0])["state"]).lower(),
    }
    assert actual == expected, (expected, actual)


def verify_filter(host):
    for pos in observer.POS:
        data = observer.filters.read(host, pos)
        assert observer.filters.filter_data(data) == FILTER, (pos, data)


def replay(args, scratch=None):
    suffix = "LAN" if scratch else "Solo"
    with (ROOT / "fixtures/smart-observer-double-chest-java.csv").open(newline="") as source:
        expected = {int(row.pop("tick")): row for row in csv.DictReader(source)}
    with fixture_world(
        args, f"SmartObserverLifecycle{suffix}", render=scratch is None, pack=args.pack,
    ) as host:
        setup(host)
        with actor_for(host, args, scratch, "configure") as (actor, name):
            host.command(f"/gamemode survival {name}")
            for pos in observer.POS:
                observer.set_filter(host, actor, name, pos, *FILTER)
            verify_filter(host)
            step(host, 8)
            for lane in range(len(observer.POS)):
                verify_power(host, actor, lane, False)
            verify_java_sample(host, expected[0])
            set_far_chest(host, "minecraft:stone 1", 1)
            step(host, 2)
            verify_java_sample(host, expected[2])
            verify_power(host, actor, 0, True)
            verify_power(host, actor, 1, False)

        host.restart()
        with actor_for(host, args, scratch, "rejoin") as (actor, _):
            verify_filter(host)
            verify_java_sample(host, expected[2])
            verify_power(host, actor, 0, True)
            verify_power(host, actor, 1, False)

            set_far_chest(host, "minecraft:air", 0)
            step(host, 12)
            verify_java_sample(host, expected[14])
            verify_power(host, actor, 0, False)
            set_far_chest(host, "minecraft:stone 1", 1)
            step(host, 2)
            verify_java_sample(host, expected[16])
            verify_power(host, actor, 0, True)
            verify_power(host, actor, 1, False)
    print(f"{suffix}: both filters survived cold reopen; a single item in the far chest half "
          "powered the Observer and lamp before and after reopen, and removal cleared both.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-obs-") as scratch:
            replay(args, Path(scratch))
    else:
        replay(args)


if __name__ == "__main__":
    main()
