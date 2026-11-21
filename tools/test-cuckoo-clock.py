#!/usr/bin/env python3
"""Check survival placement and rear-shaft RPM for both Create cuckoo clocks."""

import argparse
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
import re
import time
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

mp = import_module("test-multiplayer")
crafting = import_module("test-survival-crafting")

VARIANTS = ("create:cuckoo_clock", "create:mysterious_cuckoo_clock")
TARGETS = ((8, 180, 20), (14, 180, 20))
CRAFTING_TABLE = (6, 180, 18)


@contextmanager
def join_guest(args, host):
    port = host.call("lan", "open", 0, "commands", "force")["port"]
    with TemporaryDirectory(prefix="hc-cuckoo-lan-") as scratch, mp.joined_client(
        args, Path(scratch), f"127.0.0.1:{port}", "CuckooGuest", pack=args.pack,
        artifact_dir=Path("/private/tmp/horizon-app1998-evidence"),
    ) as guest:
        mp.until("the cuckoo guest joins", lambda: any(
            player["name"] == "CuckooGuest" and player["placed"]
            for player in host.call("lan", "status")["guests"]
        ))
        yield guest


def speed(text):
    match = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)f\b", text)
    if match is None:
        raise RuntimeError(f"Missing kinetic Speed in {text}")
    return float(match.group(1))


def step_and_wait(host, count):
    target = host.clock() + count
    host.call("command", f"/tick step {count}")
    deadline = time.monotonic() + 4
    while host.clock() < target:
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Expected stepped game time to reach {target}")


def crafting_recipes(args):
    with fixture_world(args, "CuckooClockRecipes", render=True, pack=args.pack,
                       artifact_dir=Path("/private/tmp/horizon-app1998-evidence")) as host:
        host.commands((
            "/fill 5 179 17 8 179 21 minecraft:stone",
            f"/setblock {' '.join(map(str, CRAFTING_TABLE))} minecraft:crafting_table",
            "/gamemode survival",
            "/tp @s 6.5 180 19.5",
            "/give @s minecraft:oak_planks 1",
            "/give @s create:andesite_casing 1",
            "/give @s minecraft:clock 1",
        ))
        host.call("look-at", 6.5, 180.5, 18.5)
        host.call("wait", 3)
        host.call("interact", *CRAFTING_TABLE, "up")
        crafting.distribute(host, crafting.inventory_slot(host, "minecraft:oak_planks"), (100,))
        crafting.distribute(host, crafting.inventory_slot(host, "create:andesite_casing"), (103,))
        crafting.distribute(host, crafting.inventory_slot(host, "minecraft:clock"), (106,))
        crafting.craft(host, "create:cuckoo_clock", 1)
        host.call("close")
        host.command("/give @s minecraft:gunpowder 4")
        host.call("look-at", 6.5, 180.5, 18.5)
        host.call("interact", *CRAFTING_TABLE, "up")
        crafting.distribute(host, crafting.inventory_slot(host, "minecraft:gunpowder"), (101, 103, 105, 107))
        crafting.distribute(host, crafting.inventory_slot(host, "create:cuckoo_clock"), (104,))
        crafting.craft(host, "create:mysterious_cuckoo_clock", 1)
        counts = host.call("inventory")["counts"]
        if counts.get("create:mysterious_cuckoo_clock") != 1 or counts.get("create:cuckoo_clock", 0):
            raise RuntimeError(f"Survival clock recipes left unexpected inventory: {counts}")
        print("Survival crafting produced the regular clock and converted it into the mysterious clock with four gunpowder.")


