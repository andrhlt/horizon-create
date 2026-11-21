#!/usr/bin/env python3
"""Check standalone train trapdoor states across a cold world reopen."""

import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

trapdoors = import_module("test-train-trapdoors")
mp = import_module("test-multiplayer")
nozzle = import_module("test-nozzle")

CASES = (
    ("create:train_trapdoor", (8, 172, 22), False),
    ("create:framed_glass_trapdoor", (14, 172, 22), True),
)


def block_state(block, opened):
    return f"{block}[facing=north,half=bottom,open={str(opened).lower()},powered=false,waterlogged=false]"


def replay(args):
    with fixture_world(args, "TrainTrapdoorsReopen", render=True, pack=args.pack) as control:
        for block, at, opened in CASES:
            control.command(f"/setblock {trapdoors.xyz((at[0], at[1] - 1, at[2]))} minecraft:stone")
            control.command(f"/setblock {trapdoors.xyz(at)} {block_state(block, opened)}")
            expected = block_state(block, opened)
            mp.until(f"{block} to reach its saved {opened=}",
                     lambda at=at, expected=expected: nozzle.state(control, at) == expected)

        before = {at: nozzle.state(control, at) for _, at, _ in CASES}
        control.stop()
        control.open()
        after = {at: nozzle.state(control, at) for _, at, _ in CASES}
        assert after == before, {"before": before, "after": after}

        for block, at, was_open in CASES:
            expected = block_state(block, not was_open)
            # Toggle each restored state by hand, then confirm its resulting block state.
            x, y, z = at
            feet = (x + 0.5, y, z - 2.5)
            control.commands((f"/setblock {trapdoors.xyz((x, y - 1, z - 2))} minecraft:stone",
                              f"/tp @s {trapdoors.xyz(feet)}"))
            mp.until("the player to reach the reopened trapdoor", lambda feet=feet:
                     control.call("state")["player"]["position"] == list(feet))
            target = (x + 0.5, y + (0.6 if was_open else 0.09), z + 0.9)
            nozzle.aim(control, target, at)
            control.call("wait", 2)
            control.call("mouse", "right", "click")
            mp.until(f"{block} to toggle after reopen", lambda at=at, expected=expected:
                     nozzle.state(control, at) == expected)

    print("Closed/open states for both trapdoors survived cold reopen and remained usable.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    replay(parser.parse_args())
