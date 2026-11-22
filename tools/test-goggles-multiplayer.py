#!/usr/bin/env python3
"""Check guest Goggles inspection before and after a saved world rejoin."""

import argparse
from contextlib import ExitStack
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tempfile

from fixture_world import ROOT

spec = spec_from_file_location("test_multiplayer", ROOT / "tools/test-multiplayer.py")
multiplayer = module_from_spec(spec)
spec.loader.exec_module(multiplayer)

CHUTE = (10, 95, -10)
TANK = (11, 95, -8)
TRACE_ENV = {"CREATE_GOGGLES_TRACE": "1", "HORIZON_NO_AUDIO": "1"}


def assert_readout(client, description):
    log = client.socket.parent / "ctl.log"
    expected = ("Chute Information", "Items move Downward", "Fluid Container Info:", "Water", "2500 mB / 8000 mB")
    multiplayer.until(
        description,
        lambda: log.exists() and all(value in log.read_text() for value in expected),
    )


def look_at_targets(client):
    client.call("look-at", CHUTE[0] + 0.5, CHUTE[1] + 0.5, CHUTE[2] + 0.5)
    client.call("wait", 8)
    client.call("look-at", TANK[0] + 0.5, TANK[1] + 0.5, TANK[2] + 0.5)
    client.call("wait", 8)


def run(args):
    artifact_dir = ROOT / ".local/app-2077-goggles"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hc-goggles-lan-") as temp:
        scratch = Path(temp)
        with multiplayer.dedicated(args, scratch, scenario="goggles-lan-before", artifact_dir=artifact_dir) as (address, command):
            with ExitStack() as stack:
                host = stack.enter_context(multiplayer.joined_client(
                    args, scratch, address, "GogglesHost", render=True,
                    scenario="goggles-lan-before", env=TRACE_ENV, artifact_dir=artifact_dir,
                ))
                guest = stack.enter_context(multiplayer.joined_client(
                    args, scratch, address, "GogglesGuest", render=True,
                    scenario="goggles-lan-before", env=TRACE_ENV, artifact_dir=artifact_dir,
                ))
                multiplayer.until("the host and guest chunks", lambda:
                    host.call("block", *CHUTE).get("loaded")
                    and guest.call("block", *TANK).get("loaded"))
                for setup in (
                    "fill 5 94 -12 13 94 -4 minecraft:smooth_stone",
                    f"setblock {' '.join(map(str, CHUTE))} create:chute[facing=down]",
                    f"setblock {' '.join(map(str, TANK))} create:fluid_tank",
                    f'data merge block {" ".join(map(str, TANK))} {{TankContent:{{Fluid:{{id:"minecraft:water",amount:2500}}}}}}',
                    "item replace entity GogglesHost armor.head with create:goggles",
                    "item replace entity GogglesGuest armor.head with create:goggles",
                    "tp GogglesHost 7.5 96 -9.5",
                    "tp GogglesGuest 7.5 96 -8.5",
                ):
                    command(setup)
                multiplayer.until("replicated inspection blocks", lambda:
                    host.call("block", *CHUTE)["state"].startswith("create:chute")
                    and guest.call("block", *TANK)["state"].startswith("create:fluid_tank"))
                look_at_targets(host)
                look_at_targets(guest)
                assert_readout(host, "host to draw both inspection readouts")
                assert_readout(guest, "guest to draw both inspection readouts")
                command("save-all")

        # Reuse the saved server directory; the block/fluid and player equipment
        # must be available to the returning guest without reseeding the world.
        with multiplayer.dedicated(args, scratch, scenario="goggles-lan-rejoin", artifact_dir=artifact_dir) as (address, command):
            with multiplayer.joined_client(
                args, scratch, address, "GogglesGuest", render=True,
                scenario="goggles-lan-rejoin", env=TRACE_ENV, artifact_dir=artifact_dir,
            ) as guest:
                multiplayer.until("the saved tank to load for the guest", lambda:
                    guest.call("block", *TANK).get("state", "").startswith("create:fluid_tank"))
                look_at_targets(guest)
                assert_readout(guest, "rejoined guest to inspect the saved chute and tank")
                command("save-all")
    print("Host and guest read the same chute and tank values; the guest read both again after save and rejoin.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
