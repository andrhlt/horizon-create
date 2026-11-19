#!/usr/bin/env python3
"""Exercise wirelessly relayed analog power, ordered frequencies, and receiver setup."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/misc/threshold_switch_pulley.nbt")
BASE = (8, 180, 8)
LINK = "create:redstone_link"
SENDERS = ((0, 0, 0), (7, 0, 0))
RECEIVERS = ((12, 0, 0), (16, 0, 0))
LAMP = (11, 0, 0)
SOURCE_A = (0, 0, -1)
SOURCE_B = (7, 0, 2)
KEYS = ("tx_a", "tx_a_powered", "tx_b", "tx_b_powered",
        "rx_a", "rx_a_powered", "rx_b", "rx_b_powered", "lamp")


def xyz(local):
    return tuple(x + y for x, y in zip(BASE, local, strict=True))


def pos(local):
    return " ".join(map(str, xyz(local)))


def channel(primary):
    a, b = ("minecraft:quartz", "minecraft:iron_ingot") if primary else ("minecraft:iron_ingot", "minecraft:quartz")
    return f'{{FrequencyFirst:{{id:"{a}",count:1}},FrequencyLast:{{id:"{b}",count:1}}}}'


def setup(control):
    control.commands((
        "/fill 5 179 5 31 179 11 minecraft:smooth_stone",
        *(f"/setblock {pos(at)} {LINK}[facing=up,receiver=false]{channel(True)}" for at in SENDERS),
        *(f"/setblock {pos(at)} {LINK}[facing=up,receiver=true]{channel(i == 0)}" for i, at in enumerate(RECEIVERS)),
        f"/setblock {pos(LAMP)} minecraft:redstone_lamp",
        f"/setblock {pos((7, 0, 1))} minecraft:comparator[facing=south]",
        f"/setblock {pos(SOURCE_B)} minecraft:composter[level=0]",
    ))


def sample(control):
    names = ("Transmit", "Transmit", "Receive", "Receive")
    pulse = control.commands((
        *(f"/data get block {pos(at)} {name}" for at, name in zip((*SENDERS, *RECEIVERS), names, strict=True)),
        *(f"/execute if block {pos(at)} {LINK}[powered=true]" for at in (*SENDERS, *RECEIVERS)),
        f"/execute if block {pos(LAMP)} minecraft:redstone_lamp[lit=true]",
    ))
    strengths = tuple(int(re.search(r"(\d+)$", value)[1]) if re.search(r"(\d+)$", value) else 0 for value in pulse[:4])
    on = tuple("true" if "Test passed" in value else "false" for value in pulse[4:])
    return tuple(value for pair in zip(strengths, on[:4], strict=True) for value in pair) + (on[4],)


def run(args):
    with (ROOT / "fixtures/redstone_link-java.csv").open() as data:
        expected = tuple(csv.DictReader(data))
    with fixture_world(args, "Redstone-link", STRUCTURE, render=args.visual, pack=args.pack) as control:
        setup(control)
        control.step_to(control.clock() + 1)
        start = control.clock()
        first = int(expected[0]["tick"])
        differences = []
        actions = {
            12: f"/setblock {pos(SOURCE_A)} minecraft:redstone_block",
            18: f"/setblock {pos(SOURCE_B)} minecraft:composter[level=4]",
            30: f"/setblock {pos(SOURCE_A)} minecraft:air",
            40: f"/data merge block {pos(RECEIVERS[0])} {channel(False)}",
            50: f"/data merge block {pos(RECEIVERS[0])} {channel(True)}",
            62: f"/setblock {pos(SOURCE_B)} minecraft:composter[level=0]",
        }
        with (ROOT / ".local/redstone_link-horizon.csv").open("w") as out:
            writer = csv.writer(out)
            writer.writerow(("tick", *KEYS))
            for row in expected:
                tick = int(row["tick"])
                if tick != first:
                    control.step_to(start + tick - first)
                found = sample(control)
                writer.writerow((tick, *found))
                wanted = tuple(row[key] if key.endswith("powered") or key == "lamp" else int(row[key]) for key in KEYS)
                if found != wanted:
                    detail = f"Tick {tick}: Horizon {found}, Java {wanted}"
                    if not args.diagnostics:
                        raise RuntimeError(detail)
                    differences.append(detail)
                if tick in actions:
                    control.command(actions[tick])
                if args.visual and tick == 35:
                    control.command("/time set noon")
                    control.command("/tp @s 19.5 183 5.0")
                    control.call("wait", 3)
                    control.call("look-at", 20, 180, 8.5)
                    control.call("key", "f1", "tap")
                    control.call("wait", 4)
                    control.call("screenshot", ROOT / ".local/redstone-link.png")
            if differences:
                raise RuntimeError("\n".join(differences[:10]))
    print(f"Wireless analog signals, both frequency pairs, and the lamp matched all {len(expected)} Java ticks.")


def configure(args):
    with fixture_world(args, "Redstone-link-settings", STRUCTURE, render=True, pack=args.pack) as control:
        control.commands((
            "/fill 5 179 5 13 179 11 minecraft:smooth_stone",
            "/tp @s 8.5 180 6.0 0 25",
            "/gamemode survival",
            f"/item replace entity @s hotbar.0 with {LINK}",
            "/item replace entity @s hotbar.1 with minecraft:quartz 3",
            "/item replace entity @s hotbar.2 with minecraft:iron_ingot 3",
        ))
        control.call("wait", 3)
        control.call("key", "1", "tap")
        control.call("interact", 8, 179, 8, "up")
        control.call("wait", 3)
        if "facing=up" not in control.call("block", 8, 180, 8)["state"]:
            raise RuntimeError("The link did not attach upright")
        control.call("key", "shift", "down")
        control.call("wait", 2)
        control.call("look-at", 8.5, 180.23, 8.5)
        control.call("mouse", "right", "click")
        control.call("key", "shift", "up")
        control.call("wait", 3)
        if "receiver=true" not in control.call("block", 8, 180, 8)["state"]:
            raise RuntimeError("Sneak-clicking did not set receiver mode")
        for hotbar, z in (("2", 8.65625), ("3", 8.34375)):
            control.call("key", hotbar, "tap")
            control.call("look-at", 8.5, 180.25, z)
            control.call("wait", 4)
            control.call("mouse", "right", "click")
            control.call("wait", 3)
        nbt = control.command("/data get block 8 180 8")
        if not re.search(r'FrequencyFirst:.*?minecraft:quartz', nbt) or not re.search(r'FrequencyLast:.*?minecraft:iron_ingot', nbt):
            raise RuntimeError(f"Both frequency samples were not saved: {nbt}")
        counts = control.call("inventory")["counts"]
        if counts.get("minecraft:quartz") != 3 or counts.get("minecraft:iron_ingot") != 3:
            raise RuntimeError(f"The frequency samples consumed items: {counts}")
    print("Survival placement, receiver mode, and both frequency slots worked without consuming their samples.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--configure", action="store_true")
    args = parser.parse_args()
    (configure if args.configure else run)(args)
