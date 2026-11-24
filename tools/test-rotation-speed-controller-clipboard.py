#!/usr/bin/env python3
"""Compare rotation speed controller Clipboard settings with Create's ValueSettings payload."""

import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

clipboard = import_module("test-clipboard-placement")
multiplayer = import_module("test-multiplayer")
ITEM = "create:clipboard"
SOURCE = (8, 101, -7)
TARGET = (12, 101, -7)


def coords(position):
    return " ".join(map(str, position))


def aim(host, actor, player, position):
    x, y, z = position
    feet = (x + .5, float(y), z - 1.5)
    host.command(f"/tp {player} {coords(feet)}")
    multiplayer.until("the player to reach the controller", lambda:
                      actor.call("state")["player"]["position"] == list(feet))
    actor.call("look-at", x + .5, y + .5, z + .5)
    multiplayer.until("the ray to hit the controller", lambda:
                      (actor.call("looking-at").get("block") or {}).get("pos") == list(position))
    actor.call("wait", 6)


def clipboard_content(host, player):
    raw = host.command(f"/data get entity {player} SelectedItem").split("entity data: ", 1)[1]
    item = clipboard.menu.clipboard_snbt(raw)
    return item.get("components", {}).get("create:clipboard_content", {})


def target_value(host):
    raw = host.command(f"/data get block {coords(TARGET)} ScrollValue")
    return int(raw.rsplit("block data: ", 1)[1])


def run(args):
    mode = "Lan" if args.lan else "Solo"
    env = {"HORIZON_NO_AUDIO": "1"}
    with ExitStack() as resources:
        host = resources.enter_context(fixture_world(
            args, "RotationSpeedControllerClipboard" + mode, render=not args.lan, env=env,
        ))
        host.commands((
            "/fill 6 100 -10 14 100 -5 minecraft:smooth_stone",
            f"/setblock {coords(SOURCE)} create:rotation_speed_controller[axis=x]",
            f"/setblock {coords(TARGET)} create:rotation_speed_controller[axis=x]",
            f"/data merge block {coords(SOURCE)} {{ScrollValue:-64}}",
            f"/data merge block {coords(TARGET)} {{ScrollValue:16}}",
        ))
        actor, player = host, "@s"
        if args.lan:
            scratch = Path(resources.enter_context(TemporaryDirectory(prefix="cc-")))
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            player = "CCGuest"
            actor = resources.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario="rotation-speed-controller-clipboard", env=env,
            ))
            multiplayer.until("the controller Clipboard guest to join", lambda: any(
                guest["name"] == player and guest["placed"]
                for guest in host.call("lan", "status")["guests"]
            ))
        host.commands((
            f"/gamemode survival {player}" if args.lan else "/gamemode survival",
            f"/item replace entity {player} hotbar.0 with create:clipboard",
            f"/tp {player} {SOURCE[0] + .5} {SOURCE[1]} {SOURCE[2] - 1.5}",
        ))
        actor.call("select", ITEM)
        tick = host.clock()

        aim(host, actor, player, SOURCE)
        actor.call("mouse", "right", "click")
        multiplayer.until("the signed controller settings on the Clipboard", lambda:
                          clipboard_content(host, player).get("copied_values", {}).get("Speed")
                          == {"Row": 0, "Value": 64})
        assert target_value(host) == 16
        assert host.clock() == tick

        aim(host, actor, player, TARGET)
        actor.call("mouse", "left", "click")
        multiplayer.until("the target controller to receive the signed RPM setting", lambda:
                          target_value(host) == -64)
        assert clipboard_content(host, player)["copied_values"]["Speed"] == {"Row": 0, "Value": 64}
        assert host.clock() == tick

        host.command(f"/data merge block {coords(SOURCE)} {{ScrollValue:96}}")
        aim(host, actor, player, SOURCE)
        actor.call("mouse", "right", "click")
        multiplayer.until("the positive controller setting on the Clipboard", lambda:
                          clipboard_content(host, player).get("copied_values", {}).get("Speed")
                          == {"Row": 1, "Value": 96})
        aim(host, actor, player, TARGET)
        actor.call("mouse", "left", "click")
        multiplayer.until("the target controller to receive the positive RPM setting", lambda:
                          target_value(host) == 96)
        assert host.clock() == tick
    print(f"{mode}: controller Clipboard copied and pasted negative and positive RPM with Java's Speed row/value payload.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--lan", action="store_true")
    run(parser.parse_args())
