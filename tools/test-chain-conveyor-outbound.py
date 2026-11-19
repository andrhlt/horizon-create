#!/usr/bin/env python3
"""Compare Frogport outbound custody and launch with the original Java tick trace."""

import argparse
import csv
import importlib
from pathlib import Path
import re
from struct import pack

from fixture_world import ROOT, fixture_world


chain = importlib.import_module("test-chain-conveyor-packages")
player = importlib.import_module("test-chain-conveyor-player")
A = (8, 102, -10)
B = (15, 102, -10)
PORT = (17, 100, -10)
render = importlib.import_module("test-chain-conveyor-visual")
SEND = re.compile(r"CREATE_FROGPORT_SEND_MODEL \[([^]]+)\],([^\r\n]+)")


def check_render(log, start):
    poses = {int(row["tick"]): row for row in render.rows("chain-conveyor-visual-send-java.csv")}
    reference = poses[37]
    head_pitch = float(reference["base_head"])
    length = float(reference["base_length"])

    ticks, frames = set(), []
    exact_frames = set()
    for position, fields in SEND.findall(log):
        if render.vector(position) != PORT:
            continue
        game_tick, partial, yaw, progress, head, pitch, tongue, scale, vertices = map(float, fields.split(","))
        if not 37 <= game_tick - start <= 45:
            continue
        tick = int(game_tick - start)
        render.close(progress, min(1, (tick - 37 + partial) / 10), fields)
        render.close(yaw, reference["yaw"], fields)
        render.close(pitch, reference["pitch"], fields)
        render.close(head, head_pitch * max(0, 1 - ((progress * 1.25) * 2 - 1)**4), fields)
        render.close(tongue, length * max(0, 1 - ((progress * 1.25 - 0.25) * 4 - 1)**4), fields)
        render.close(scale, 0.25 + 0.75 * progress, fields)
        if partial >= 0.999999:
            pose = poses[tick]
            for sampled, key in ((progress, "progress"), (head, "head"), (tongue, "tongue"), (scale, "scale")):
                render.close(sampled, pose[key], fields, epsilon=5e-5)
            exact_frames.add(tick)
        assert vertices > 0, fields
        ticks.add(tick)
        frames.append((progress, vertices))
    assert len(ticks) >= 7 and len(exact_frames) >= 6, (ticks, exact_frames)
    assert max(vertices for progress, vertices in frames if 0.4 <= progress <= 0.6) > max(
        vertices for progress, vertices in frames if 0.75 <= progress <= 0.9
    ), frames
    print(f"{len(frames)} offscreen Frogport launch poses across {len(ticks)} ticks")



def run(args):
    with (ROOT / "fixtures/chain-conveyor-outbound-java.csv").open() as stream:
        expected = {int(row["tick"]): row for row in csv.DictReader(stream)}
    with fixture_world(args, "ChainFrogportOutbound", pack=args.pack, render=args.visual,
                       env={"CREATE_CHAIN_RENDER": "1"} if args.visual else None) as world:
        chain.setup(world, A, B, (8, 101, -10), PORT, (7, 0, 0), False, warm=7)
        chain.merge(world, PORT, '{AddressFilter:"Lab-In",Target:{RelativePos:[I;-2,2,0],ChainPosition:150f}}')
        chain.merge(world, B, "{PackagePorts:[{Port:[I;2,-2,0],ChainPosition:150f}]}")
        if args.visual:
            world.command("/gamemode spectator")
            world.command("/tp @s 14.0 104.0 -5.0")
            world.call("look-at", 17.0, 101.0, -10.0)
            world.call("key", "f1", "tap")
        start = world.clock()
        for tick in range(1, max(expected) + 1):
            world.step_to(start + tick)
            if tick == 2:
                cargo = chain.stack("Lab-In", "paper", 3)
                chain.merge(world, A, f"{{Packages:[{{Item:{cargo},Position:40f}}]}}")
            if tick == 35:
                cargo = chain.stack("Away", "paper", 4)
                existing = player.get(world, PORT, "Items")
                assert chain.payload(existing) == "Lab-In:paper:3"
                chain.merge(world, PORT, "{Items:" + existing.rstrip("]") + ",{Slot:1b," + cargo[1:] + "]}")
            if args.visual and 37 <= tick <= 46:
                world.call("wait", 2)
                if args.capture and tick == 41:
                    world.call("screenshot", args.capture)
            if tick not in expected:
                continue
            raw = world.commands((
                f"/data get block {chain.coords(PORT)}",
                f"/data get block {chain.coords(PORT)} Items",
                f"/data get block {chain.coords(PORT)} SendingPackage",
                f"/data get block {chain.coords(B)} Packages",
            ))
            port, inventory, sending, packages = [reply.partition("block data: ")[2] for reply in raw]
            wanted = expected[tick]
            progress = float(chain.scalar(port, "AnimationProgress"))
            custody = (
                chain.scalar(port, "CurrentlyDepositing") != "0",
                '"Away"' in inventory,
                '"Away"' in sending,
            )
            assert custody == tuple(wanted[k] == "true" for k in ("depositing", "stored", "animated")), (
                tick, raw, wanted,
            )
            assert abs(progress - float(wanted["progress"])) < 1e-7, (tick, progress, wanted)
            loaded = next((entry for entry in chain.snbt.top_level_entries(packages) if '"Away"' in entry), "")
            position = float(chain.scalar(loaded, "Position")) if loaded else -1
            assert pack("f", position) == pack("f", float(wanted["position"])), (tick, position, wanted)
            assert "Lab-In:paper:3" in [chain.payload(item) for item in chain.snbt.top_level_entries(inventory)]
            if loaded:
                assert chain.payload(loaded) == "Away:paper:4"
        if args.visual:
            check_render((world.socket.parent / "ctl.log").read_text(), start)
    print(f"{len(expected)} Java outbound ticks, including launch at tick 42 and continuing loop position")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--capture", type=Path)
    run(parser.parse_args())
