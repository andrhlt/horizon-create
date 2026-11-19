#!/usr/bin/env python3
"""Compare a survival player's Java seat landing and rebound on each physics tick."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
GUEST = "FallGuest"
SUPPORT_Y = 171
START_HEIGHT = 9.25
FIRST_TICK = 9


def same_state(row, sample):
    return (
        abs(sample["position"][1] - SUPPORT_Y - float(row["y"])) < 2e-7
        and abs(sample["velocity"][1] - float(row["vy"])) < 2e-7
        and sample["on_ground"] == (row["grounded"] == "true")
    )


def fall(host, actor, player, case, expected):
    host.command(f"/gamemode survival {player}")
    host.command("/tick unfreeze")
    crouched = case == "crouched-seat"
    if crouched:
        actor.call("key", "shift", "down")
        actor.call("wait", 2)
    try:
        warp = f"/tp {player} 9.5 {SUPPORT_Y + START_HEIGHT} 21.5"
        samples = "wait 1\nstate\n" * 39
        if host is actor:
            replies = actor.call("script", script=f'command "{warp}"\n{samples}')
        else:
            host.command(warp)
            replies = actor.call("script", script=samples)
    finally:
        if crouched:
            actor.call("key", "shift", "up")
    observed = [reply["player"] for reply in replies if "player" in reply]
    start = next((i for i, sample in enumerate(observed) if same_state(expected[0], sample)), None)
    if start is None:
        raise RuntimeError(f"{case} never reached the initial Java descent state at tick {FIRST_TICK}.")
    got = observed[start:start + len(expected)]
    if len(got) != len(expected):
        raise RuntimeError(f"{case} has {len(got)} comparable samples, wanted {len(expected)}.")
    for row, sample in zip(expected, got, strict=True):
        if not same_state(row, sample):
            dy = sample["position"][1] - SUPPORT_Y
            raise RuntimeError(f"{case} Java {row}, Horizon y={dy}, vy={sample['velocity'][1]}, "
                               f"grounded={sample['on_ground']}.")
    health = float(expected[-1]["health"])
    multiplayer.until(f"{case} health {health} to reach the client",
                      lambda: actor.call("state")["player"]["health"] == health)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/seat-fall-ticks-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    for case in ("stone", "seat", "crouched-seat"):
        block = "minecraft:stone" if case == "stone" else "create:red_seat"
        trace = [row for row in rows if row["kind"] == case and int(row["tick"]) >= FIRST_TICK]
        suffix = "lan" if args.lan else "solo"
        with fixture_world(args, f"Seat fall {case} {suffix}", render=True, pack=args.pack) as host:
            host.commands((
                "/fill 6 170 18 13 170 25 minecraft:stone",
                f"/setblock 9 {SUPPORT_Y} 21 {block}",
                "/gamerule fall_damage true",
            ))
            rule = host.command("/gamerule natural_health_regeneration false")
            if "false" not in rule:
                raise RuntimeError(f"Could not disable the control world's health regeneration: {rule}")
            if args.lan:
                port = host.call("lan", "open", 0, "commands", "force")["port"]
                with TemporaryDirectory(prefix="hc-fall-") as scratch, multiplayer.joined_client(
                    args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                    scenario="seat-fall", pack=args.pack,
                ) as actor:
                    multiplayer.until("the falling guest to join", lambda: any(
                        p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]
                    ))
                    fall(host, actor, GUEST, case, trace)
            else:
                fall(host, host, "@s", case, trace)
        print(f"{case} matched {len(trace)} Java player ticks and final health.", flush=True)


if __name__ == "__main__":
    main()
