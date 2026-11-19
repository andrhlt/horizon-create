#!/usr/bin/env python3
"""Replay Java Clipboard placement and attack pickup through Horizon player input."""

import argparse
from contextlib import ExitStack
from importlib import import_module
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
menu = import_module("test-frogport-menu")
CLIPBOARD = "create:clipboard"
FACE_OFFSETS = {
    "up": (0, 1, 0), "down": (0, -1, 0),
    "north": (0, 0, -1), "south": (0, 0, 1),
    "west": (-1, 0, 0), "east": (1, 0, 0),
}


def coords(values):
    return " ".join(map(str, values))


def held_clipboard(host, player):
    response = host.command(f"/data get entity {player} SelectedItem")
    _, delimiter, data = response.partition("entity data: ")
    return menu.clipboard_snbt(data) if delimiter else {}


def clipboard_state(client, position):
    block = client.call("block", *position)
    if block.get("block") != CLIPBOARD:
        return None
    return dict(re.findall(r"(\w+)=(\w+)", block["state"]))


def ray_hit(client, position, face):
    hit = client.call("looking-at").get("block") or {}
    return hit if hit.get("pos") == list(position) and hit.get("face") == face else None


def verify_clipboard(host, actor, player, index, row, *, sneak_pickup=False):
    side = row["side"]
    offset = FACE_OFFSETS[side]
    support = (7 + 5 * index, {"down": 175, "up": 170}.get(side, 172), 20)
    target = tuple(cell + step for cell, step in zip(support, offset, strict=True))
    feet = (support[0] + .5 + 2 * offset[0], 171, 20.5 + 2 * offset[2])
    if side in ("down", "up"):
        feet = (feet[0], feet[1], feet[2] - 2)
    supply = (int(feet[0]) - 1, 171, int(feet[2]))
    original = menu.clipboard_snbt(row["before"])
    host.commands((
        f"/clear {player}",
        f"/setblock {coords(support)} minecraft:stone",
        f"/tp {player} {coords(feet)}",
    ))
    multiplayer.until(f"the player to reach the {side} support", lambda:
                      actor.call("state")["player"]["position"] == list(feet))
    if original.get("components"):
        host.commands((
            f"/setblock {coords(supply)} minecraft:barrel",
            f"/data merge block {coords(supply)} {{Items:[{{Slot:0b," + row["before"][1:] + "]}",
        ))
        actor.call("interact", *supply, "east")
        multiplayer.until("the written Clipboard in the barrel", lambda:
                          menu.stack_item(actor, 300) == CLIPBOARD)
        actor.call("click-slot", 300)
        actor.call("click-slot", 0)
        actor.call("close")
    else:
        host.command(f"/item replace entity {player} hotbar.0 with {CLIPBOARD}")
    multiplayer.until("the Clipboard in the hotbar", lambda:
                      actor.call("inventory")["counts"].get(CLIPBOARD) == 1)
    actor.call("select", CLIPBOARD)
    multiplayer.until("the selected Clipboard to match the Java item", lambda:
                      held_clipboard(host, player) == original)

    aim = tuple(cell + .5 + .5 * step for cell, step in zip(support, offset, strict=True))
    actor.call("look-at", *aim)
    actor.call("key", "shift", "down")
    try:
        multiplayer.until(f"the aim to reach the {side} support", lambda: ray_hit(actor, support, side))
        actor.call("wait", 2)
        tick = host.clock()
        actor.call("mouse", "right", "click")
        try:
            multiplayer.until(f"the {side} Clipboard to be placed", lambda:
                              clipboard_state(host, target) == row["state"], seconds=5)
        except RuntimeError as error:
            raise AssertionError((side, host.call("block", *target), held_clipboard(host, player),
                                  actor.call("looking-at"))) from error
    finally:
        actor.call("key", "shift", "up")
    assert host.clock() == tick
    assert (held_clipboard(host, player) == {}) == row["spent"]
    if original.get("components"):
        saved = host.command(f"/data get block {coords(target)} ClipboardItem")
        data = menu.clipboard_snbt(saved.split("block data: ", 1)[1])
        data.pop("Slot", None)
        assert data == menu.clipboard_snbt(row["block_item"]), (side, data)

    multiplayer.until(f"the {side} Clipboard and inventory to synchronize", lambda: (
        clipboard_state(actor, target) == row["state"]
        and not multiplayer.count(actor, CLIPBOARD)
    ))
    outline = row["shape"]
    actor.call("look-at", *(v + (outline[i] + outline[i + 3]) / 2 for i, v in enumerate(target)))
    axis = next(i for i, step in enumerate(offset) if step)
    plane = target[axis] + outline[axis + 3 * int(offset[axis] > 0)]

    def sees_java_outline():
        hit = ray_hit(actor, target, side)
        return hit and abs(hit["point"][axis] - plane) < 1e-5

    multiplayer.until(f"the ray to hit the Java {side} outline", sees_java_outline)
    actor.call("wait", 5)
    recovered = menu.clipboard_snbt(row["recovered"])
    if sneak_pickup:
        actor.call("key", "shift", "down")
    try:
        if sneak_pickup:
            multiplayer.until("the crouching player to face the Clipboard", sees_java_outline)
        actor.call("mouse", "right" if sneak_pickup else "left", "click")
        multiplayer.until(f"the selected slot to receive the {side} Clipboard", lambda:
                          held_clipboard(host, player) == recovered)
    finally:
        if sneak_pickup:
            actor.call("key", "shift", "up")
    assert host.clock() == tick
    assert (host.call("block", *target)["block"] == "minecraft:air") == row["removed"]
    multiplayer.until(f"the {side} pickup to synchronize", lambda: (
        actor.call("block", *target)["block"] == "minecraft:air"
        and multiplayer.count(actor, CLIPBOARD) == 1
    ))
    hotbar = next(stack for stack in actor.call("inventory")["hotbar"] if stack["slot"] == 0)
    assert menu.clipboard_snbt(hotbar.get("components") or "{}") == recovered.get("components", {})
    action = "sneak use" if sneak_pickup else "attack"
    print(f"{side} {action}: Java state, outline, consumed item, immediate pickup and recovered components")


