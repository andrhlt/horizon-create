#!/usr/bin/env python3
"""Connect Redstone Links from two independent clients on a dedicated Horizon server."""
import argparse
from contextlib import ExitStack
import importlib.util
from pathlib import Path
import tempfile

spec = importlib.util.spec_from_file_location("multiplayer", Path(__file__).with_name("test-multiplayer.py"))
multiplayer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multiplayer)

SCENARIO = "multiplayer-redstone-link"
LINK = "create:redstone_link"
Z = -8
Y = 95
SENDER = 8
RECEIVER = 18
LAMP = (19, Y, Z)


def press_sample(control, x, slot, z):
    control.call("key", slot, "tap")
    control.call("look-at", x + 0.5, Y + 0.25, Z + z)
    control.call("wait", 4)
    control.call("mouse", "right", "click")
    control.call("wait", 3)


def input_samples(control, x):
    for slot, z in (("2", 0.65625), ("3", 0.34375)):
        press_sample(control, x, slot, z)


def lamp(control, value):
    return f"lit={str(value).lower()}" in control.call("block", *LAMP)["state"]


def run(args, scratch):
    with ExitStack() as stack:
        address, command = stack.enter_context(multiplayer.dedicated(args, scratch, scenario=SCENARIO))
        alice = stack.enter_context(multiplayer.joined_client(args, scratch, address, "CreateAlice", scenario=SCENARIO))
        bob = stack.enter_context(multiplayer.joined_client(args, scratch, address, "CreateBob", scenario=SCENARIO))
        command("fill 5 94 -13 22 94 -5 minecraft:smooth_stone")
        command(f"setblock {SENDER} {Y} {Z} {LINK}[facing=up]")
        command(f"setblock {RECEIVER} {Y} {Z} {LINK}[facing=up]")
        command(f"setblock {' '.join(map(str, LAMP))} minecraft:redstone_lamp")
        for who, x in (("CreateAlice", SENDER), ("CreateBob", RECEIVER)):
            command(f"tp {who} {x + 0.5} {Y} {Z - 2.2} 0 25")
            command(f"item replace entity {who} hotbar.1 with minecraft:quartz 3")
            command(f"item replace entity {who} hotbar.2 with minecraft:iron_ingot 3")
        for client, x in ((alice, SENDER), (bob, RECEIVER)):
            multiplayer.until("a reachable supported Redstone Link",
                              lambda: client.call("block", x, Y, Z)["block"] == LINK)
            multiplayer.until("both frequency samples",
                              lambda: all(multiplayer.count(client, item) == 3
                                          for item in ("minecraft:quartz", "minecraft:iron_ingot")))
        bob.call("key", "1", "tap")
        bob.call("look-at", RECEIVER + 0.5, Y + 0.25, Z + 0.5)
        bob.call("key", "shift", "down")
        bob.call("wait", 4)
        bob.call("mouse", "right", "click")
        bob.call("key", "shift", "up")
        multiplayer.until("Bob's link to receive", lambda: "receiver=true" in bob.call("block", RECEIVER, Y, Z)["state"])
        input_samples(alice, SENDER)
        input_samples(bob, RECEIVER)
        command(f"item replace entity CreateAlice hotbar.4 with minecraft:redstone_block")
        multiplayer.until("Alice's power source", lambda: multiplayer.count(alice, "minecraft:redstone_block") == 1)
        alice.call("key", "5", "tap")
        alice.call("interact", SENDER, Y - 1, Z - 1, "up")
        multiplayer.until("Bob's lamp to light from Alice's sender", lambda: lamp(bob, True))
        press_sample(bob, RECEIVER, "3", 0.65625)
        multiplayer.until("the mismatched frequency to turn Bob's lamp off", lambda: lamp(bob, False))
        press_sample(bob, RECEIVER, "2", 0.65625)
        multiplayer.until("the restored frequency to light Bob's lamp", lambda: lamp(bob, True))
        for client in (alice, bob):
            if any(multiplayer.count(client, item) != 3 for item in ("minecraft:quartz", "minecraft:iron_ingot")):
                raise RuntimeError("A client spent a frequency sample.")
    print("Two clients configured live Redstone Link channels. Alice powered Bob’s lamp, and Bob could disconnect and reconnect his frequency.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    with tempfile.TemporaryDirectory(prefix="hc-wireless-mp-") as scratch:
        run(parser.parse_args(), Path(scratch))
