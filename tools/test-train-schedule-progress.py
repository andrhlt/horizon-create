#!/usr/bin/env python3
"""Verify original Train Schedule reset and skip buttons through real play."""
import argparse
import json
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

entry = import_module("test-train-schedule-entry")
conductor = import_module("test-train-conductor")
multiplayer = conductor.multiplayer
GUEST = "ProgressGuest"

def exercise(world, actor, who, expected):
    world.command(f"/attribute {who} minecraft:gravity base set 0")
    starting = json.dumps(expected["start"], separators=(",", ":")).replace('"Cyclic":0', '"Cyclic":0b')
    conductor.set_held(world, actor, who, conductor.SCHEDULE,
                       components='{"create:train_schedule":' + starting + "}")
    for previous, label, step in (
        ("start", "Skip current Stop", "wrapped"),
        ("wrapped", "Skip current Stop", "skipped"),
        ("skipped", "Reset Progress", "reset"),
    ):
        multiplayer.until("the expected starting schedule", lambda: entry.selected_schedule(world, who) == expected[previous])
        entry.use(actor)
        buttons = entry.buttons(actor)
        if not buttons["Skip current Stop"]["enabled"] or buttons["Reset Progress"]["enabled"] != ("Progress" in expected[previous]):
            raise RuntimeError(f"Wrong enabled state when opening at {previous}: {buttons}")
        actor.call("click-button", label)
        actor.call("wait", 2)
        if entry.buttons(actor)["Reset Progress"]["enabled"] != ("Progress" in expected[step]):
            raise RuntimeError(f"Reset Progress enabled state did not follow {step}.")
        actor.call("click-button", "Done")
        actor.call("wait", 7)
        multiplayer.until("the exact progressed schedule in server inventory",
                          lambda: entry.selected_schedule(world, who) == expected[step])
        multiplayer.until("the exact progressed schedule in client inventory",
                          lambda: entry.client_schedule(actor) == expected[step])


def run(args):
    expected = json.loads((ROOT / "fixtures/train-schedule-progress-java.json").read_text())
    scenario = "Schedule-progress-LAN" if args.multiplayer else "Schedule-progress"
    with fixture_world(args, scenario, render=True, pack=args.pack) as world:
        world.commands((
            "/fill 4 95 36 15 95 46 minecraft:smooth_stone",
            "/tp @s 8.5 96 41.3 -90 -25",
            "/gamemode survival",
        ))
        if not args.multiplayer:
            exercise(world, world, "@s", expected)
            return
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-progress-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST,
            render=True, scenario=scenario, pack=args.pack,
        ) as guest:
            multiplayer.until("the progress guest", lambda: any(
                link["name"] == GUEST and link["placed"] for link in world.call("lan", "status")["guests"]
            ))
            world.commands((f"/gamemode survival {GUEST}", f"/tp {GUEST} 10.5 96 41.3 -90 -25"))
            guest.call("wait", 5)
            exercise(world, guest, GUEST, expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
    print("Original Skip Current Stop wrapping, reset eligibility and saved progress matched Java.")
