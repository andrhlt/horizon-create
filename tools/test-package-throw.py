#!/usr/bin/env python3
"""Physically charge and release original Create packages in solo or live LAN."""
import argparse
import csv
from importlib import import_module
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import time

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
BOX = "create:cardboard_package_12x12"
ENTITY = "create:package"
GUEST = "PackageTossGuest"
SUPPLY = "10 203 18"
AT = (13.5, 203.0, 20.5)
SELECTOR = f"@e[type={ENTITY},distance=..8,limit=1,sort=nearest]"
THROW_SOUND = "minecraft:entity.snowball.throw"
CHARGE_EVENT = re.compile(r"CREATE_PACKAGE_CHARGE (tick|release),(\d+)")


def charge_events(host):
    log = host.socket.parent / "ctl.log"
    return [(event, int(ticks)) for event, ticks in CHARGE_EVENT.findall(log.read_text())]


def release(host, actor, charged):
    first = len(charge_events(host))
    if charged == 0:
        actor.call("mouse", "right", "click")
    else:
        actor.call("mouse", "right", "down")
        deadline = time.monotonic() + 70
        try:
            while ("tick", charged - 1) not in charge_events(host)[first:]:
                if time.monotonic() >= deadline:
                    screen = actor.call("state")["screen"]
                    target = actor.call("looking-at")["kind"]
                    raise RuntimeError(f"Use did not reach {charged - 1} on {screen} aiming at {target}: "
                                       f"{charge_events(host)[first:]}")
                time.sleep(.01)
        finally:
            actor.call("mouse", "right", "up")
    multiplayer.until("the server to observe release", lambda: any(
        event == "release" for event, _ in charge_events(host)[first:]))
    results = [value for event, value in charge_events(host)[first:] if event == "release"]
    if results != [charged]:
        raise RuntimeError(f"The attempted {charged}-tick hold produced these releases: {results}")


def package_field(host, field, selector=SELECTOR):
    return host.command(f"/data get entity {selector} {field}")


def package_vector(host, field, selector=SELECTOR):
    value = package_field(host, field, selector)
    match = re.search(r"\[([\-+eE0-9.dD, ]+)\]$", value)
    if not match:
        raise RuntimeError(f"Package {field} returned {value!r}")
    return tuple(float(number.strip().rstrip("dD")) for number in match[1].split(","))


def close(observed, expected, label, tolerance=1e-6):
    if any(abs(a - b) > tolerance for a, b in zip(observed, expected, strict=True)):
        raise RuntimeError(f"{label} was {observed}, Java was {expected}")


def uuid_value(data):
    match = re.search(r"\[I;\s*(-?\d+(?:\s*,\s*-?\d+){3})\]$", data)
    if not match:
        raise RuntimeError(f"Could not read UUID {data!r}")
    return tuple(int(value) for value in match[1].split(","))


def sample_flight(host):
    with (ROOT / "fixtures/package-flight-java.csv").open() as source:
        cases = list(csv.DictReader(source))
    host.command(f"/tag {SELECTOR} add charge-flight")
    flight = f"@e[type={ENTITY},tag=charge-flight,limit=1]"
    start = host.clock()
    anchor = (AT[0] - 3, AT[1] - 2.5, AT[2])
    for row in cases:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        position = tuple(anchor[i] + float(row[axis]) for i, axis in enumerate("xyz"))
        motion = tuple(float(row["d" + axis]) for axis in "xyz")
        close(package_vector(host, "Pos", flight), position, f"flight {tick} position")
        close(package_vector(host, "Motion", flight), motion, f"flight {tick} motion", tolerance=1e-8)
        grounded = bool(int(package_field(host, "OnGround", flight).split()[-1].removesuffix("b")))
        if grounded != (row["on_ground"] == "true"):
            raise RuntimeError(f"Flight {tick} on-ground state was {grounded}, Java was {row['on_ground']}")
    print(f"Matched the original {len(cases)} unlanded Package flight samples.")


def played_throws(client):
    log = client.socket.parent / "ctl.log"
    prefix = "CREATE_ELEVATOR_PLAYBACK "
    frames = []
    for line in log.read_text().splitlines(keepends=True):
        if not line.endswith("\n") or prefix not in line:
            continue
        name, category, x, y, z, gain, pitch = line.split(prefix, 1)[1].split(",")
        if name == THROW_SOUND:
            frames.append((int(category), float(x), float(y), float(z), float(gain), float(pitch)))
    return frames


def expected_sounds():
    with (ROOT / "fixtures/package-throw-sound-java.csv").open() as source:
        return {
            (row["gamemode"], int(row["charged"])): (
                int(row["category"]),
                *(AT[axis] + float(row[key]) for axis, key in enumerate("xyz")),
                float(row["volume"]),
                float(row["pitch"]),
            )
            for row in csv.DictReader(source)
        }


