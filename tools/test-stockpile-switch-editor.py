#!/usr/bin/env python3
"""Compare real Stockpile Switch settings and redstone timing with Java Create."""

import argparse
from contextlib import contextmanager
import csv
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world


SWITCH = (8, 101, -8)
BARREL = (8, 101, -7)
GUEST = "StockpileGuest"
ATLAS = "assets/create/textures/gui/threshold_switch.png"
ATLAS_HASH = "6a1c9208c3c95cfa56284f22b478e051ec14e7d44a74aec8a3064882ab11084c"


def xyz(pos):
    return " ".join(map(str, pos))


def load_multiplayer():
    spec = spec_from_file_location("multiplayer", ROOT / "tools/test-multiplayer.py")
    multiplayer = module_from_spec(spec)
    spec.loader.exec_module(multiplayer)
    return multiplayer


def wait_for(control, reason, predicate):
    for _ in range(45):
        if predicate():
            return
        control.call("wait", 2)
    raise RuntimeError(f"Timed out waiting for {reason}.")


def widget(control, label):
    buttons = control.call("screen")["buttons"]
    for button in buttons:
        if button["label"] == label:
            return button["x"] + button["w"] / 2, button["y"] + button["h"] / 2
    raise RuntimeError(f"Expected {label!r} among the Stockpile Switch controls: {buttons}.")


def scroll(control, label, direction, times=1):
    x, y = widget(control, label)
    control.call("script", script=f"scroll-at {x} {y} {direction}\n" * times)
    control.call("wait", 3)


def open_editor(control):
    control.call("look-at", 8.73, 101.76, -7.9)
    control.call("wait", 3)
    hit = control.call("looking-at").get("block")
    assert hit and hit["pos"] == list(SWITCH), hit
    control.call("mouse", "right", "click")
    wait_for(control, "the Stockpile Switch editor", lambda: control.call("state")["screen"] == "mod")
    wait_for(control, "the five editor fields", lambda: len(control.call("screen")["buttons"]) == 5)


def confirm(control):
    control.call("click-at", *widget(control, "Confirm"))
    wait_for(control, "the editor to close", lambda: control.call("state")["screen"] == "playing")


def field(reply, key, default=None):
    match = re.search(rf'\b{key}: (-?\d+(?:\.\d+)?)[bfs]?', reply)
    return int(float(match[1])) if match else default


def configuration(control, lower, upper, inverted, stacks):
    reply = control.command(f"/data get block {xyz(SWITCH)}")
    return tuple(field(reply, name) for name in ("OffBelowAmount", "OnAboveAmount", "Inverted", "InStacks")) == (
        lower, upper, inverted, stacks,
    )


def setup(host):
    host.commands((
        "/fill 7 100 -12 11 100 -8 minecraft:smooth_stone",
        f"/setblock {xyz(BARREL)} minecraft:barrel",
        f"/item replace block {xyz(BARREL)} container.0 with minecraft:stone 64",
        f"/setblock {xyz(SWITCH)} create:stockpile_switch[target=wall,facing=south]",
        "/tp @s 8.5 101 -11.5",
        "/gamemode survival @s",
    ))


@contextmanager
def actor_for(host, args, scratch):
    if scratch is None:
        yield host
        return
    multiplayer = load_multiplayer()
    host.command("/tp @s 10.5 101 -8.5")
    address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
    with multiplayer.joined_client(
        args, scratch, address, GUEST, render=True, scenario="stockpile-switch", pack=args.pack,
    ) as guest:
        multiplayer.until("the Stockpile Switch guest to join", lambda: any(
            player["name"] == GUEST and player["placed"] for player in host.call("lan", "status")["guests"]
        ))
        host.commands((f"/gamemode survival {GUEST}", f"/tp {GUEST} 8.5 101 -11.5"))
        multiplayer.until("the guest to reach the sensor", lambda:
            guest.call("state")["player"]["position"][:3] == [8.5, 101.0, -11.5]
        )
        yield guest


def verify(args, scratch):
    data = args.pack or ROOT / ".local/create.hmod"
    with ZipFile(data) as pack:
        assert sha256(pack.read(ATLAS)).hexdigest() == ATLAS_HASH
    with (ROOT / "fixtures/stockpile-switch-editor-java.csv").open(newline="") as source:
        rows = list(csv.reader(source))
    assert len(rows) == 43
    with fixture_world(args, "StockpileSwitchEditor", render=True, pack=args.pack) as host:
        setup(host)
        with actor_for(host, args, scratch) as actor:
            start = host.clock()
            for tick, row in enumerate(rows[1:], 1):
                host.step_to(start + tick)
                if tick == 4:
                    open_editor(actor)
                    scroll(actor, "Items", -1)
                    widget(actor, "≥ 2")
                    widget(actor, "≤ 1")
                    actor.call("click-at", *widget(actor, "Invert Signal"))
                    wait_for(host, "inversion to apply on the action tick", lambda:
                        configuration(host, 64, 128, True, True)
                    )
                    assert host.clock() == start + tick
                if tick == 8:
                    scroll(actor, "Stacks", 1)
                    scroll(actor, "≥ 128", -1, 32)
                    scroll(actor, "≤ 64", -1, 32)
                    widget(actor, "≥ 96")
                    widget(actor, "≤ 32")
                    confirm(actor)
                    wait_for(host, "the amended thresholds to save", lambda:
                        configuration(host, 32, 96, True, False)
                    )
                    assert host.clock() == start + tick
                if tick == 13:
                    host.command(f"/item replace block {xyz(BARREL)} container.1 with minecraft:stone 64")
                if tick == 25:
                    open_editor(actor)
                    widget(actor, "≥ 96")
                    widget(actor, "≤ 32")
                    actor.call("click-at", *widget(actor, "Invert Signal"))
                    wait_for(host, "uninversion to apply on the action tick", lambda:
                        configuration(host, 32, 96, False, False)
                    )
                    confirm(actor)
                    assert host.clock() == start + tick
                if tick == 27:
                    host.command(f'/data merge block {xyz(BARREL)} {{Items:[{{Slot:0b,id:"minecraft:stone",count:32}}]}}')
                tick_id, current, capacity, lower, upper, stacks, inverted, raw, powered, level = row
                assert int(tick_id) == tick
                reply = host.command(f"/data get block {xyz(SWITCH)}")
                for key, expected, default in (
                    ("CurrentAmount", int(current), None),
                    ("CurrentMaxAmount", int(capacity), None),
                    ("OffBelowAmount", int(lower), 64),
                    ("OnAboveAmount", int(upper), 128),
                    ("InStacks", int(stacks == "true"), 0),
                    ("Inverted", int(inverted == "true"), 0),
                    ("Powered", int(raw == "true"), 0),
                    ("PoweredAfterDelay", int(powered == "true"), 0),
                ):
                    actual = field(reply, key, default)
                    assert actual == expected, (tick, key, actual, expected, reply)
                query = f"/execute if block {xyz(SWITCH)} create:stockpile_switch[level={level},powered={powered}]"
                assert host.command(query).startswith("Test passed"), (tick, query, reply)
    who = "A live guest" if scratch is not None else "The host"
    print(f"{who} matched all 42 initialized Java Stockpile Switch ticks using the original editor controls.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-stockpile-") as scratch:
            verify(args, Path(scratch))
    else:
        verify(args, None)


if __name__ == "__main__":
    main()
