#!/usr/bin/env python3
"""Compare ordinary Stockpile Switch placement and attached inventory sensing."""

import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


ITEM = "create:stockpile_switch"
POSITION = (8, 102, -9)
DIRECTIONS = {
    "east": (1, 0, 0), "west": (-1, 0, 0),
    "up": (0, 1, 0), "down": (0, -1, 0),
    "south": (0, 0, 1), "north": (0, 0, -1),
}
spec = spec_from_file_location("stockpile_editor", ROOT / "tools/test-stockpile-switch-editor.py")
editor = module_from_spec(spec)
spec.loader.exec_module(editor)


def offset(direction, sign=1):
    return tuple(value + sign * shift for value, shift in zip(POSITION, DIRECTIONS[direction], strict=True))


def setup(control, support, block, neighbors):
    control.commands((
        "/fill 4 100 -14 13 100 -4 minecraft:smooth_stone",
        "/fill 4 101 -14 13 108 -4 minecraft:air",
        f"/setblock {editor.xyz(support)} {block}",
        *(f"/setblock {editor.xyz(offset(direction))} minecraft:barrel"
          for direction in neighbors),
    ))


def expected(facing, mount):
    return f"{ITEM}[facing={facing},level=0,powered=false,target={mount}]"


def verify(args):
    reference = ROOT / "fixtures/stockpile-switch-placement-java.csv"
    with reference.open(newline="") as source:
        rows = list(csv.reader(source))
    assert len(rows) == 12
    with fixture_world(args, "StockpileSwitchPlacement", render=True, pack=args.pack) as control:
        control.command("/gamemode survival")
        for row in rows:
            case, block, face, yaw, pitch, sneaking, around, facing, mount, consumed = row
            support = offset(face, -1)
            neighbors = [] if around == "-" else around.split("+")
            setup(control, support, block, neighbors)
            dx, dy, dz = DIRECTIONS[face]
            px, py, pz = POSITION
            feet = (px + .5 + 2 * dx + 2 * abs(dy), py - 1 + int(dy > 0) * 3, pz + .5 + 2 * dz)
            if dy > 0:
                control.command(f"/setblock {px + 2} {py + 1} {pz} minecraft:smooth_stone")
            control.commands((
                f"/tp @s {editor.xyz(feet)} {yaw} {pitch}",
                f"/item replace entity @s hotbar.0 with {ITEM}",
            ))
            control.call("wait", 3)
            control.call("select", ITEM)
            if sneaking == "true":
                control.call("key", "shift", "down")
                control.call("wait", 2)
            try:
                result = control.call("interact", *support, face)
            finally:
                if sneaking == "true":
                    control.call("key", "shift", "up")
            assert consumed == "true" and result.get("inventory_change", {}).get(ITEM) == -1, (case, row, result)
            placed = control.call("block", *POSITION)["state"]
            assert placed == expected(facing, mount), (case, row, placed)
    print("All twelve Java placement cases matched: all mount faces, fluid target, conflicting inventories and sneaking fallback.")


def verify_lan(args, scratch):
    multiplayer = editor.load_multiplayer()
    support = offset("north", -1)
    name = "StockpileMount"
    with fixture_world(args, "StockpileMountLAN", render=True, pack=args.pack) as host:
        setup(host, support, "minecraft:barrel", ())
        host.commands((
            f"/item replace block {editor.xyz(support)} container.0 with minecraft:stone 32",
            "/tp @s 11.5 101 -8.5",
        ))
        address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
        with multiplayer.joined_client(
            args, scratch, address, name, render=True, scenario="stockpile-placement", pack=args.pack,
        ) as guest:
            multiplayer.until("the Stockpile Switch placer to join", lambda: any(
                player["name"] == name and player["placed"] for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {name}",
                f"/tp {name} 8.5 101 -11.5",
                f"/item replace entity {name} hotbar.0 with {ITEM}",
            ))
            editor.wait_for(guest, "the guest to reach the barrel with the Stockpile Switch", lambda:
                guest.call("state")["player"]["position"][:3] == [8.5, 101., -11.5]
                and guest.call("inventory")["counts"].get(ITEM) == 1
            )
            guest.call("select", ITEM)
            guest.call("key", "shift", "down")
            try:
                guest.call("look-at", 8.5, 102.5, -8.001)
                guest.call("wait", 3)
                hit = guest.call("looking-at").get("block")
                assert hit and hit["pos"] == list(support) and hit["face"] == "north", hit
                guest.call("mouse", "right", "click")
                multiplayer.until("the host and guest to see the switch face the barrel", lambda: all(
                    peer.call("block", *POSITION)["state"] == expected("south", "wall")
                    for peer in (host, guest)
                ))
            finally:
                guest.call("key", "shift", "up")
            host.step_to(host.clock() + 1)
            data = host.command(f"/data get block {editor.xyz(POSITION)}")
            assert editor.field(data, "CurrentAmount") == 32, data
            assert guest.call("inventory")["counts"].get(ITEM, 0) == 0
    print("A live guest placed the sensor on the barrel, and the host immediately measured the correct attached stock.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-stpp-") as scratch:
            verify_lan(args, Path(scratch))
    else:
        verify(args)


if __name__ == "__main__":
    main()
