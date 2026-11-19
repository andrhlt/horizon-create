#!/usr/bin/env python3
"""Compare Frogport push and pull through the original barrel below it."""

import argparse
from contextlib import ExitStack
import csv
import importlib
import json
import re
from pathlib import Path
from struct import pack
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


outbound = importlib.import_module("test-chain-conveyor-outbound")
chain, player = outbound.chain, outbound.player
multiplayer = importlib.import_module("test-multiplayer")
A, B, PORT = outbound.A, outbound.B, outbound.PORT
BARREL = (PORT[0], PORT[1] - 1, PORT[2])


def check_blocked(tick, row, barrel, port, inventory):
    entries = list(chain.snbt.top_level_entries(barrel))
    matching = [entry for entry in entries if "Lab-In" in entry]
    sticks = sum(int(chain.scalar(entry, "count")) for entry in entries if "minecraft:stick" in entry)
    custody = "inventory:" + chain.payload(inventory) if "Lab-In" in inventory else "-"
    observed = (chain.scalar(port, "FailedLastExport") == "1", bool(matching), custody, sticks)
    expected = (row["blocked"] == "true", row["received"] == "true", row["custody"], int(row["sticks"]))
    assert observed == expected, (tick, observed, expected, barrel, port)
    if matching:
        assert len(matching) == 1 and chain.payload(matching[0]) == "Lab-In:paper:3", matching
        assert chain.scalar(matching[0], "Slot") == "2", matching


def warning_samples(log):
    samples = []
    for clock, raw in re.findall(r"CREATE_GOGGLES (\d+) ([^\r\n]+)", log):
        lines = json.loads(raw)
        text = " ".join("".join(part[0] for part in line) for line in lines)
        if "Contains Packages" not in text:
            continue
        assert "Could it be full?" in " ".join(text.split()), text
        styles = [part for line in lines for part in line]
        assert any(word.strip() == "Frogport" and color == 0xFFFFFF for word, color, _ in styles), styles
        samples.append(int(clock))
    return samples


def check_hud(log, start):
    samples = [clock - start for clock in warning_samples(log)]
    assert 38 in samples and 47 in samples, samples
    assert max(samples) < 49 and min(samples) >= 36, samples
    print(f"Frogport warning shown during blockage in {len(samples)} offscreen samples")


