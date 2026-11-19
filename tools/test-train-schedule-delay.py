#!/usr/bin/env python3
"""Edit a Java Schedule delay and preserve other conditions and progress."""
import argparse
import json
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

entry = import_module("test-train-schedule-entry")
conductor = import_module("test-train-conductor")
multiplayer = conductor.multiplayer
GUEST = "DelayEditor"
COMPONENT = "create:train_schedule"
ADVANCED = ('{Cyclic:1b,Progress:1,Entries:[{Conditions:[[{Id:"create:powered",'
            'Data:{}}],[{Id:"create:time_of_day",Data:{Hour:6,Minute:30,Rotation:8}}]],'
            'Instruction:{Id:"create:destination",Data:{Text:"Waiting Station"}},Extra:"keep"},'
            '{Conditions:[[{Id:"create:delay",Data:{TimeUnit:1,Value:6}}]],'
            'Instruction:{Id:"create:destination",Data:{Text:"Harbor"}}}],Version:"keep"}')


def scroll(actor, label, direction, count=1):
    control = entry.buttons(actor)[label]
    x = int(control["x"] + control["w"] / 2)
    y = int(control["y"] + control["h"] / 2)
    actor.call("script", script=f"scroll-at {x} {y} {direction}\n" * count)
    actor.call("wait", 2)


def check_saved(world, actor, who, wanted):
    multiplayer.until("the Schedule component to reach the authority",
                      lambda: entry.selected_schedule(world, who) == wanted)
    multiplayer.until("the Schedule component to reach the client",
                      lambda: entry.client_schedule(actor) == wanted)


def prepare_item(world, actor, who):
    world.command(f"/attribute {who} minecraft:gravity base set 0")
    world.command(f"/item replace entity {who} hotbar.0 with create:schedule")
    actor.call("key", "1", "tap")
    actor.call("wait", 5)


def exercise(world, actor, who, empty, first, last, lower):
    prepare_item(world, actor, who)
    entry.enter_and_close(actor, empty)
    check_saved(world, actor, who, empty)

    entry.use(actor)
    actor.call("click-button", "Wait: 5s")
    scroll(actor, "Duration", 1, 3)
    scroll(actor, "Time Unit", -1)
    actor.call("click-button", "Confirm Condition")
    assert entry.buttons(actor)["Wait: 8min"]["enabled"]
    actor.call("click-button", "Done")
    actor.call("wait", 8)
    check_saved(world, actor, who, first)

    entry.use(actor)
    actor.call("click-button", "Wait: 8min")
    scroll(actor, "Duration", 1, 135)
    scroll(actor, "Time Unit", 1, 3)
    actor.call("click-button", "Confirm Condition")
    assert entry.buttons(actor)["Wait: 120t"]["enabled"]
    actor.call("click-button", "Done")
    actor.call("wait", 8)
    check_saved(world, actor, who, last)

    entry.use(actor)
    actor.call("click-button", "Wait: 120t")
    scroll(actor, "Duration", -1, 135)
    scroll(actor, "Time Unit", -1)
    actor.call("click-button", "Confirm Condition")
    assert entry.buttons(actor)["Wait: 0s"]["enabled"]
    actor.call("click-button", "Done")
    actor.call("wait", 8)
    check_saved(world, actor, who, lower)

    conductor.set_held(world, actor, who, conductor.SCHEDULE,
                       components='{"create:train_schedule":' + ADVANCED + "}")
    wanted = entry.snbt(ADVANCED)
    check_saved(world, actor, who, wanted)
    entry.use(actor)
    actor.call("click-button", "Waiting Station")
    actor.call("click-button", "Station Name")
    actor.call("key", "ctrl", "down")
    actor.call("key", "a", "tap")
    actor.call("key", "ctrl", "up")
    actor.call("type", "Depot *")
    actor.call("click-button", "Confirm Action")
    actor.call("click-button", "Loop Forever")
    actor.call("click-button", "Done")
    actor.call("wait", 8)
    wanted["Cyclic"] = 0
    wanted["Entries"][0]["Instruction"]["Data"]["Text"] = "Depot *"
    check_saved(world, actor, who, wanted)
    entry.use(actor)
    assert entry.buttons(actor)["Depot *"]["enabled"]
    actor.call("click-button", "Done")
    actor.call("wait", 8)
    check_saved(world, actor, who, wanted)


def run(args):
    expected = json.loads((ROOT / "fixtures/train-schedule-delay-java.json").read_text())
    name = "train-schedule-delay-lan" if args.multiplayer else "train-schedule-delay"
    with fixture_world(args, name, render=True, pack=args.pack) as world:
        world.commands((
            "/fill 4 95 36 15 95 46 minecraft:smooth_stone",
            "/tp @s 8.5 96 41.3 -90 -25",
            "/gamemode survival",
        ))
        rows = tuple(expected[name] for name in ("initial", "edited", "boundary", "lower_bound"))
        if not args.multiplayer:
            exercise(world, world, "@s", *rows)
            return
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-delay-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST,
            render=True, scenario=name, pack=args.pack,
        ) as guest:
            multiplayer.until("the guest delay editor to join", lambda: any(
                link["name"] == GUEST and link["placed"] for link in world.call("lan", "status")["guests"]
            ))
            world.commands((f"/gamemode survival {GUEST}", f"/tp {GUEST} 10.5 96 41.3 -90 -25"))
            guest.call("wait", 5)
            exercise(world, guest, GUEST, *rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
    print("Duration and time unit edits match the Java Schedule; unrelated conditions and progress survived rename, toggle and reopen.")
