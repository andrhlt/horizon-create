#!/usr/bin/env python3
"""Replay original Create package placement through both actual Horizon clients."""
import argparse
import csv
import math
import struct
import re
import uuid
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

package = import_module("test-package-open")
editor = package.editor
TARGET = (8, 104, -12)
CENTER = tuple(value + 0.5 for value in TARGET)
ENTITY = "create:package"
TRACE = "CREATE_PACKAGE_SPAWN "
DIRECTIONS = {
    "down": (0, -1, 0), "up": (0, 1, 0),
    "north": (0, 0, -1), "south": (0, 0, 1),
    "west": (-1, 0, 0), "east": (1, 0, 0),
}


def witness(peer):
    return peer.call("entities", 16, ENTITY)["entities"]


def teleport(host, actor, name, at):
    host.command(f"/tp {name} {editor.xyz(at)}")
    editor.wait_for(actor, "the placer to reach the original face", lambda:
        tuple(actor.call("state")["player"]["position"][:3]) == at
    )


def approach(host, actor, name, direction, *, repeat=False):
    x, _, z = CENTER
    fx, fy, fz = direction
    point = tuple(origin + face * 0.5 for origin, face in zip(CENTER, direction, strict=True))
    if fy > 0:
        feet = (6.5, 105.0, z)
        if repeat:
            point = (point[0] - .45, point[1], point[2])
    elif fy < 0:
        feet = (x - .45 if repeat else x, 101.0, z)
        if repeat:
            point = (point[0] - .45, point[1], point[2])
    else:
        feet = (x + fx * 2.5, 101.0, z + fz * 2.5)
        if repeat:
            point = (point[0], point[1] - .4, point[2])
    teleport(host, actor, name, feet)
    actor.call("look-at", *point)
    face = next(face for face, normal in DIRECTIONS.items() if normal == direction)
    def targeted():
        pick = actor.call("looking-at")
        block = pick.get("block") or {}
        return pick.get("kind") == "block" and block.get("pos") == list(TARGET) and block.get("face") == face

    editor.wait_for(actor, "the original unobstructed block face", targeted)
    actual = tuple(actor.call("looking-at")["block"]["point"])
    assert same(actual, point, 5e-4), (direction, actual, point)
    return actual, point


def action(host, actor):
    tick = host.clock()
    actor.call("wait", 6)
    actor.call("mouse", "right", "click")
    actor.call("wait", 6)
    assert host.clock() == tick


def wait_for_guest_pose(host, actor, name):
    def server_vector(field):
        text = host.command(f"/data get entity {name} {field}").split("entity data: ", 1)[1]
        return tuple(float(value) for value in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?=[df])", text))

    def synced():
        player = actor.call("state")["player"]
        position = server_vector("Pos")
        rotation = server_vector("Rotation")
        return (len(position) == 3 and len(rotation) == 2
                and same(position, player["position"][:3], .01)
                and all(abs((a - b + 180) % 360 - 180) < .01
                        for a, b in zip(rotation, (player["yaw"], player["pitch"]), strict=True)))

    editor.wait_for(actor, "the guest pose to reach the server", synced)


def block_use(host, actor, name, direction, expected_hit):
    """Send exactly one guest block-use packet, then fence it on that connection."""
    tick = host.clock()
    actor.call("wait", 6)
    wait_for_guest_pose(host, actor, name)
    hit = actor.call("fixture-use-block")
    assert hit["block"] == list(TARGET) and hit["face"] == list(direction), hit
    assert same(hit["point"], expected_hit, 5e-4), (hit, expected_hit)
    # Await a unique server message sent after UseItemOn on this connection.
    marker = f"PackageUseFence-{uuid.uuid4().hex}"
    actor.call("command", f'/tellraw @s {{"text":"{marker}"}}')
    editor.wait_for(actor, "the server to process the block-use packet", lambda:
                    marker in actor.call("chat-log", 40)["chat"])
    actor.call("wait", 6)
    assert host.clock() == tick
    return tuple(hit["point"])