def run(args):
    trace = "blocked-barrel" if args.blocked else "adjacent"
    with (ROOT / f"fixtures/chain-conveyor-{trace}-java.csv").open() as stream:
        java = {int(row["tick"]): row for row in csv.DictReader(stream)}
    name = "ChainFrogportBlocked" if args.blocked else "ChainFrogportAdjacent"
    if args.visual:
        name += "Offscreen"
    env = {"CREATE_GOGGLES_TRACE": "1"} if args.visual else None
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, name, pack=args.pack,
                                                   render=args.visual and not args.lan, env=env))
        observer, observed_player = world, "@s"
        if args.lan:
            address = "127.0.0.1:" + str(world.call("lan", "open", "0", "commands", "force")["port"])
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-frogport-warning-")))
            observed_player = "FrogportGuest"
            observer = stack.enter_context(multiplayer.joined_client(
                args, scratch, address, observed_player, render=True, scenario="frogport-warning",
                pack=args.pack, env=env,
            ))
            multiplayer.until("guest to enter the world", lambda: any(
                guest["name"] == observed_player and guest["placed"]
                for guest in world.call("lan", "status")["guests"]
            ))
        chain.setup(world, A, B, (8, 101, -10), PORT, (7, 0, 0), False, warm=7)
        chain.merge(world, PORT, '{AddressFilter:"Lab-In",Target:{RelativePos:[I;-2,2,0],ChainPosition:150f}}')
        chain.merge(world, B, "{PackagePorts:[{Port:[I;2,-2,0],ChainPosition:150f}]}")
        if args.visual:
            world.command("/setblock 20 99 -9 minecraft:stone")
            world.command(f"/tp {observed_player} 20.5 100 -8.5")
            if args.lan:
                multiplayer.until("guest to reach the Frogport", lambda:
                                  observer.call("state")["player"]["position"] == [20.5, 100, -8.5])
                multiplayer.until("guest to see the Frogport", lambda:
                                  observer.call("block", *PORT).get("state", "").startswith("create:package_frogport"))
            observer.call("look-at", 17.5, 100.35, -9.5)
            hit = observer.call("state")["looking_at"]
            assert hit["kind"] == "block" and hit["block"]["pos"] == list(PORT), hit
        start = world.clock()
        for tick in range(1, max(java) + 1):
            world.step_to(start + tick)
            if tick == 2:
                incoming = chain.stack("Lab-In", "paper", 3)
                chain.merge(world, A, f"{{Packages:[{{Item:{incoming},Position:40f}}]}}")
            if tick == 35:
                world.command(f"/setblock {chain.coords(BARREL)} minecraft:barrel")
                if args.blocked:
                    items = ",".join(f'{{Slot:{n}b,id:"minecraft:stick",count:64}}' for n in range(27))
                    chain.merge(world, BARREL, "{Items:[" + items + "]}")
                else:
                    outgoing = chain.stack("Away", "paper", 4)
                    chain.merge(world, BARREL,
                                '{Items:[{Slot:0b,id:"minecraft:stick",count:1},{Slot:1b,' + outgoing[1:] + "]}")
            if args.blocked and tick == 43:
                world.command(f"/item replace block {chain.coords(BARREL)} container.2 with minecraft:air")
            if args.visual and tick in (36, 38, 47, 49, 52):
                log = observer.socket.parent / "ctl.log"
                offset = log.stat().st_size
                observer.call("wait", 4 if args.lan else 2)
                if args.lan:
                    samples = warning_samples(log.read_text()[offset:])
                    assert bool(samples) == (tick in (38, 47)), (tick, samples)
                if args.capture and tick == 38:
                    observer.call("screenshot", args.capture)
            if tick not in java:
                continue
            barrel = player.get(world, BARREL, "Items")
            port = world.command(f"/data get block {chain.coords(PORT)}").partition("block data: ")[2]
            port_inventory = player.get(world, PORT, "Items")
            if args.blocked:
                check_blocked(tick, java[tick], barrel, port, port_inventory)
                continue
            sending = player.get(world, PORT, "SendingPackage")
            looping = player.get(world, B, "Packages")
            custody = "-"
            if "Away" in sending:
                custody = "animation:" + chain.payload(sending)
            elif "Lab-In" in port_inventory:
                custody = "inventory:" + chain.payload(port_inventory)
            observed = (
                "Lab-In" in barrel, "Away" in barrel,
                "Away" in looping, "minecraft:stick" in barrel,
            )
            row = java[tick]
            assert observed == tuple(row[key] == "true" for key in (
                "received_below", "outbound_below", "launched", "stick_untouched",
            )), (tick, observed, row, barrel, port)
            assert custody == row["port_custody"], (tick, custody, row)
            assert pack("f", float(chain.scalar(port, "AnimationProgress"))) == pack("f", float(row["progress"])), (
                tick, port, row,
            )
            if "Lab-In" in barrel:
                intake = next(entry for entry in chain.snbt.top_level_entries(barrel) if "Lab-In" in entry)
                assert chain.payload(intake) == "Lab-In:paper:3", intake
            if "Away" in looping:
                launched = next(entry for entry in chain.snbt.top_level_entries(looping) if "Away" in entry)
                assert chain.payload(launched) == "Away:paper:4", launched
        if args.lan:
            print("LAN guest saw the warning appear and clear with the authoritative export")
        elif args.visual:
            check_hud((world.socket.parent / "ctl.log").read_text(), start)
    outcome = "blocked at tick 37, delivered at tick 48" if args.blocked else "push and pull at tick 37, launch at tick 42"
    print(f"{len(java)} Java Frogport ticks, {outcome}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--blocked", action="store_true")
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--capture", type=Path)
    args = parser.parse_args()
    if args.visual and not args.blocked:
        parser.error("--visual requires --blocked")
    if args.lan and not args.visual:
        parser.error("--lan requires --visual")
    run(args)
