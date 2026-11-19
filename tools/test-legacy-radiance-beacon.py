#!/usr/bin/env python3
"""Replay Chromatic Compound drops above clear and blocked beacon columns."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world, last_command_message, run_command_harness

legacy = import_module("test-legacy-material-float")
mp = legacy.mp
CASES = {"beam": 2, "blocked": 8, "no_beacon": 14}
HEIGHT = 174.5
ENV = {"HORIZON_NO_AUDIO": "1"}


def setup(host):
    host.commands((
        "/fill 1 170 4 3 170 6 minecraft:iron_block",
        "/fill 7 170 4 9 170 6 minecraft:iron_block",
        "/setblock 2 171 5 minecraft:beacon",
        "/setblock 8 171 5 minecraft:beacon",
        "/setblock 8 172 5 minecraft:stone",
        "/setblock 9 170 8 minecraft:stone",
        "/tp @s 9.5 171 8.5",
    ))
    end = host.clock() + 90
    host.command("/tick step 90")
    mp.until("both beacon columns to tick", lambda: host.clock() == end)
    return end


FIELDS = ("Item.id", "Item.count", "Pos[1]", "Motion[1]",
          "NoGravity", "Silent", "NeoForgeData.JustCreated")


def check(row, readings, height=HEIGHT):
    item, count, y, motion, *flags = readings
    assert (item.strip('"'), int(count), *(flag == "1b" for flag in flags)) == (
        row["item"], int(row["count"]),
        *(row[key] == "true" for key in ("no_gravity", "silent", "just_created")),
    ), (row, item, count, flags)
    assert abs(float(y.removesuffix("d")) - height - float(row["y"])) < 3e-7, (row, y)
    assert abs(float(motion.removesuffix("d")) - float(row["motion_y"])) < 3e-7, (row, motion)


def run(args):
    with (ROOT / "fixtures/legacy-radiance-beacon-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    scenario = "LegacyRadianceBeaconLan" if args.lan else "LegacyRadianceBeacon"
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, scenario, pack=args.pack, env=ENV))
        start = setup(host)
        guest = None
        if args.lan:
            port = host.call("lan", "open", "0", "commands")["port"]
            scratch = Path(sessions.enter_context(TemporaryDirectory(prefix="hc-radiance-")))
            guest = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", "RadianceGuest",
                scenario=scenario, pack=args.pack, env=ENV))
            mp.until("the radiance guest to join", lambda: any(
                player["name"] == "RadianceGuest" and player["placed"]
                for player in host.call("lan", "status")["guests"]))
            host.command("/tp RadianceGuest 9.5 171 8.5")
        for case, x in CASES.items():
            host.command(f'/summon minecraft:item {x + .5} {HEIGHT} 5.5 '
                         '{Item:{id:"create:chromatic_compound",count:3},Motion:[0d,0d,0d],'
                         f'PickupDelay:32767s,Tags:["Radiance_{case}"]}}')

        current = 0
        for row in rows:
            tick = int(row["tick"])
            if tick > current:
                assert tick == current + 1
                host.step_to(start + tick)
                current = tick
            selector = f'@e[type=minecraft:item,tag=Radiance_{row["case"]},limit=1]'
            check(row, (legacy.query(host, selector, field) for field in FIELDS))

        if guest:
            mp.until("the Refined Radiance stack to reach the guest", lambda: any(
                entry.get("item", {}).get("item") == "create:refined_radiance"
                and entry["item"]["count"] == 3
                for entry in guest.call("entities", 16, "minecraft:item")["entities"]))
    print(f"Refined Radiance beacon conversion and both controls matched {len(rows)} Java samples.")


def replay_reload(args):
    with (ROOT / "fixtures/legacy-radiance-reload-java.csv").open() as source:
        restored = {int(row["tick"]): row for row in csv.DictReader(source)}
    assert set(restored) == {1, 2}
    with (ROOT / "fixtures/legacy-radiance-beacon-java.csv").open() as source:
        beam = {int(row["tick"]): row for row in csv.DictReader(source) if row["case"] == "beam"}
    selector = "@e[type=minecraft:item,tag=RadianceReload,limit=1]"
    for saved, snapshot in restored.items():
        with fixture_world(args, f"LegacyRadianceReload{saved}", pack=args.pack, env=ENV) as host:
            start = setup(host)
            host.command(f'/summon minecraft:item 2.5 {HEIGHT} 5.5 '
                         '{Item:{id:"create:chromatic_compound",count:3},'
                         'PickupDelay:32767s,Tags:["RadianceReload"]}')
            for tick in range(1, saved + 1):
                host.step_to(start + tick)
            check(beam[saved], (legacy.query(host, selector, field) for field in FIELDS))
            uuid_query = f"/data get entity {selector} UUID"
            uuid = host.command(uuid_query).partition("entity data: ")[2]
            assert uuid.startswith("[I;"), uuid
            game = host.socket.parent / "game"
            host.stop()
            queries = ("/time query gametime", uuid_query,
                       *(f"/data get entity {selector} {field}" for field in FIELDS))
            sample = [{"op": "cmd", "cmd": query} for query in queries]
            operations = [{"op": "settle"}, *sample]
            for _ in range(saved + 1, 9):
                operations.extend(({"op": "tick", "n": 1}, *sample))
            records = run_command_harness(args, game, f"LegacyRadianceReload{saved}",
                                          operations, host.env)
            messages = [last_command_message(record) for record in records]
            assert len(messages) == (9 - saved) * len(queries), messages
            for tick in range(saved, 9):
                offset = (tick - saved) * len(queries)
                clock, identity, *readings = messages[offset:offset + len(queries)]
                assert int(clock.split()[-2]) == start + tick, clock
                assert identity.partition("entity data: ")[2] == uuid, identity
                check(snapshot if tick == saved else beam[tick],
                      (reading.rsplit(" ", 1)[-1] for reading in readings))
    print("Both Java Refined Radiance save points and their following ticks matched a Horizon reopen.")


def replay_charge(args):
    height = 179.5
    component = "create:chromatic_compound_collecting_light"
    selectors = {}
    with (ROOT / "fixtures/legacy-radiance-charge-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    with fixture_world(args, "LegacyRadianceCharge", pack=args.pack, env=ENV) as host:
        setup(host)
        start = host.clock()
        for charge, x in ((9, 5.5), (10, 10.5)):
            selectors[charge] = f"@e[type=minecraft:item,x={x},y={height},z=12.5,distance=..2,limit=1]"
            host.command(f'/summon minecraft:item {x} {height} 12.5 '
                         f'{{Item:{{id:"create:chromatic_compound",count:1,components:{{"{component}":{charge}}}}}}}')
        current = 0
        for row in rows:
            tick = int(row["tick"])
            if tick != current:
                assert tick == current + 1
                host.step_to(start + tick)
                current = tick
            selector = selectors[int(row["charge"])]
            readings = (legacy.query(host, selector, field) for field in FIELDS)
            check(row, readings, height)
            charge = host.command(f'/data get entity {selector} Item.components."{component}"')
            if "entity data: " in charge:
                charge = int(charge.rsplit(" ", 1)[-1])
            else:
                assert charge.startswith("Found no elements"), charge
                charge = 0
            age = int(legacy.query(host, selector, "Age").removesuffix("s"))
            assert (charge, age) == (int(row["stored_charge"]), int(row["age"])), (row, charge, age)
    print(f"Default Refined Radiance light threshold matched {len(rows)} Java samples.")


def replay_collection(args):
    component = "create:chromatic_compound_collecting_light"
    with (ROOT / "fixtures/legacy-radiance-collection-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    for row in rows:
        case = int(row["case"])
        env = {**ENV, "CREATE_RADIANCE_TRACE_SEED": "4100"}
        with fixture_world(args, f"LegacyRadianceCollection{case}", pack=args.pack, env=env) as host:
            block = "stone" if case == 2 else "glowstone"
            host.commands(("/setblock 4 170 8 minecraft:stone",
                           "/tp @s 4.5 171 8.5",
                           f"/setblock 6 178 5 minecraft:{block}"))
            if case == 1:
                host.command("/setblock 4 178 5 minecraft:stone")
            host.command('/summon minecraft:item 3.5 178.5 5.5 '
                         '{Item:{id:"create:chromatic_compound",count:2},'
                         'PickupDelay:32767s,Tags:["RadianceCollection"]}')
            host.step_to(host.clock() + 1)
            near = "@e[type=minecraft:item,x=3.5,y=178.5,z=5.5,distance=..2"
            plain = f"{near},tag=RadianceCollection,limit=1]"
            charged = f"{near},tag=!RadianceCollection,limit=1]"
            match = host.command(f'/execute if block 6 178 5 {row["block"]}')
            assert match.startswith("Test passed"), (
                row, match, host.call("block", 6, 178, 5),
                [host.command(f"/data get entity {entity}") for entity in (plain, charged)],
            )
            assert int(legacy.query(host, plain, "Item.count")) == int(row["plain"]), row
            if int(row["charged"]):
                assert int(legacy.query(host, charged, "Item.count")) == int(row["charged"]), row
                charge = legacy.query(host, charged, f'Item.components."{component}"')
                assert int(charge) == int(row["charge"]), (row, charge)
            else:
                assert host.command(f"/execute if entity {charged}").startswith("Test failed"), row
    print("Visible, occluded and unlit blocks matched Java's first light collection tick.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--lan", action="store_true")
    mode.add_argument("--reload", action="store_true")
    mode.add_argument("--charge", action="store_true")
    mode.add_argument("--collection", action="store_true")
    args = parser.parse_args()
    if args.reload:
        replay_reload(args)
    elif args.charge:
        replay_charge(args)
    elif args.collection:
        replay_collection(args)
    else:
        run(args)
