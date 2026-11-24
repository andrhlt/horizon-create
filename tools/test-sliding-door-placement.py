#!/usr/bin/env python3
"""Check survival placement of folding and sliding Create doors."""

import argparse
from importlib import import_module
import json
from pathlib import Path

from fixture_world import fixture_world

multiplayer = import_module("test-multiplayer")


FACES = {
    "north": ((0, 0, -1), (0.5, 0.75, 0.001)),
    "south": ((0, 0, 1), (0.5, 0.75, 0.999)),
    "east": ((1, 0, 0), (0.999, 0.75, 0.5)),
    "west": ((-1, 0, 0), (0.001, 0.75, 0.5)),
}


def block_state(world, pos):
    return world.call("block", *pos)["state"]


def place(world, material, facing, index):
    delta, hit_offset = FACES[facing]
    start_tick = world.clock()
    support = (8 + index * 8, 170, 8)
    target = tuple(value + step for value, step in zip(support, delta, strict=True))
    feet = tuple(value + step * 3 for value, step in zip(support, delta, strict=True))
    feet = (feet[0] + 0.5, feet[1], feet[2] + 0.5)
    floor = (int(feet[0]), 169, int(feet[2]))
    player = "@s"
    world.call("script", script="".join(f"command {json.dumps(command)}\n" for command in (
        f"/setblock {floor[0]} {floor[1]} {floor[2]} minecraft:stone",
        f"/setblock {support[0]} {support[1]} {support[2]} minecraft:stone",
        f"/gamemode survival {player}",
        f"/clear {player}",
        f"/item replace entity {player} hotbar.0 with create:{material}_door 1",
        f"/tp {player} {feet[0]} {feet[1]} {feet[2]}",
    )))
    multiplayer.until("survival door item and player position", lambda:
                     world.call("inventory")["counts"].get(f"create:{material}_door") == 1
                     and world.call("state")["player"]["position"] == list(feet))
    world.call("select", f"create:{material}_door")
    point = tuple(value + offset for value, offset in zip(support, hit_offset, strict=True))
    world.call("look-at", *point)
    def intended_face():
        result = world.call("looking-at").get("block") or {}
        return result if result.get("pos") == list(support) and result.get("face") == facing else None

    hit = multiplayer.until("the intended support face", intended_face)
    assert hit["face"] == facing, hit
    world.call("wait", 2)
    world.call("mouse", "right", "click")
    door_facing = {"north": "south", "south": "north", "east": "west", "west": "east"}[facing]
    lower = f"create:{material}_door[facing={door_facing},half=lower,hinge=left,open=false,powered=false,visible=true]"
    upper = f"create:{material}_door[facing={door_facing},half=upper,hinge=left,open=false,powered=false,visible=true]"
    multiplayer.until(f"the {material} {facing} two-block door placement", lambda:
                     block_state(world, target) == lower
                     and block_state(world, (target[0], target[1] + 1, target[2])) == upper
                     and world.call("inventory")["counts"].get(f"create:{material}_door", 0) == 0)
    assert world.clock() == start_tick
    print(f"{material} {facing}: both Java placement states matched; one item consumed.", flush=True)
    return target, door_facing


def reopen_states(world, opened, closed):
    open_pos, open_facing = opened
    closed_pos, closed_facing = closed
    states = (
        (open_pos, f"create:andesite_door[facing={open_facing},half=lower,hinge=left,open=true,powered=false,visible=false]"),
        ((open_pos[0], open_pos[1] + 1, open_pos[2]), f"create:andesite_door[facing={open_facing},half=upper,hinge=left,open=true,powered=false,visible=false]"),
        (closed_pos, f"create:brass_door[facing={closed_facing},half=lower,hinge=left,open=false,powered=false,visible=true]"),
        ((closed_pos[0], closed_pos[1] + 1, closed_pos[2]), f"create:brass_door[facing={closed_facing},half=upper,hinge=left,open=false,powered=false,visible=true]"),
    )
    for pos, state in states:
        world.command(f"/setblock {pos[0]} {pos[1]} {pos[2]} {state}")
    world.restart()
    for pos, expected in states:
        multiplayer.until(f"saved door state at {pos}", lambda: block_state(world, pos) == expected)
    print("Open Andesite and closed Brass pairs retained both halves through cold reopen.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with fixture_world(args, "SlidingDoorPlacement", render=True, pack=args.pack) as world:
        placed = []
        for index, (material, facing) in enumerate((
            ("andesite", "north"), ("andesite", "east"),
            ("brass", "south"), ("brass", "west"),
        )):
            placed.append(place(world, material, facing, index))
        reopen_states(world, placed[0], placed[2])
    print("All four survival sliding-door placement cases matched Java.")


if __name__ == "__main__":
    main()