def verify_support(host, actor, player):
    rows = json.loads((ROOT / "fixtures/clipboard-support-java.json").read_text())
    collisions = json.loads((ROOT / "content/data/create/horizon/block/clipboard.json").read_text())
    targets = []
    tick = host.clock()
    for index, row in enumerate(rows):
        scenario = row["scenario"]
        support = (7 + index * 6, 170, 20)
        target = (support[0], 171, support[2])
        feet = (support[0] + .5, 171, 18.5)
        aim = (support[0] + .5, 171, 20.5)
        host.commands((
            f"/clear {player}",
            f"/tp {player} {coords(feet)}",
            f"/setblock {coords(support)} minecraft:stone",
            f"/setblock {coords(target)} " + ("minecraft:water" if scenario.startswith("wet") else "minecraft:air"),
            f"/item replace entity {player} hotbar.0 with {CLIPBOARD}",
        ))
        multiplayer.until("the player to arrive with a Clipboard", lambda: (
            actor.call("state")["player"]["position"] == list(feet)
            and multiplayer.count(actor, CLIPBOARD) == 1
        ))
        actor.call("select", CLIPBOARD)
        blank = {"id": CLIPBOARD, "count": 1}
        multiplayer.until("the host to see the selected Clipboard", lambda: held_clipboard(host, player) == blank)
        actor.call("look-at", *aim)
        actor.call("key", "shift", "down")
        try:
            multiplayer.until("the player to aim up at the support face", lambda: ray_hit(actor, support, "up"))
            actor.call("wait", 2)
            actor.call("mouse", "right", "click")
            try:
                multiplayer.until(f"{scenario} placement to match Java", lambda:
                                  clipboard_state(host, target) == row["placed"], seconds=6)
            except RuntimeError as error:
                raise AssertionError((scenario, host.call("block", *target),
                                      held_clipboard(host, player), actor.call("looking-at"))) from error
        finally:
            actor.call("key", "shift", "up")
        multiplayer.until("the placed Clipboard and spent item to reach the client", lambda: (
            clipboard_state(actor, target) == row["placed"] and not multiplayer.count(actor, CLIPBOARD)
        ))
        collision = collisions["collision_shapes"]["values"]["floor,north"][0]
        assert all(abs(a - b) < 1e-12 for a, b in zip(collision, row["collision"], strict=True))
        if scenario.endswith("_attack"):
            actor.call("wait", 5)
            actor.call("look-at", target[0] + .5, target[1] + .03125, target[2] + .5)
            multiplayer.until("the player to face the Clipboard", lambda: ray_hit(actor, target, "up"))
            actor.call("mouse", "left", "click")
        else:
            host.command(f"/setblock {coords(support)} minecraft:air")
        try:
            multiplayer.until(f"{scenario} to resolve in the same tick", lambda: (
                host.call("block", *target)["state"] == row["removed"]
                and held_clipboard(host, player) == (blank if row["held"] else {})
            ), seconds=6)
        except RuntimeError as error:
            raise AssertionError((scenario, host.call("block", *target),
                                  held_clipboard(host, player), actor.call("looking-at"))) from error
        assert host.clock() == tick
        targets.append((target, row))
    assert all(row["tick"] == rows[0]["tick"] for row in rows)
    host.command(f"/tick step {rows[0]['tick']}")
    multiplayer.until("the original five ticks to elapse", lambda: host.clock() == tick + rows[0]["tick"])
    for target, row in targets:
        assert host.call("block", *target)["state"] == row["after"], row["scenario"]
        multiplayer.until(f"{row['scenario']} to synchronize at tick five", lambda:
                          actor.call("block", *target)["state"] == row["after"])
        print(f"{row['scenario']}: Java placement, collision box, removal, receipt and tick-five block")


def run(args):
    mode = "Lan" if args.lan else "Solo"
    env = {"HORIZON_NO_AUDIO": "1"}
    with ExitStack() as resources:
        host = resources.enter_context(fixture_world(
            args, "Clipboard" + ("Support" if args.support else "Placement") + mode,
            pack=args.pack, render=not args.lan, env=env,
        ))
        host.command("/fill 3 170 15 38 170 25 minecraft:stone")
        actor, name = host, "@s"
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            name = "ClipboardGuest"
            scratch = Path(resources.enter_context(TemporaryDirectory(prefix="hc-clipboard-")))
            actor = resources.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, scenario="clipboard-placement",
                pack=args.pack, render=True, env=env,
            ))
            multiplayer.until("the Clipboard guest to join", lambda: any(
                guest["name"] == name and guest["placed"] for guest in host.call("lan", "status")["guests"]
            ))
        host.command(f"/gamemode survival {name}")
        if args.lan:
            host.command("/tp @s 4.5 171 18.5")
        if args.support:
            verify_support(host, actor, name)
            return
        rows = json.loads((ROOT / "fixtures/clipboard-placement-java.json").read_text())
        for index, row in enumerate(rows):
            verify_clipboard(host, actor, name, index, row)
        wall = next(row for row in rows if row["side"] == "south")
        verify_clipboard(host, actor, name, len(rows), wall, sneak_pickup=True)
    print(f"{mode}: all {len(rows)} Java Clipboard placement and attack cases matched, plus sneak pickup")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--support", action="store_true")
    run(parser.parse_args())
