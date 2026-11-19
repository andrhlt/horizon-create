#!/usr/bin/env python3
"""Replay Java Toolbox equip, resupply and unlink from the real radial menu."""

import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

menu = import_module("test-toolbox-menu")
storage = menu.storage
mp = menu.mp
ALT = "key.keyboard.left.alt"
POS = storage.POS
NEAR = (12.5, 100.0, -6.5)
FAR = (12.5, 100.0, 6.5)


def replay(host, actor, player, reconnect=None, screenshots=None):
    host.commands((
        "/fill 8 99 -12 16 99 8 minecraft:stone",
        f"/setblock {storage.xyz(POS)} {storage.BROWN}",
        f"/gamemode survival {player}",
    ))
    storage.replace(host, 0, "minecraft:cobblestone", 64)
    storage.replace(host, 1, "minecraft:cobblestone", 32)
    storage.step(host, 1)
    tick = host.clock()
    rows = {row["action"]: row for row in menu.reference("link")}

    def move(feet):
        host.command(f"/tp {player} {storage.xyz(feet)}")
        mp.until("the player to be teleported", lambda:
            actor.call("state")["player"]["position"] == list(feet))

    def hold(count):
        host.command(f"/item replace entity {player} hotbar.0 with minecraft:cobblestone {count}")
        mp.until(f"the server to send {count} items to the player's slot", lambda:
            actor.call("inventory")["hotbar"][0].get("count") == count)

    def observe(action):
        row = rows[action]
        target = tick + int(row["tick"])
        if host.clock() < target:
            host.step_to(target)

        def state():
            held = actor.call("inventory")["hotbar"][0]
            contents = storage.items(host)
            return (
                menu.describe(held) if held.get("item") else "_",
                "|".join(contents.get(slot, "_") for slot in range(4)),
            )

        expected = (row["held"], row["slots"])
        try:
            mp.until(action, lambda: state() == expected, seconds=5)
        except RuntimeError as error:
            raise AssertionError((row, state())) from error
        assert host.clock() == target
        print(f"{action} matched Java at tick {row['tick']}", flush=True)
        if screenshots and action in {"initial_restock", "out_of_range", "unequip"}:
            actor.call("wait", 3)
            actor.call("screenshot", screenshots / f"{action}.png")

    def open_radial():
        actor.call("key", ALT, "down")
        mp.until("the Toolbox radial menu", lambda: actor.call("screen")["screen"] == "mod")

    def radial_closed():
        mp.until("the Toolbox radial to close", lambda: actor.call("screen")["screen"] == "playing")
        actor.call("key", ALT, "up")
        actor.call("wait", 3)

    move(NEAR)
    actor.call("key", "1", "tap")
    open_radial()
    actor.call("key", "1", "tap")
    radial_closed()
    observe("equip")
    observe("initial_restock")
    if reconnect:
        actor = reconnect()
        mp.until("the guest to retain survival mode", lambda: any(
            entry["name"] == player and entry["game_mode"] == 0
            for entry in host.call("lan", "status")["guests"]
        ))
        observe("initial_restock")
        print("The guest rejoined with their original Toolbox connection.", flush=True)
    hold(27)
    observe("consumed")
    hold(47)
    observe("surplus")
    move(FAR)
    hold(20)
    observe("out_of_range")
    move(NEAR)
    observe("back_in_range")
    open_radial()
    button = "Unequip: Cobblestone"
    mp.until("the Toolbox centre Unequip control", lambda:
        any(entry["label"] == button for entry in actor.call("screen")["buttons"]))
    actor.call("click-button", button)
    radial_closed()
    observe("unequip")
    # Picking up a linked Toolbox first returns the linked stack into its
    # inventory, then packs that updated inventory into the item.
    open_radial()
    actor.call("key", "1", "tap")
    radial_closed()
    storage.step(host, 1)
    mp.until("the linked stack to replenish", lambda:
        actor.call("inventory")["hotbar"][0].get("count") == 32)
    actor.call("look-at", POS[0] + .5, POS[1] + .3, POS[2] + .5)
    actor.call("mouse", "left", "click")
    mp.until("the linked Toolbox to be picked up", lambda:
        actor.call("inventory")["counts"].get(storage.BROWN) == 1)
    assert actor.call("inventory")["counts"].get("minecraft:cobblestone", 0) == 0
    packed = next(item for item in actor.call("inventory")["hotbar"] if item.get("item") == storage.BROWN)
    contents = storage.toolbox.stack_components(packed)["create:toolbox_inventory"]["items"]["items"]
    assert sum(stack["count"] for stack in contents.values()) == 94, contents
    print("Pickup returned the linked stack before packing the Toolbox.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--reconnect", action="store_true")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if args.reconnect and not args.lan:
        parser.error("--reconnect requires --lan")
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    env = {"HORIZON_NO_AUDIO": "1"}
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, f"Toolbox-link-{args.lan}", render=not args.lan, pack=args.pack, env=env))
        actor, player = host, "@s"
        connect = None
        if args.lan:
            player = "ToolboxLinkGuest"
            port = host.call("lan", "open", 0, "commands")["port"]
            session = stack.enter_context(ExitStack())

            def connect():
                session.close()
                mp.until("the previous Toolbox guest session to close", lambda: not any(
                    entry["name"] == player for entry in host.call("lan", "status")["guests"]
                ))
                scratch = Path(session.enter_context(TemporaryDirectory(prefix="hc-toolbox-link-")))
                actor = session.enter_context(mp.joined_client(
                    args, scratch, f"127.0.0.1:{port}", player, render=True,
                    scenario="toolbox-link", pack=args.pack, env=env,
                ))
                mp.until("the Toolbox guest to join", lambda: any(
                    entry["name"] == player and entry["placed"] for entry in host.call("lan", "status")["guests"]
                ))
                return actor

            actor = connect()
        replay(host, actor, player, connect if args.reconnect else None, args.screenshots)


if __name__ == "__main__":
    main()