def live_repeat(host, actor, name, direction, expected_hit, stored, entity_id, row):
    """Check live fallback against Java using the host-observed release duration."""
    log = host.socket.parent / "ctl.log"
    offset = len(log.read_bytes())
    if actor is not host:
        wait_for_guest_pose(host, actor, name)
    pick = actor.call("looking-at")
    assert pick.get("kind") == "block" and pick["block"]["pos"] == list(TARGET), pick
    assert DIRECTIONS[pick["block"]["face"]] == direction, pick
    assert same(pick["block"]["point"], expected_hit, 5e-4), pick
    tick = host.clock()
    actor.call("mouse", "right", "click")
    def release_ticks():
        suffix = log.read_bytes()[offset:].decode(errors="replace")
        lines = suffix.splitlines(keepends=True)
        releases = [int(match[1]) for line in lines if line.endswith("\n")
                    if (match := re.search(r"CREATE_PACKAGE_CHARGE release,(\d+)", line))]
        return releases or None
    editor.wait_for(actor, "the server to observe the package release", release_ticks)
    charges = release_ticks()
    assert len(charges) == 1, charges
    charged = charges[0]
    actor.call("wait", 6)
    assert host.clock() == tick
    thrown = charged >= 3
    expected_count = int(row["repeat_held"]) - int(thrown and row["gamemode"] == "SURVIVAL")
    held = host.command(f"/data get entity {name} SelectedItem")
    if expected_count:
        assert package.parse(held.split("entity data: ", 1)[1]) == stored, (row, charged, held)
    else:
        assert "Found no elements" in held, (row, charged, held)
    editor.wait_for(actor, "the released package result to reach the client", lambda:
        actor.call("inventory")["counts"].get(row["item"], 0) == expected_count
        and len(witness(actor)) == 1 + int(thrown))
    entities = witness(host)
    assert len(entities) == 1 + int(thrown), (charged, entities)
    assert sum(entity["id"] == entity_id for entity in entities) == 1, entities
    if thrown:
        box = next(entity for entity in entities if entity["id"] != entity_id)
        item, frame = trace(host, box["id"])
        assert item == row["item"] and same(frame[3:], (float(row["width"]), float(row["height"]))), (row, frame)
        x, y, z = box["pos"]
        selector = f"@e[type={ENTITY},distance=..0.1,limit=1,sort=nearest]"
        prefix = f"/execute positioned {x:.9f} {y:.9f} {z:.9f} run "
        contents = host.command(prefix + f"data get entity {selector} equipment.mainhand")
        assert package.parse(contents.split("entity data: ", 1)[1]) == stored, (row, contents)
        owner = host.command(prefix + f"data get entity {selector} CreatePackageTossedBy")
        player_uuid = host.command(f"/data get entity {name} UUID")
        owner_id = re.search(r"\[I;[^]]+\]", owner)
        player_id = re.search(r"\[I;[^]]+\]", player_uuid)
        assert owner_id and player_id and owner_id[0] == player_id[0], (owner, player_uuid)
        motion = host.command(prefix + f"data get entity {selector} Motion")
        values = tuple(float(value) for value in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?=d)", motion))
        assert len(values) == 3, motion
        f32 = lambda v: struct.unpack("f", struct.pack("f", v))[0]
        ratio = f32(charged / 20.0)
        strength = min(f32(f32(f32(ratio * ratio) + f32(ratio * 2.0)) / 3.0), 1.0)
        speed = f32(strength * 2.0)
        # Vanilla table-based sine/cosine is not exactly unit length.
        assert math.isclose(math.sqrt(sum(v*v for v in values)), speed, abs_tol=2e-4), (charged, values, speed)
        host.command(prefix + f"kill {selector}")
        editor.wait_for(actor, "the observed thrown package to be removed", lambda:
            [entity["id"] for entity in witness(actor)] == [entity_id])
    print(f"LIVE_REPEAT charged={charged} thrown={thrown} held={expected_count}", flush=True)


def put_sample(host, actor, name, item, address):
    teleport(host, actor, name, package.FEET)
    source = (
        f'{{id:"{item}",count:1,components:{{"create:package_address":"{address}",'
        '"create:package_contents":[{slot:0,item:{id:"minecraft:stone",count:3}}]}}'
    )
    package.seed_package(host, actor, name, source)


def trace(host, entity_id):
    for line in (host.socket.parent / "ctl.log").read_text().splitlines():
        if TRACE not in line:
            continue
        entity, item, x, y, z, width, height = line.split(TRACE, 1)[1].split(",")
        if int(entity) == entity_id:
            return item, tuple(map(float, (x, y, z, width, height)))
    raise AssertionError(f"Missing package creation trace for entity {entity_id}.")


def same(lhs, rhs, tolerance=1e-6):
    return all(abs(a - b) <= tolerance for a, b in zip(lhs, rhs, strict=True))


