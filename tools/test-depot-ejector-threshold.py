#!/usr/bin/env python3
"""Compare Weighted Ejector stack-size authoring and launch behavior with Java."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

launch = import_module("test-depot-ejector-launch")
multiplayer = import_module("test-multiplayer")
LABEL = "Ejected Stack Size"


def target(actor):
    actor.call("look-at", 5.99, 105.375, -10.5)
    observed = actor.call("looking-at")
    if (observed.get("block") or {}).get("pos") != [5, 105, -11]:
        raise RuntimeError(f"The player isn't looking at the Weighted Ejector: {observed}")
    actor.call("mouse", "right", "down")
    actor.call("wait", 7)
    buttons = actor.call("screen")["buttons"]
    row = next((button for button in buttons if button["label"] == LABEL), None)
    if row is None:
        actor.call("mouse", "right", "up")
        raise RuntimeError(f"The Ejector stack-size board did not open: {buttons}")
    return row


def minimum(control):
    return int(launch.value(control.command(f"/data get block {launch.EJECTOR} ScrollValue")) or 0)


def edit(control, actor, size):
    row = target(actor)
    offset = 2 * size + ((max(size, 1) - 1) // 10) * 4 + 1.5
    if size % 10 == 0:
        offset += 2
    if size:
        offset += 4
    x = row["x"] + offset
    y = row["y"] + row["h"] / 2
    actor.call("scroll-at", x, y, 0)
    actor.call("click-at", x, y, "right")
    actor.call("wait", 3)
    multiplayer.until(f"setting stack size to {size}", lambda: minimum(control) == size)
    if actor.call("state")["screen"] != "playing":
        raise RuntimeError("Releasing use did not close the Ejector stack-size board.")


def run(args):
    with args.reference.open() as source:
        data = csv.reader(source)
        header, expected = next(data), list(data)
    world = "EjectorStackSizeLAN" if args.multiplayer else "EjectorStackSize"
    actual = []
    with ExitStack() as stack:
        control = stack.enter_context(fixture_world(args, world, render=True, pack=args.pack))
        launch.setup(control)
        actor, name = control, "@s"
        if args.multiplayer:
            port = control.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejector-count-")))
            name = "EjectSizeGuest"
            actor = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, scenario="ejector-stack-size",
                render=True, pack=args.pack,
            ))
            multiplayer.until("the guest enters the fixture", lambda: any(
                player["name"] == name and player["placed"]
                for player in control.call("lan", "status")["guests"]
            ))
        control.commands((
            "/fill 6 104 -12 8 104 -10 minecraft:smooth_stone",
            f"/gamemode survival {name}",
            f"/tp {name} 7.5 105 -10.5",
        ))
        multiplayer.until("the player reaches the Ejector", lambda: (
            actor.call("state")["player"]["position"] == [7.5, 105, -10.5]
            and actor.call("block", 5, 105, -11)["block"] == "create:weighted_ejector"
        ))
        edit(control, actor, 3)
        start = control.clock()
        for row in expected:
            tick = int(row[0])
            control.step_to(start + tick)
            if tick == 12:
                control.commands((
                    f'/data merge block {launch.EJECTOR} '
                    f'{{Items:[{{Slot:0b,id:"{launch.ITEM}",count:2}}],BeltPosition:0.5f}}',
                    f"/setblock {launch.POWER} minecraft:air",
                ))
            elif tick == 20:
                edit(control, actor, 2)
                if control.clock() != start + tick:
                    raise RuntimeError("Changing the minimum unexpectedly advanced the simulation.")
            state, contents, flying, received = control.commands((
                f"/data get block {launch.EJECTOR} State", f"/data get block {launch.EJECTOR} Items",
                f"/data get block {launch.EJECTOR} LaunchedItems", f"/data get block {launch.DEPOT} Items",
            ))
            matched = re.search(r"\b(CHARGED|LAUNCHING|RETRACTING)\b", state)
            age = re.search(r"\bTime: (\d+)", flying)
            if not matched:
                raise RuntimeError(f"Missing Ejector state at tick {tick}: {state}")
            actual.append([str(tick), str(minimum(control)), matched[1], str(launch.count(contents)),
                           age[1] if age else "-1", str(launch.count(received))])
    if args.trace:
        with args.trace.open("w") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(actual)
    differences = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
    if differences:
        raise RuntimeError(f"Stack-size behavior differed on {len(differences)} Java ticks: {differences[:8]}")
    print(f"The Weighted Ejector matched {len(actual)} Java ticks after authoring the threshold from three to two.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/depot-ejector-threshold-java.csv")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    run(parser.parse_args())