def run(args):
    crafting_recipes(args)
    with fixture_world(args, "CuckooClockVariants", render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"},
                       artifact_dir=Path("/private/tmp/horizon-app1998-evidence")) as host:
        host.commands((
            "/fill 6 179 17 16 179 24 minecraft:stone",
            "/fill 6 180 17 16 184 24 minecraft:air",
            "/gamemode survival",
            "/give @s create:cuckoo_clock 1",
            "/give @s create:mysterious_cuckoo_clock 1",
        ))
        for block, pos in zip(VARIANTS, TARGETS):
            x, y, z = pos
            # Place the block in ordinary survival first, then connect a motor
            # and shaft through the rear of its actual facing.
            host.command(f"/tp @s {x + 0.5} {y} {z + 3.5}")
            host.call("select", block)
            host.call("look-at", x + 0.5, y + 0.5, z + 0.5)
            host.call("wait", 3)
            host.call("interact", x, y - 1, z, "up")
            state = host.call("block", *pos)["state"]
            if not state.startswith(f"{block}["):
                raise RuntimeError(f"Survival placement of {block} produced {state}")
            if host.call("inventory")["counts"].get(block, 0) != 0:
                raise RuntimeError(f"Survival placement did not consume the {block} item")
            facing = re.search(r"\bfacing=(north|south|east|west)", state)
            if facing is None:
                raise RuntimeError(f"No horizontal facing in placed state {state}")
            rear = {"north": (0, 0, 1), "south": (0, 0, -1),
                    "east": (-1, 0, 0), "west": (1, 0, 0)}[facing.group(1)]
            dx, dy, dz = rear
            host.commands((
                f"/setblock {x + dx} {y + dy} {z + dz} create:shaft[axis={'x' if dx else 'z'}]",
                f"/setblock {x + 2 * dx} {y + 2 * dy} {z + 2 * dz} create:creative_motor[facing={'east' if dx < 0 else 'west' if dx > 0 else 'south' if dz < 0 else 'north'}]",
                f"/data merge block {x + 2 * dx} {y + 2 * dy} {z + 2 * dz} {{ScrollValue:16}}",
            ))
            # Confirm this clock joins the motor network through its rear face.
            host.step_to(host.clock() + 1)
            host.step_to(host.clock() + 1)
            observed = speed(host.command(f"/data get block {x} {y} {z}"))
            if observed != 16:
                raise RuntimeError(f"{block} rear shaft expected 16 RPM, got {observed}")
            print(f"{block}: placed as {state}; rear shaft {observed:g} RPM", flush=True)

        host.restart()
        for block, (x, y, z) in zip(VARIANTS, TARGETS):
            state = host.call("block", x, y, z)["state"]
            if not state.startswith(f"{block}["):
                raise RuntimeError(f"Idle reopen lost {block}: {state}")
            observed = speed(host.command(f"/data get block {x} {y} {z}"))
            if observed != 16:
                raise RuntimeError(f"Idle reopen lost {block}'s connection: {observed} RPM")

        # Noon exercises the Java pig event on the regular clock and the
        # mysterious clock's delayed blast. Keep the two clocks outside each
        # other's 3-block blast radius.
        host.command("/time set 6000")
        host.step_to(host.clock() + 1)
        regular_animation = host.command("/data get block 8 180 20 ClockAnimation")
        mysterious_animation = host.command("/data get block 14 180 20 ClockAnimation")
        if "PIG" not in regular_animation or "SURPRISE" not in mysterious_animation:
            raise RuntimeError(
                "Noon events were not selected: "
                f"regular={regular_animation}; mysterious={mysterious_animation}"
            )
        for key in ("ClockHour", "ClockMinute"):
            reading = host.command(f"/data get block 8 180 20 {key}")
            if not reading.endswith("0"):
                raise RuntimeError(f"Noon clock hand state {key} was not zero: {reading}")
        host.restart()
        state = host.call("block", 14, 180, 20)["state"]
        remaining = 0
        if state.startswith("create:mysterious_cuckoo_clock["):
            reopened_animation = host.command("/data get block 14 180 20 ClockAnimation")
            if "SURPRISE" not in reopened_animation:
                raise RuntimeError(f"Active reopen lost the mysterious event: {reopened_animation}")
            raw_progress = host.command("/data get block 14 180 20 ClockAnimationProgress")
            match = re.search(r"(-?\d+)\s*$", raw_progress)
            if match is None:
                raise RuntimeError(f"Active reopen lost animation progress: {raw_progress}")
            remaining = max(0, 50 - int(match.group(1)))
        elif state != "minecraft:air":
            raise RuntimeError(f"Active reopen produced unexpected clock state: {state}")
        with join_guest(args, host) as guest:
            # The guest performs an ordinary survival placement; the host and
            # guest must see the same facing and block identity.
            for command in (
                "/gamemode survival CuckooGuest",
                "/tp CuckooGuest 10.5 180 23.5",
                "/give CuckooGuest create:cuckoo_clock 1",
            ):
                host.call("command", command)
            mp.until("the guest to receive a cuckoo clock", lambda:
                     guest.call("inventory")["counts"].get("create:cuckoo_clock", 0) == 1)
            guest.call("select", "create:cuckoo_clock")
            guest.call("look-at", 10.5, 180.5, 20.5)
            guest.call("interact", 10, 179, 20, "up")
            mp.until("the host to see the guest's clock", lambda:
                     host.call("block", 10, 180, 20)["block"] == "create:cuckoo_clock")
            guest_state = guest.call("block", 10, 180, 20)["state"]
            host_state = host.call("block", 10, 180, 20)["state"]
            if guest_state != host_state or "facing=" not in guest_state:
                raise RuntimeError(f"Host and guest clock placement differed: {host_state} vs {guest_state}")
            if remaining > 1:
                step_and_wait(host, remaining - 1)
            if host.call("block", 14, 180, 20)["state"].startswith("minecraft:air"):
                raise RuntimeError("Mysterious clock disappeared before animation progress 50")
            if remaining > 0:
                step_and_wait(host, 1)
            if host.call("block", 14, 180, 20)["state"] != "minecraft:air":
                raise RuntimeError("Mysterious clock did not trigger its delayed explosion at progress 50")
            mp.until("the guest to observe the mysterious event", lambda:
                     guest.call("block", 14, 180, 20)["state"] == "minecraft:air")
            if not host.call("block", 8, 180, 20)["state"].startswith("create:cuckoo_clock["):
                raise RuntimeError("Mysterious clock explosion reached the separate regular clock")
        print("Both clocks placed and ran at 16 RPM; idle and active reopen passed; the guest placed a clock with matching host state; the noon surprise removed only the mysterious clock after 50 active ticks and converged to the guest.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, required=True)
    run(parser.parse_args())
