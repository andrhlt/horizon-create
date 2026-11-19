#!/usr/bin/env python3
"""Compare Java's Package as the receiver of a survival player's push."""
import argparse
import csv
from contextlib import ExitStack
import math
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
placement = import_module("test-package-placement")
throw = import_module("test-package-throw")
BOX = "@e[type=create:package,tag=OwnedPackage,limit=1]"
HEIGHTS = {"level": 0.0, "above": 0.25, "clear": 0.55}
PLAYER_X = 8.699999988079071
ORIGIN = (8.3, 105.0, -11.5)


def replay(host, player, actor, case, expected):
    y = 105 + HEIGHTS[case]
    host.commands((
        "/fill 5 104 -15 12 109 -8 minecraft:air",
        "/fill 5 104 -15 12 104 -8 minecraft:obsidian",
        "/fill 9 105 -12 9 107 -11 minecraft:obsidian",
        f"/gamemode survival {player}",
        f"/attribute {player} minecraft:gravity base set 0",
        f"/tp {player} {PLAYER_X} {y} -11.5",
    ))
    mp.until("the player to reach the contact point", lambda:
             actor.call("state")["player"]["position"] == [PLAYER_X, y, -11.5])
    position = ' '.join(map(str, ORIGIN))
    host.command(f'/summon create:package {position} {{Tags:["OwnedPackage"],'
                 'NoGravity:1b,Health:5f,Fire:-1s,CreatePackageTossedBy:[I;183,281,313,521],'
                 'equipment:{mainhand:{id:"create:cardboard_package_10x8",count:1}}}')
    mp.until("the actor to see the Package", lambda: len(placement.witness(actor)) == 1)
    start = host.clock()
    differences = []
    for tick in range(8):
        if tick:
            host.step_to(start + tick)
        state = actor.call("state")["player"]["position"]
        owned = "entity data:" in host.command(f"/data get entity {BOX} CreatePackageTossedBy")
        position = throw.package_vector(host, "Pos", BOX)
        motion = throw.package_vector(host, "Motion", BOX)
        dx = position[0] - ORIGIN[0]
        want = expected[tick]
        print(tick, str(owned).lower(), repr(dx), repr(motion[0]), tuple(state), "java", want, flush=True)
        if (
            owned != want[0]
            or not math.isclose(dx, want[1], rel_tol=0, abs_tol=2e-8)
            or not math.isclose(motion[0], want[2], rel_tol=0, abs_tol=2e-8)
            or position[1:] != ORIGIN[1:]
            or motion[1:] != (0.0, 0.0)
        ):
            differences.append(tick)
    print(f"{case}: compared {len(expected)} rows, differing ticks {differences}", flush=True)
    return not differences


def run_case(args, case, expected):
    scenario = f"PackagePlayerContact{case}" + ("LAN" if args.lan else "")
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, scenario, pack=args.pack))
        actor, player = host, "@s"
        if args.lan:
            player = "PkgGuest"
            host.command("/tp @s 11 101 -7.5")
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            directory = Path(stack.enter_context(TemporaryDirectory(prefix="hc-pc-")))
            actor = stack.enter_context(mp.joined_client(
                args, directory, f"127.0.0.1:{port}", player, scenario=scenario, pack=args.pack,
            ))
            mp.until("the guest to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]
            ))
        return replay(host, player, actor, case, expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ("ctl", "client", "resources"):
        parser.add_argument(role, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--case", choices=HEIGHTS)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/package-player-contact-java.csv")
    args = parser.parse_args()
    cases = (args.case,) if args.case else HEIGHTS
    with args.reference.open(newline="") as source:
        rows = list(csv.DictReader(source))
    outcomes = []
    for case in cases:
        expected = {
            int(row["tick"]): (
                row["owned"] == "true", float(row["package_dx"]), float(row["package_vx"]),
            )
            for row in rows if row["case"] == case
        }
        assert len(expected) == 8
        outcomes.append(run_case(args, case, expected))
    print(f"Compared {8 * len(outcomes)} original Package player contact ticks.", flush=True)
    raise SystemExit(not all(outcomes))


if __name__ == "__main__":
    main()
