#!/usr/bin/env python3
"""Program a Sequenced Gearshift as a survival guest and run it on the host."""
import argparse
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

spec = spec_from_file_location("multiplayer_fixture", ROOT / "tools/test-multiplayer.py")
multiplayer = module_from_spec(spec)
spec.loader.exec_module(multiplayer)
spec = spec_from_file_location("sequencer_fixture", ROOT / "tools/test-sequenced-gearshift-editor.py")
sequencer = module_from_spec(spec)
spec.loader.exec_module(sequencer)
GUEST = "GearshiftGuest"

def verify(args, tmp):
    program = sequencer.original_program()
    with fixture_world(args, "SequencerEditorLAN", render=True, pack=args.pack) as host:
        sequencer.setup(host)
        host.command("/data merge block 7 101 -10 {ScrollValue:32}")
        host.step_to(host.clock() + 1)
        host.command("/tp @s 13.500 101.000 -7.500")
        address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
        with multiplayer.joined_client(
            args, tmp, address, GUEST, render=True, scenario="gearshift-lan", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the Sequenced Gearshift test world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/tp {GUEST} 8.500 101.000 -6.500",
            ))
            multiplayer.until("the guest to see the gearshift", lambda: (
                guest.call("state")["player"]["position"] == [8.5, 101.0, -6.5]
                and guest.call("block", *sequencer.SEQUENCER)["block"] == "create:sequenced_gearshift"
            ))
            sequencer.configure(guest)
            multiplayer.until("the edited instructions to reach the host", lambda: sequencer.program_matches(host, program))
            host.command("/setblock 8 102 -10 minecraft:redstone_block")
            host.step_to(host.clock() + 1)
            multiplayer.until("the guest to see the first instruction running", lambda: (
                "state=1" in guest.call("block", *sequencer.SEQUENCER)["state"]
            ))
            out = sequencer.sample(host.command(f"/data get block {sequencer.coords(sequencer.OUTPUT)}"), "Speed")
            if out != 64.0:
                raise RuntimeError(f"The guest's first programmed turn should produce +64 RPM, got {out}.")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-sql-") as tmp:
        verify(args, Path(tmp))
    print("A survival guest saved all five original instructions, and both saw the first turn at +64 RPM.")

if __name__ == "__main__":
    main()
