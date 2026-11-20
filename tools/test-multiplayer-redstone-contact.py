#!/usr/bin/env python3
"""Check Redstone Contact state agreement between a dedicated host and LAN guests."""

import argparse
from contextlib import ExitStack
from pathlib import Path
import tempfile

import importlib.util

spec = importlib.util.spec_from_file_location("multiplayer", Path(__file__).with_name("test-multiplayer.py"))
multiplayer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multiplayer)

SCENARIO = "redstone-contact-lan"
CASES = (
    ("matching Redstone Contacts", (9, 95, -9), (10, 95, -9),
     "create:redstone_contact[facing=east,powered=false]",
     "create:redstone_contact[facing=west,powered=false]", True),
    ("nonmatching faces", (13, 95, -9), (14, 95, -9),
     "create:redstone_contact[facing=east,powered=false]",
     "create:redstone_contact[facing=north,powered=false]", False),
    ("Redstone/Elevator Contacts", (17, 95, -9), (18, 95, -9),
     "create:redstone_contact[facing=east,powered=false]",
     "create:elevator_contact[facing=west,powered=false,calling=false,powering=false]", True),
)


def contact_state(client, position):
    state = client.call("block", *position)["state"]
    return "powered=true" in state


def run(args, scratch):
    with ExitStack() as stack:
        address, command = stack.enter_context(multiplayer.dedicated(args, scratch, scenario=SCENARIO))
        host = stack.enter_context(multiplayer.joined_client(args, scratch, address, "ContactHost", scenario=SCENARIO))
        guest = stack.enter_context(multiplayer.joined_client(args, scratch, address, "ContactGuest", scenario=SCENARIO))
        command("tp ContactHost 8.5 96 -7.5")
        command("tp ContactGuest 8.5 96 -7.5")
        multiplayer.until("both clients to load the contact fixtures", lambda: (
            host.call("block", 9, 95, -9).get("loaded")
            and guest.call("block", 9, 95, -9).get("loaded")
        ))
        for _, left, right, left_state, right_state, expected in CASES:
            command(f"setblock {' '.join(map(str, left))} {left_state}")
            command(f"setblock {' '.join(map(str, right))} {right_state}")
            for client in (host, guest):
                multiplayer.until("both clients to agree on contact matching", lambda: (
                    contact_state(client, left) == expected
                ))
            if contact_state(host, left) != contact_state(guest, left):
                raise RuntimeError("Host and guest disagreed on Redstone Contact output.")
        for _, left, right, _, _, _ in CASES:
            command(f"setblock {' '.join(map(str, right))} air")
            for client in (host, guest):
                multiplayer.until("both clients to see contact deactivation", lambda: (
                    not contact_state(client, left)
                ))
    print("Host and guest agreed on matching, mismatched, mixed-contact, and deactivation states.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    with tempfile.TemporaryDirectory(prefix="hc-redstone-contact-lan-") as scratch:
        run(parser.parse_args(), Path(scratch))
