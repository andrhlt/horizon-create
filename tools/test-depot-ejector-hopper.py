#!/usr/bin/env python3
"""Compare the original Hopper feeding a Weighted Ejector set to three items."""
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
HOPPER = "5 106 -11"


def run(args):
    actual = []
    with args.reference.open() as source:
        reader = csv.reader(source)
        header, expected = next(reader), list(reader)
    world = "EjectorHopperLAN" if args.multiplayer else "EjectorHopper"
    with ExitStack() as stack:
        control = stack.enter_context(fixture_world(args, world, pack=args.pack))
        launch.setup(control)
        control.commands((
            f"/data merge block {launch.EJECTOR} {{ScrollValue:3}}",
            f"/setblock {HOPPER} minecraft:hopper[facing=down,enabled=true]",
            f'/data merge block {HOPPER} {{Items:[{{Slot:0b,id:"{launch.ITEM}",count:3}}],TransferCooldown:0}}',
        ))
        guest = None
        if args.multiplayer:
            port = control.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejector-hopper-")))
            name = "EjectHopper"
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, scenario="ejector-hopper", pack=args.pack,
            ))
            multiplayer.until("guest enters the Ejector fixture", lambda: any(
                player["name"] == name and player["placed"]
                for player in control.call("lan", "status")["guests"]
            ))
            control.commands((f"/gamemode survival {name}", f"/tp {name} 7.5 105 -10.5"))
            multiplayer.until("guest sees the receiving Depot",
                              lambda: guest.call("block", 9, 105, -11)["block"] == "create:depot")
        start = control.clock()
        for row in expected:
            tick = int(row[0])
            control.step_to(start + tick)
            if tick == 12:
                control.command(f"/setblock {launch.POWER} minecraft:air")
            machine, input_items, flying, depot, hopper, cooldown, incoming = control.commands((
                f"/data get block {launch.EJECTOR}", f"/data get block {launch.EJECTOR} Items",
                f"/data get block {launch.EJECTOR} LaunchedItems", f"/data get block {launch.DEPOT} Items",
                f"/data get block {HOPPER} Items", f"/data get block {HOPPER} TransferCooldown",
                f"/data get block {launch.EJECTOR} Incoming",
            ))
            state = re.search(r"\b(CHARGED|LAUNCHING|RETRACTING)\b", machine)
            minimum = re.search(r"\bScrollValue: (-?\d+)\b", machine)
            age = re.search(r"\bTime: (\d+)", flying)
            delay = launch.value(cooldown)
            if not state or not minimum or delay is None:
                raise RuntimeError(f"Missing Hopper or Ejector data at tick {tick}: {(machine, cooldown)}")
            pending = re.findall(r"\bPos: (-?\d+(?:\.\d+)?)(?:f)?", incoming)
            actual.append([str(tick), minimum[1], state[1], str(launch.count(input_items)),
                           age[1] if age else "-1", str(launch.count(depot)), str(launch.count(hopper)),
                           str(int(delay)), str(len(pending)), f"{float(pending[0]) if pending else 0:.6f}"])
        if guest:
            guest.call("interact", 9, 105, -11, "up")
            multiplayer.until("guest retrieves the three ingots", lambda: multiplayer.count(guest, launch.ITEM) == 3)
    if args.trace:
        with args.trace.open("w") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(actual)
    differences = [(want, got) for want, got in zip(expected, actual, strict=True)
                   if want[:-1] != got[:-1] or abs(float(want[-1]) - float(got[-1])) > .000002]
    if differences:
        raise RuntimeError(f"Hopper-fed Ejector differed on {len(differences)} Java ticks: {differences[:8]}")
    print(f"Hopper-fed Ejector, incoming queue and landing matched all {len(actual)} Java ticks.")
    if args.multiplayer:
        print("The guest collected the combined stack of three ingots.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/depot-ejector-hopper-java.csv")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    run(parser.parse_args())