def run_case(host, actor, name, row, screenshot, *, guest_block_use=False):
    face, item = row["face"], row["item"]
    direction = DIRECTIONS[face]
    expected = tuple(origin + float(row[axis]) for origin, axis in zip(CENTER, "xyz", strict=True))
    dims = tuple(float(row[key]) for key in ("width", "height"))
    host.call("command", f"/gamemode {row['gamemode'].lower()} {name}")
    host.call("command", f"/setblock 6 104 -12 {'minecraft:stone' if face == 'up' else 'minecraft:air'}")
    put_sample(host, actor, name, item, row["address"])
    actual_hit, face_center = approach(host, actor, name, direction)
    if guest_block_use:
        actual_hit = block_use(host, actor, name, direction, actual_hit)
    else:
        action(host, actor)
    # Java sends an exact face centre directly. The recording uses a real
    # viewport ray whose f32 aim can differ slightly from that input.
    expected = tuple(at + actual - nominal for at, actual, nominal in zip(
        expected, actual_hit, face_center, strict=True,
    ))
    for peer in (host,) if actor is host else (host, actor):
        editor.wait_for(peer, "the newly placed package to appear", lambda:
            len(witness(peer)) == int(row["placed"])
        )
        assert same(witness(peer)[0]["pos"], expected), (row, witness(peer))
    entity_id = witness(host)[0]["id"]
    seen_item, frame = trace(host, entity_id)
    assert seen_item == item and same(frame, (*expected, *dims)), (row, frame)
    data = host.command(f"/data get entity @e[type={ENTITY},limit=1] equipment.mainhand")
    stored = package.parse(data.split("entity data: ", 1)[1])
    assert stored["id"] == item and stored["count"] == 1, stored
    assert stored["components"]["create:package_address"] == row["address"], stored
    assert stored["components"]["create:package_contents"] == [
        {"slot": 0, "item": {"id": "minecraft:stone", "count": 3}},
    ], stored
    assert actor.call("inventory")["counts"].get(item, 0) == int(row["held"]), row
    if screenshot:
        actor.call("screenshot", screenshot)

    put_sample(host, actor, name, item, row["address"])
    repeat_hit, _ = approach(host, actor, name, direction, repeat=True)
    if guest_block_use:
        block_use(host, actor, name, direction, repeat_hit)
        authority = host.command(f"/data get entity {name} SelectedItem")
        assert package.parse(authority.split("entity data: ", 1)[1]) == stored, (row, authority)
        assert actor.call("inventory")["counts"].get(item, 0) == int(row["repeat_held"]), row
    else:
        live_repeat(host, actor, name, direction, repeat_hit, stored, entity_id, row)
    assert [entity["id"] for entity in witness(host)] == [entity_id], row
    assert actor.call("state")["screen"] == "playing", row

    host.call("command", f"/clear {name}")
    editor.wait_for(actor, "the empty hand before picking up the package", lambda:
        actor.call("inventory")["held"] is None
    )
    actor.call("look-at", expected[0], expected[1] + dims[1] * .5, expected[2])
    action(host, actor)
    editor.wait_for(actor, "the original package to return to the empty hand", lambda:
        actor.call("inventory")["counts"].get(item) == 1 and not witness(actor)
    )
    returned = package.parse(host.command(f"/data get entity {name} SelectedItem").split("entity data: ", 1)[1])
    assert returned == stored, (returned, stored)
    assert not witness(host)
    print(f"{row['gamemode']} {item} {face}", flush=True)


def measured(args, scratch):
    reference = args.reference or ROOT / "fixtures/package-place-java.csv"
    with reference.open(newline="") as source:
        rows = list(csv.DictReader(source))
    if args.reference is None:
        assert len(rows) == 36
    if args.case:
        rows = [rows[index] for index in args.case]
    world = "PackagePlacementGuestUseOn" if args.guest_block_use else (
        "PackagePlacementGuest" if args.lan else "PackagePlacementHost"
    )
    with fixture_world(args, world, render=True, env={"HORIZON_CREATE_PACKAGE_TRACE": "1"}, pack=args.pack) as host:
        host.commands((
            "/fill 4 100 -16 16 100 -4 minecraft:smooth_stone",
            "/fill 4 101 -16 16 112 -4 minecraft:air",
            f"/setblock {editor.xyz(TARGET)} minecraft:stone",
        ))
        env = {"HORIZON_FIXTURE_USE_BLOCK": "1"} if args.guest_block_use else None
        with package.filters.actor_for(host, args, scratch if args.lan else None, env=env) as (actor, name):
            for row in rows:
                filename = f"{world}-{row['gamemode']}-{row['style']}-{row['face']}.png"
                screenshot = args.shot_dir / filename if args.shot_dir else None
                run_case(host, actor, name, row, screenshot, guest_block_use=args.guest_block_use)
    print(f"{'Guest' if args.lan else 'Host'} matched {len(rows)} original package placement cases.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ("ctl", "client", "resources"):
        parser.add_argument(parameter, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--guest-block-use", action="store_true",
                        help="send a single block-use packet from the LAN guest")
    parser.add_argument("--case", type=int, action="append")
    parser.add_argument("--shot-dir", type=Path)
    args = parser.parse_args()
    if args.guest_block_use and not args.lan:
        parser.error("--guest-block-use requires --lan")
    if args.shot_dir:
        args.shot_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="hc-package-placement-") as directory:
        measured(args, Path(directory))


if __name__ == "__main__":
    main()
