#!/usr/bin/env python3
"""Pour and recover both original placeable Create fluids with survival buckets."""
import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")


def run(args):
    env = {"HORIZON_NO_AUDIO": "1"}
    scenario = "PlacedCreateFluidsLan" if args.lan else "PlacedCreateFluidsSolo"
    with ExitStack() as scope:
        world = scope.enter_context(fixture_world(args, scenario, pack=args.pack, env=env))
        actor, name = world, "@s"
        if args.lan:
            port = world.call("lan", "open", "0", "commands", "force")["port"]
            name = "LiquidsGuest"
            scratch = Path(scope.enter_context(TemporaryDirectory(prefix="hc-liquids-")))
            actor = scope.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", name,
                scenario=scenario, pack=args.pack, env=env))
            mp.until("the guest to join", lambda: any(guest["name"] == name and guest["placed"]
                     for guest in world.call("lan", "status")["guests"]))
        world.commands((
            "/fill 5 169 19 15 169 27 minecraft:stone",
            "/fill 5 170 19 15 173 27 minecraft:air",
            f"/gamemode survival {name}",
        ))
        for index, liquid in enumerate(("honey", "chocolate")):
            x = 8 + 4 * index
            source = f"create:{liquid}"
            bucket = f"{source}_bucket"
            world.commands((
                f"/clear {name}",
                f"/tp {name} {x + .5} 170 24.5 180 30",
                f"/item replace entity {name} hotbar.0 with {bucket}",
            ))
            mp.until(f"{bucket} to reach the player", lambda: mp.count(actor, bucket) == 1)
            mp.until("the player and floor to synchronize", lambda:
                     actor.call("state")["player"]["position"] == [x + .5, 170, 24.5]
                     and actor.call("block", x, 169, 21)["block"] == "minecraft:stone")
            actor.call("select", 1)
            actor.call("interact", x, 169, 21, "up")
            mp.until(f"the {liquid} source", lambda:
                     world.call("block", x, 170, 21)["state"] == f"{source}[level=0]")
            mp.until(f"pouring {liquid} to return a bucket", lambda: mp.count(actor, "minecraft:bucket") == 1)
            mp.until(f"the player to see the {liquid} source", lambda:
                     actor.call("block", x, 170, 21)["state"] == f"{source}[level=0]")
            actor.call("look-at", x + .5, 170.5, 21.5)
            actor.call("mouse", "right", "click")
            mp.until(f"recovery to return {bucket}", lambda: mp.count(actor, bucket) == 1)
            mp.until(f"the recovered {liquid} source to disappear", lambda:
                     world.call("block", x, 170, 21)["block"] == "minecraft:air")
            print(f"A survival player poured and recovered the original {liquid} bucket.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    run(parser.parse_args())
