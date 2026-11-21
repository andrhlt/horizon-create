#!/usr/bin/env python3
"""Probe vanilla BellBlock hit handling for a Create bell template."""
import argparse
from pathlib import Path
from fixture_world import fixture_world


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ctl", type=Path)
    parser.add_argument("client", type=Path)
    parser.add_argument("resources", type=Path)
    parser.add_argument("--pack", type=Path, required=True)
    args = parser.parse_args()
    pos = (9, 170, 24)
    with fixture_world(args, "Peculiar-haunted-bell-hit", render=True, pack=args.pack,
                       env={"HORIZON_CREATE_ELEVATOR_TRACE": "1"}) as world:
        world.commands((
            "/fill 8 169 22 10 169 26 minecraft:stone",
            "/setblock 9 170 24 create:haunted_bell[facing=north,attachment=floor,powered=false]",
            "/tp @s 9.5 171 26.5",
        ))
        before = world.call("block", *pos)
        world.call("look-at", 9.5, 170.35, 24.5)
        world.call("wait", 2)
        world.call("mouse", "left", "click")
        world.call("wait", 2)
        after = world.call("block", *pos)
        log = world.socket.parent / "ctl.log"
        sounds = [line for line in log.read_text().splitlines() if "bell" in line.lower()] if log.exists() else []
        print(f"before={before['state']} after={after['state']} block={after['block']} sound_or_event_lines={len(sounds)}")
        for line in sounds[-5:]:
            print(line)


if __name__ == "__main__":
    main()
