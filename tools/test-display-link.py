#!/usr/bin/env python3
"""Compare Display Link chest counts, Nixie text, and redstone gating on every tick."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

TEMPLATE = Path("gametest/items/smart_observer_counting.nbt")
BASE = (4, 98, -12)
SINGLE_NIXIE = (2, 2, 1)
DOUBLE_NIXIE = (1, 2, 3)
SINGLE_LINK = (2, 1, 2)
DOUBLE_LINK = (1, 1, 2)
SIGNAL = (3, 1, 2)
CHEST = (3, 1, 1)
OTHER_HALF = (3, 1, 3)


def pos(point):
    return " ".join(str(x + y) for x, y in zip(BASE, point, strict=True))


def sample(control):
    rows = control.commands((
        *(f"/data get block {pos(tube)} CustomText" for tube in (SINGLE_NIXIE, DOUBLE_NIXIE)),
        *(f"/execute if block {pos(link)} create:display_link[powered=true]"
          for link in (SINGLE_LINK, DOUBLE_LINK)),
    ))
    texts = []
    for row in rows[:2]:
        result = re.search(r'"text"\s*:\s*"(\d+)"', row.replace('\\\"', '"'))
        if not result:
            raise RuntimeError(f"Unexpected Nixie text: {row}")
        texts.append(result[1])
    return (*texts, *("true" if "Test passed" in reply else "false" for reply in rows[2:]))


def run(args):
    fixture = ROOT / "fixtures/display_link-java.csv"
    with fixture.open() as data:
        expected = tuple(csv.DictReader(data))
    with fixture_world(args, "Display-link", TEMPLATE, render=args.visual, pack=args.pack) as control:
        control.command(f"/place template create:gametest/items/smart_observer_counting {' '.join(map(str, BASE))}")
        start = control.clock()
        result = ROOT / ".local/display_link-horizon.csv"
        keys = ("single", "double", "single_powered", "double_powered")
        with result.open("w") as out:
            writer = csv.writer(out)
            writer.writerow(("tick", *keys))
            for row in expected:
                tick = int(row["tick"])
                if tick:
                    control.step_to(start + tick)
                values = sample(control)
                writer.writerow((tick, *values))
                wanted = tuple(row[k] for k in keys)
                if values != wanted:
                    raise RuntimeError(f"Tick {tick}: Horizon {values}, Java {wanted}")
                if tick == 5:
                    control.commands((
                        f"/item replace block {pos(CHEST)} container.0 with minecraft:iron_ingot 7",
                        f"/item replace block {pos(OTHER_HALF)} container.0 with minecraft:gold_ingot 13",
                    ))
                elif tick == 108:
                    control.command(f"/setblock {pos(SIGNAL)} minecraft:redstone_block")
                elif tick == 111:
                    control.command(f"/item replace block {pos(CHEST)} container.0 with minecraft:iron_ingot 4")
                elif tick == 125:
                    control.command(f"/setblock {pos(SIGNAL)} minecraft:air")
        if args.visual:
            x, y, z = BASE
            control.command("/time set noon")
            control.command(f"/tp @s {x - 3.0} {y + 3.0} {z + 1.5}")
            control.call("wait", 3)
            control.call("look-at", x + 2.0, y + 1.6, z + 2.2)
            control.call("key", "f1", "tap")
            control.call("wait", 4)
            control.call("screenshot", ROOT / ".local/display-link.png")
    print(f"Display Link counts and redstone gating matched all {len(expected)} Java ticks.")


def configure(args):
    with fixture_world(args, "Display-link-setup", TEMPLATE, render=True, pack=args.pack) as control:
        control.commands((
            f"/place template create:gametest/items/smart_observer_counting {' '.join(map(str, BASE))}",
            f"/setblock {pos(SINGLE_LINK)} minecraft:air",
            "/fill 5 98 -9 8 98 -7 minecraft:smooth_stone",
            "/gamemode survival",
            "/tp @s 6.5 99 -7.7 180 -5",
            "/item replace entity @s hotbar.0 with create:display_link 2",
        ))
        control.call("wait", 3)
        control.call("key", "1", "tap")
        # The Java floor shape has a gap between its two tubes at the block center.
        x, y, z = target = tuple(map(int, pos(SINGLE_NIXIE).split()))
        control.call("look-at", x + 0.25, y + 0.43, z + 0.5)
        control.call("wait", 4)
        hit = control.call("looking-at").get("block")
        assert hit and hit["pos"] == list(target), hit
        control.call("mouse", "right", "click")
        control.call("wait", 3)
        inventory = control.command("/data get entity @s Inventory")
        if "create:click_to_link_data" not in inventory:
            raise RuntimeError(f"Nixie was not selected: {inventory}")
        observer = tuple(map(int, pos((2, 1, 1)).split()))
        control.call("interact", *observer, "south")
        control.call("wait", 3)
        data = control.command(f"/data get block {pos(SINGLE_LINK)} TargetOffset")
        if "[I; 0, 1, -1]" not in data:
            raise RuntimeError(f"New link has the wrong target offset: {data}")
        inventory = control.command("/data get entity @s Inventory")
        if "create:click_to_link_data" in inventory or "count: 1" not in inventory:
            raise RuntimeError(f"Placing the configured link did not spend one item: {inventory}")
        control.command(f"/item replace block {pos(CHEST)} container.0 with minecraft:iron_ingot 7")
        control.call("key", "2", "tap")
        control.commands((
            "/setblock 9 98 -10 minecraft:smooth_stone",
            "/tp @s 9.2 99 -9.5 90 15",
        ))
        control.call("wait", 3)
        control.step_to(control.clock() + 1)
        control.call("look-at", 6.7, 99.35, -9.5)
        control.call("wait", 3)
        control.call("mouse", "right", "click")
        control.call("wait", 5)
        control.call("click-button", "Amount of matching Items")
        control.call("wait", 3)
        values = sample(control)
        if values != ("17", "40", "false", "false"):
            raise RuntimeError(f"Link settings did not publish the chosen source: {values}")
        if args.visual:
            control.call("screenshot", ROOT / ".local/display-link-settings.png")
    print("Survival placement selected the Nixie, spent one Display Link, and configured the live count.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--configure", action="store_true")
    args = parser.parse_args()
    (configure if args.configure else run)(args)
