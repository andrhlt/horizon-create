#!/usr/bin/env python3
"""Assemble and drive a train while a second client observes the dedicated server."""
import argparse
from contextlib import ExitStack
import csv
import importlib.util
import math
from pathlib import Path
import tempfile
import time

from fixture_world import ROOT, FixtureWorld


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCENARIO = "multiplayer-train"
multiplayer = load("test-multiplayer")
train = load("test-simple-train")


class ConsoleClient(FixtureWorld):
    def __init__(self, client, send, name):
        super().__init__(client.ctl, client.socket, client.env)
        self.send = send
        self.name = name

    def command(self, command):
        log = ROOT / f".local/{SCENARIO}-server.log"
        start = log.stat().st_size
        self.send(f"execute as {self.name} at @s run {command.removeprefix('/')}")
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            with log.open() as file:
                file.seek(start)
                for line in file:
                    if "System chat: " in line:
                        return line.split("System chat: ", 1)[-1].strip()
            time.sleep(0.01)
        raise RuntimeError(f"No server response to {command}")

    def commands(self, batch):
        return [self.command(command) for command in batch]


def run(args, scratch):
    with (ROOT / "fixtures/manual_train-java.csv").open() as source:
        expected = {int(row["tick"]): row for row in csv.DictReader(source)}
    with ExitStack() as stack:
        address, command = stack.enter_context(multiplayer.dedicated(args, scratch, scenario=SCENARIO))
        alice = stack.enter_context(multiplayer.joined_client(args, scratch, address, "CreateAlice", render=True, scenario=SCENARIO))
        bob = stack.enter_context(multiplayer.joined_client(args, scratch, address, "CreateBob", render=True, scenario=SCENARIO))
        for action in ("op CreateAlice", "op CreateBob", "gamemode creative CreateAlice", "tick freeze"):
            command(action)
        alice.call("wait", 4)
        bob.call("wait", 4)
        alice = ConsoleClient(alice, command, "CreateAlice")
        bob = ConsoleClient(bob, command, "CreateBob")
        train.setup(alice)
        start = alice.clock()
        x, y, z = train.X, train.Y, train.Z
        command(f"setblock {x + 4} {y + 2} {z - 5} minecraft:smooth_stone")
        command(f"tp CreateBob {x + 4.5} {y + 3} {z - 4.5}")
        bob.call("wait", 4)
        multiplayer.until(
            "Bob to see the station and the block positions the train left behind",
            lambda: bob.call("block", *train.STATION)["block"] == "create:track_station"
            and bob.call("block", x + 1, y + 2, z)["block"] == "minecraft:air",
        )
        for tick in range(13, 50):
            if tick > 13:
                alice.step_to(start + tick - 13)
            found = train.sample(bob)
            wanted = (float(expected[tick]["speed"]), *(float(expected[tick][f"wheel_{wheel}"]) for wheel in range(1, 5)), 3)
            if any(not math.isclose(a, b, rel_tol=0, abs_tol=1.2e-6) for a, b in zip(found, wanted, strict=True)):
                raise RuntimeError(f"Tick {tick}: second client read {found}, Java {wanted}")
            if tick == 18:
                alice.call("key", "w", "down")
                alice.call("wait", 3)
            elif tick == 37:
                # Bob's view consumes the same display entity stream as a normal guest.
                bob.call("look-at", x - 0.2, y + 1.6, z + 0.5)
                bob.call("key", "f1", "tap")
                bob.call("wait", 3)
                bob.call("screenshot", ROOT / ".local/multiplayer-train.png")
        alice.call("key", "w", "up")
    print("A survival carriage assembled on the dedicated server. A second client observed the train and read 37 Java-matching motion ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    with tempfile.TemporaryDirectory(prefix="hc-train-mp-") as scratch:
        run(parser.parse_args(), Path(scratch))
