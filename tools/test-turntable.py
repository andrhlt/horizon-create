#!/usr/bin/env python3
"""Replay Java Create's Turntable placement, survival recipe and pig ride."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

crafting = import_module("test-machine-crafting")
entity_data = import_module("test-depot-ejector-obstacle")
multiplayer = import_module("test-multiplayer")
nbt = import_module("test-rotation-speed-controller")

BLOCK = "create:turntable"
TABLE = (9, 171, 21)
SIDE = (12, 171, 21)
ABOVE = (15, 171, 21)
PIG = "@e[type=minecraft:pig,tag=TurntablePig,limit=1]"
GUEST = "TurntableWatcher"


def java(name):
    with (ROOT / "fixtures" / f"turntable-{name}-java.csv").open(newline="") as source:
        return list(csv.DictReader(source))


def craft_and_place(args):
    with fixture_world(args, "TurntableCraftingPlacement", render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as host:
        host.commands((
            "/fill 8 169 22 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
            "/gamemode survival",
        ))
        for row in java("crafting"):
            crafting.replay(host, {**row, "slots": row["inputs"].replace("|", ","), "remainder": ""})
        host.commands((
            "/fill 8 169 22 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:air",
            "/setblock 12 170 25 minecraft:air",
        ))
        target = (12, 170, 25)
        x, y, z = target
        approaches = {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}
        for row in java("placement"):
            dx, dz = approaches[int(row["yaw"])]
            host.commands((
                f"/setblock {nbt.coords(target)} minecraft:air",
                f"/clear @s {BLOCK}",
                f"/item replace entity @s hotbar.0 with {BLOCK}",
                f"/tp @s {x + 0.5 + dx * 2} {y} {z + 0.5 + dz * 2}",
            ))
            host.call("select", BLOCK)
            host.call("look-at", x + 0.5, y, z + 0.5)
            host.call("wait", 3)
            host.call("interact", x, y - 1, z, "up")
            actual = host.call("block", *target)["state"]
            remaining = host.call("inventory")["counts"].get(BLOCK, 0)
            if (actual, remaining) != (row["id"], int(row["item_count"])):
                raise RuntimeError(f"Placement at {row['yaw']}° left {actual}, {remaining} items.")
    print("The original survival recipe and all four placement yaws matched Java.")


def prepare(host):
    host.commands((
        "/fill 7 169 18 16 169 25 minecraft:stone",
        "/fill 7 170 18 16 175 25 minecraft:air",
        f"/setblock {nbt.coords(TABLE)} {BLOCK}",
        f"/setblock {nbt.coords(SIDE)} {BLOCK}",
        f"/setblock {nbt.coords(ABOVE)} {BLOCK}",
        "/setblock 9 170 21 create:creative_motor[facing=up]",
        "/setblock 12 171 20 create:creative_motor[facing=south]",
        "/setblock 15 172 21 create:creative_motor[facing=down]",
        "/tp @s 9.5 170 24.5",
        "/gamerule spawn_mobs false",
    ))


def pigs(actor):
    return [mob for mob in actor.call("mobs", 12)["near"] if mob["kind"] == "minecraft:pig"]


def sample(host, tick):
    replies = host.commands((
        *(f"/data get block {nbt.coords(pos)}" for pos in (TABLE, SIDE, ABOVE)),
        f"/data get entity {PIG}",
    ))
    table, side, above, pig_data = replies
    pig, = pigs(host)
    return {
        "tick": tick,
        "rpm": nbt.tag(table, "Speed", float),
        "side_rpm": nbt.tag(side, "Speed", float),
        "above_rpm": nbt.tag(above, "Speed", float),
        "network_stress": nbt.tag(table, "Stress", float),
        "height": pig["pos"][1] - TABLE[1],
        "yaw": entity_data.vector(pig_data, "Rotation")[0],
        "on_ground": str(pig["on_ground"]).lower(),
    }


def ride(args):
    rows = java("live")
    actual = []
    name = "TurntablePigRideLAN" if args.lan else "TurntablePigRide"
    env = {"HORIZON_NO_AUDIO": "1"}
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, name, env=env, pack=args.pack))
        prepare(host)
        guest = None
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-turntable-")))
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", GUEST,
                scenario=name, pack=args.pack, env=env,
            ))
            multiplayer.until("the guest to join", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.command(f"/tp {GUEST} 10.5 171 23.5")
            multiplayer.until("the guest to receive the Turntable block",
                              lambda: guest.call("block", *TABLE)["state"] == BLOCK)
        start = host.clock()
        for tick in range(1, 25):
            host.step_to(start + tick)
            if tick == 8:
                host.commands((
                    '/summon minecraft:pig 9.5 172.25 21.5 {Tags:["TurntablePig"],Rotation:[90f,0f]}',
                    f"/attribute {PIG} minecraft:movement_speed base set 0",
                ))
            elif tick == 14:
                host.command("/data merge block 9 170 21 {ScrollValue:-16}")
            elif tick == 20:
                host.command("/setblock 9 170 21 minecraft:air")
            if tick >= 8:
                actual.append(sample(host, tick))
        if guest:
            def matching_landing():
                nearby = pigs(guest)
                return len(nearby) == 1 and isclose(
                    nearby[0]["pos"][1] - TABLE[1], actual[-1]["height"],
                    abs_tol=0.002, rel_tol=0.0,
                )

            multiplayer.until("the guest to receive the landed pig", matching_landing)

    with args.output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=actual[0])
        writer.writeheader()
        writer.writerows(actual)

    mismatches = []
    for row, got in zip(rows, actual, strict=True):
        for field in ("tick", "rpm", "side_rpm", "above_rpm", "height", "yaw", "on_ground"):
            want = row[field] if field == "on_ground" else float(row[field])
            tolerance = 0.0001 if field == "yaw" else 2e-7
            equal = got[field] == want if field == "on_ground" else isclose(
                got[field], want, abs_tol=tolerance, rel_tol=0.0
            )
            if not equal:
                mismatches.append((got["tick"], field, want, got[field]))
        stress = abs(float(row["rpm"])) * float(row["stress"])
        if got["network_stress"] != stress:
            mismatches.append((got["tick"], "network_stress", stress, got["network_stress"]))
    if mismatches:
        raise RuntimeError(f"Turntable differed at {len(mismatches)} samples. First {mismatches[:12]}.")
    print(f"Shaft drive, stress, pig height, yaw and on-ground flag matched all {len(actual)} Java ticks.")
    if args.lan:
        print("The guest received the Turntable block and observed the pig at the matching settled height.")


def persistence(args):
    """Check disconnected and driven Turntables across world save/reopen."""
    with fixture_world(args, "TurntablePersistence", pack=args.pack) as host:
        host.commands((
            "/fill 7 169 18 16 169 25 minecraft:stone",
            f"/setblock {nbt.coords(TABLE)} {BLOCK}",
            f"/setblock {nbt.coords((TABLE[0], TABLE[1] - 1, TABLE[2]))} create:shaft[axis=y]",
            f"/setblock {nbt.coords(SIDE)} {BLOCK}",
        ))
        host.call("save")
        host.env["HORIZON_STILL"] = "1"
        host.restart()
        idle = tuple(host.call("block", *pos)["state"] for pos in (
            TABLE, (TABLE[0], TABLE[1] - 1, TABLE[2]), SIDE,
        ))
        if idle[0] != BLOCK or not idle[1].startswith("create:shaft[axis=y") or idle[2] != BLOCK:
            raise RuntimeError(f"Idle Turntable/shaft setup changed across save/reopen: {idle}")

        host.commands((
            f"/setblock {nbt.coords((TABLE[0], TABLE[1] - 1, TABLE[2]))} create:creative_motor[facing=up]",
            "/gamerule spawn_mobs false",
            f'/summon minecraft:pig {TABLE[0] + 0.5} {TABLE[1] + 1.25} {TABLE[2] + 0.5} {{Tags:["TurntablePersistPig"],Rotation:[90f,0f]}}',
            '/attribute @e[type=minecraft:pig,tag=TurntablePersistPig,limit=1] minecraft:movement_speed base set 0',
            f'/summon minecraft:item {TABLE[0] + 0.5} {TABLE[1] + 1.25} {TABLE[2] + 0.5} {{Tags:["TurntablePersistItem"],Item:{{id:"minecraft:iron_ingot",count:1}},PickupDelay:32767s,Motion:[0d,0d,0d]}}',
        ))
        for _ in range(3):
            host.step_to(host.clock() + 1)
        before_data = host.command(f"/data get block {nbt.coords(TABLE)}")
        before_speed = nbt.tag(before_data, "Speed", float)
        if before_speed == 0:
            raise RuntimeError(f"Active Turntable did not receive motor power before save: {before_data}")
        before_yaw = entity_data.vector(host.command(
            "/data get entity @e[type=minecraft:pig,tag=TurntablePersistPig,limit=1]"
        ), "Rotation")[0]
        host.call("save")
        host.restart()
        after_data = host.command(f"/data get block {nbt.coords(TABLE)}")
        after_speed = nbt.tag(after_data, "Speed", float)
        if before_speed != after_speed:
            raise RuntimeError(f"Turntable speed changed across active save/reopen: {before_speed} -> {after_speed}")
        for _ in range(8):
            host.step_to(host.clock() + 1)
            pig_data = host.command("/data get entity @e[type=minecraft:pig,tag=TurntablePersistPig,limit=1]")
            after_yaw = entity_data.vector(pig_data, "Rotation")[0]
            if after_yaw != before_yaw:
                break
        if after_yaw == before_yaw:
            raise RuntimeError(f"Active Turntable did not resume mob contact after reopen: {pig_data}")
        item = host.command(
            '/data get entity @e[type=minecraft:item,tag=TurntablePersistItem,limit=1] Item.count'
        )
        if not item.endswith("1"):
            raise RuntimeError(f"Iron ingot was lost or changed during Turntable contact: {item}")
    print("Idle placement and active shaft drive survived save/reopen; mob contact resumed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/turntable-horizon.csv")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--craft-and-place", action="store_true")
    mode.add_argument("--persistence", action="store_true")
    mode.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.craft_and_place:
        craft_and_place(args)
    elif args.persistence:
        persistence(args)
    else:
        ride(args)


if __name__ == "__main__":
    main()