def replay(host, actor, player, args):
    with (ROOT / "fixtures/package-throw-java.csv").open() as source:
        cases = list(csv.DictReader(source))
    host.commands((
        f"/tp {player} {' '.join(map(str, AT))} 0 0",
        "/tick rate 2",
        f"/setblock {SUPPLY} minecraft:barrel",
        f'/data merge block {SUPPLY} {{Items:[{{Slot:0b,id:"{BOX}",count:1,'
        'components:{"create:package_address":"Fixture Address"}}]}',
    ))
    owner = uuid_value(host.command(f"/data get entity {player} UUID"))
    sounds = expected_sounds() if args.sound else {}
    listeners = ((host,) if actor is host else (host, actor)) if args.sound else ()
    if args.flight:
        cases = [row for row in cases if row["gamemode"] == "SURVIVAL" and row["charged"] == "20"]
    for row in cases:
        charged = int(row["charged"])
        if charged == 0 and not args.immediate:
            continue
        if actor.call("entities", 8, ENTITY)["entities"]:
            host.command(f"/kill {SELECTOR}")
            host.command("/tick rate 20")
            done = host.clock() + 24
            host.command("/tick step 24")
            multiplayer.until("the prior Package to leave the world", lambda: host.clock() == done and
                              not actor.call("entities", 8, ENTITY)["entities"])
            host.command("/tick rate 2")
        host.call("command", f"/gamemode {row['gamemode'].lower()} {player}")
        host.command(f"/tp {player} {' '.join(map(str, AT))} 0 0")
        multiplayer.until("the thrower's original feet and direction", lambda:
                          actor.call("state")["player"]["position"] == list(AT))
        host.command(f"/item replace entity {player} hotbar.0 from block {SUPPLY} container.0")
        actor.call("key", "1", "tap")
        multiplayer.until("the addressed package to become held", lambda:
                          (actor.call("inventory")["held"] or {}).get("item") == BOX)
        heard = {client: len(played_throws(client)) for client in listeners}
        release(host, actor, charged)
        expected_held = int(row["held"])
        multiplayer.until("the original held package count", lambda:
                          ((actor.call("inventory")["held"] or {}).get("count", 0)) == expected_held)
        exists = int(row["spawned"])
        multiplayer.until("the original number of packages to be visible", lambda:
                          len(actor.call("entities", 8, ENTITY)["entities"]) == exists)
        for client in listeners:
            wanted = sounds.get((row["gamemode"], charged))
            if wanted:
                multiplayer.until("the package throw to play on the client", lambda:
                                  len(played_throws(client)) > heard[client])
            else:
                client.call("wait", 3)
            observed = played_throws(client)[heard[client]:]
            if observed != ([wanted] if wanted else []):
                raise RuntimeError(f"Package {charged}-tick throw cues were {observed}, Java played {wanted}")
        if not exists:
            continue
        close(package_vector(host, "Pos"), tuple(AT[i] + float(row[axis]) for i, axis in enumerate("xyz")),
              f"{row['gamemode']} {charged}-tick position")
        close(package_vector(host, "Motion"), tuple(float(row["d" + axis]) for axis in "xyz"),
              f"{row['gamemode']} {charged}-tick velocity")
        payload = package_field(host, "equipment.mainhand")
        if row["address"] not in payload or BOX not in payload:
            raise RuntimeError(f"The thrown package lost its address or style: {payload}")
        if owner != uuid_value(package_field(host, "CreatePackageTossedBy")):
            raise RuntimeError("The thrown package lost its server-side owner.")
        if args.flight:
            return sample_flight(host)
    print(f"Matched {len(cases) if args.immediate else len(cases) - 2} original charge cases.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--immediate", action="store_true")
    parser.add_argument("--flight", action="store_true")
    parser.add_argument("--sound", action="store_true")
    args = parser.parse_args()
    os.environ["HORIZON_CREATE_PACKAGE_TRACE"] = "1"
    if args.sound:
        os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    with fixture_world(args, "PackageThrowLAN" if args.lan else "PackageThrow", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 10 202 18 17 202 20 minecraft:stone",
            "/fill 10 195 21 17 204 39 minecraft:air",
        ))
        if args.lan:
            host.command("/tp @s 10.5 203 20.5")
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            with TemporaryDirectory(prefix="hct-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True, scenario="package-toss", pack=args.pack
            ) as guest:
                multiplayer.until("the guest to join", lambda: any(
                    player["name"] == GUEST and player["placed"] for player in host.call("lan", "status")["guests"]))
                replay(host, guest, GUEST, args)
        else:
            replay(host, host, "@s", args)


if __name__ == "__main__":
    main()
