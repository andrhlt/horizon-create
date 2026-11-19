#!/usr/bin/env python3
"""Compare the original comparator delay and a save during an active turn."""
import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
from tempfile import TemporaryDirectory
from pathlib import Path

from fixture_world import ROOT, fixture_world

spec = spec_from_file_location("sequencer_fixture", ROOT / "tools/test-sequenced-gearshift-editor.py")
sequencer = module_from_spec(spec)
spec.loader.exec_module(sequencer)
spec = spec_from_file_location("multiplayer_fixture", ROOT / "tools/test-multiplayer.py")
multiplayer = module_from_spec(spec)
spec.loader.exec_module(multiplayer)

METER = (8, 101, -11)
GUEST = "SeqStopGuest"


def samples():
    with (ROOT / "fixtures/sequenced-gearshift-comparator-java.csv").open() as source:
        _, *rows = csv.reader(source)
    return {int(tick): (int(step), int(power), float(rpm)) for tick, step, power, rpm in rows}


def verify(args):
    program = sequencer.original_program()
    reference = samples()
    if len(reference) != 44:
        raise RuntimeError("Expected 44 Java comparator samples.")
    diffs = []
    with fixture_world(args, "SequencerAnalog", render=True, pack=args.pack) as control:
        sequencer.setup(control)
        control.command("/setblock 8 101 -11 minecraft:comparator[facing=south]")
        start = control.clock()
        for tick, (step, signal, rpm) in reference.items():
            if tick:
                control.step_to(start + tick)
            if tick == 2:
                sequencer.configure(control)
                sequencer.wait_until(control, "the original program to save", lambda: sequencer.program_matches(control, program))
            if tick == 39:
                sequencer.open_editor(control)
                control.call("click-at", *sequencer.widget(control, "Confirm"))
                sequencer.wait_until(control, "the active instruction to cancel", lambda: sequencer.sample(
                    control.command(f"/data get block {sequencer.coords(sequencer.SEQUENCER)}"), "InstructionIndex",
                ) == -1)
            out, result = control.commands((
                f"/data get block {sequencer.coords(sequencer.OUTPUT)}", f"/data get block {sequencer.coords(METER)}",
            ))
            active = control.call("block", *sequencer.SEQUENCER)["state"]
            actual = f"state={step}" in active, sequencer.sample(result, "OutputSignal"),
            if actual != (True, signal):
                diffs.append((tick, "comparator", (step, signal), actual))
            output = sequencer.sample(out, "Speed")
            if output != rpm:
                diffs.append((tick, "RPM", rpm, output))
            if tick == 0:
                control.command("/data merge block 7 101 -10 {ScrollValue:32}")
            if tick in (4, 20, 37):
                control.command("/setblock 8 102 -10 minecraft:redstone_block")
            if tick in (5, 21, 40):
                control.command("/setblock 8 102 -10 minecraft:air")
    if diffs:
        raise RuntimeError(f"{len(diffs)} Java signal/cancel differences: {diffs[:35]}.")
    print("The comparator and saving during an active turn matched all 44 Java samples.")

def verify_lan(args, tmp):
    program = sequencer.original_program()
    reference = samples()
    with fixture_world(args, "SequencerAnalogLAN", render=True, pack=args.pack) as host:
        sequencer.setup(host)
        host.commands((
            "/data merge block 7 101 -10 {ScrollValue:32}",
            "/setblock 8 101 -11 minecraft:comparator[facing=south]",
            "/tp @s 13.500 101.000 -7.500",
        ))
        host.step_to(host.clock() + 1)
        address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
        with multiplayer.joined_client(
            args, tmp, address, GUEST, render=True, scenario="sequencer-stop-lan", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}", f"/tp {GUEST} 8.500 101.000 -6.500",
            ))
            multiplayer.until("the guest to reach the gearshift", lambda: (
                guest.call("state")["player"]["position"] == [8.5, 101.0, -6.5]
                and guest.call("block", *sequencer.SEQUENCER)["block"] == "create:sequenced_gearshift"
            ))
            sequencer.configure(guest)
            multiplayer.until("the host to receive the guest's program", lambda: sequencer.program_matches(host, program))
            host.command("/setblock 8 102 -10 minecraft:redstone_block")
            first_tick = host.clock() + 1
            host.step_to(first_tick)
            speed = sequencer.sample(host.command(f"/data get block {sequencer.coords(sequencer.OUTPUT)}"), "Speed")
            if speed != 64:
                raise RuntimeError(f"The guest's first row produced {speed} RPM.")
            host.step_to(first_tick + 1)
            sequencer.open_editor(guest)
            guest.call("click-at", *sequencer.widget(guest, "Confirm"))
            multiplayer.until("the host to accept the guest's save", lambda: sequencer.sample(
                host.command(f"/data get block {sequencer.coords(sequencer.SEQUENCER)}"), "InstructionIndex",
            ) == -1)
            for tick in range(39, 44):
                if tick > 39:
                    host.step_to(first_tick + tick - 38)
                want, signal, rpm = reference[tick]
                for peer in (host, guest):
                    multiplayer.until("the guest and host to see the original step", lambda: (
                        f"state={want}" in peer.call("block", *sequencer.SEQUENCER)["state"]
                    ))
                output, meter = host.commands((
                    f"/data get block {sequencer.coords(sequencer.OUTPUT)}", "/data get block 8 101 -11",
                ))
                if (sequencer.sample(output, "Speed"), sequencer.sample(meter, "OutputSignal")) != (rpm, signal):
                    raise RuntimeError(f"The active save should stop the shaft and preserve the comparator delay at Java tick {tick}: {output}, {meter}.")
                if tick == 40:
                    host.command("/setblock 8 102 -10 minecraft:air")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-cpl-") as tmp:
            verify_lan(args, Path(tmp))
        print("The guest stopped the shaft on save. Both clients saw Java’s comparator and step timing.")
    else:
        verify(args)

if __name__ == "__main__":
    main()
