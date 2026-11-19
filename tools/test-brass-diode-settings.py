#!/usr/bin/env python3
"""Compare real Pulse Timer value-board input with the Java timings oracle."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
import os
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
TIMER = (8, 120, -8)
COORDS = " ".join(map(str, TIMER))
LABELS = ("Ticks", "Seconds", "Minutes")


def sample(world):
    data = world.command(f"/data get block {COORDS}")
    return tuple(int(re.search(rf"\b{key}: (-?\d+)", data)[1]) for key in ("ScrollValue", "State"))


def choose(actor, row, value):
    actor.call("look-at", 8.5, 120.115, -7.5)
    hit = actor.call("looking-at")["block"]
    if not hit or hit["pos"] != list(TIMER) or hit["face"] != "up":
        raise RuntimeError(f"Expected the center value slot on top of the Pulse Timer: {hit}")
    actor.call("script", script="mouse right down\nwait 7\n")
    buttons = actor.call("screen")["buttons"]
    bars = [button for button in buttons if button["label"] in LABELS]
    if [bar["label"] for bar in bars] != list(LABELS):
        raise RuntimeError(f"The three Java timing rows did not open: {buttons}.")
    bar = bars[row]
    x = bar["x"] + ((max(value, 1) - 1) // 10) * 4 + value * 2 + 1.5
    x += 2 if value % 10 == 0 else 0
    x += 4 if value else 0
    y = bar["y"] + bar["h"] / 2
    actor.call("scroll-at", x, y, 0)
    actor.call("click-at", x, y, "right")
    actor.call("wait", 4)
    if actor.call("state")["screen"] != "playing":
        raise RuntimeError("Releasing Use did not close the Redstone Interval board.")


def main():
    os.environ["CREATE_SPEED_CONTROLLER_INPUT_TRACE"] = "1"
    os.environ.setdefault("HORIZON_NO_AUDIO", "1")
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/brass-diode-settings-java.csv").open(newline="") as stream:
        expected = list(csv.DictReader(stream))
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, "PulseTimerSettingsLAN" if args.lan else "PulseTimerSettings", render=True, pack=args.pack))
        world.commands((
            "/fill 5 119 -10 11 119 -5 minecraft:smooth_stone",
            "/fill 5 120 -10 11 123 -5 minecraft:air",
            f"/setblock {COORDS} create:pulse_timer[facing=east]",
            "/gamemode survival @s",
            "/tp @s 9.6 120 -7.5",
        ))
        actor = world
        if args.lan:
            name = "DiodeTimingGuest"
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            folder = Path(stack.enter_context(TemporaryDirectory(prefix="hc-diode-timing-")))
            actor = stack.enter_context(multiplayer.joined_client(
                args, folder, f"127.0.0.1:{port}", name, render=True,
                scenario="diode-settings", pack=args.pack,
            ))
            multiplayer.until("the Pulse Timer guest joins", lambda: any(
                guest["name"] == name and guest["placed"] for guest in world.call("lan", "status")["guests"]
            ))
            world.commands((f"/gamemode survival {name}", f"/tp {name} 9.6 120 -7.5"))
        multiplayer.until("the player sees the timer and floor", lambda:
            actor.call("block", *TIMER)["block"] == "create:pulse_timer"
            and actor.call("state")["player"]["position"] == [9.6, 120.0, -7.5])
        for entry in expected:
            row, value, start, interval, progress = (
                int(entry[key]) for key in ("row", "value", "start_ticks", "interval", "clamped_ticks")
            )
            world.command(f"/data merge block {COORDS} {{State:{start}}}")
            choose(actor, row, value)
            multiplayer.until(f"the authority applies {value} in {LABELS[row]}",
                              lambda: sample(world) == (interval, progress))
            inverted = world.command(f"/execute if block {COORDS} create:pulse_timer[inverted=true]")
            if inverted != "Test failed":
                raise RuntimeError("Holding to configure changed the timer's polarity.")
        actor.call("look-at", 8.5, 120.115, -7.5)
        actor.call("wait", 1)
        actor.call("script", script="mouse right down\nwait 2\n")
        if world.command(f"/execute if block {COORDS} create:pulse_timer[inverted=true]") != "Test failed":
            raise RuntimeError("The value-slot press inverted the timer before release.")
        actor.call("script", script="mouse right up\nwait 3\n")
        multiplayer.until("the original short top click inverts the timer", lambda:
            world.command(f"/execute if block {COORDS} create:pulse_timer[inverted=true]") == "Test passed")
    print(f"Matched {len(expected)} Java Redstone Interval settings and the top short click in {'LAN' if args.lan else 'solo'}.")


if __name__ == "__main__":
    main()
