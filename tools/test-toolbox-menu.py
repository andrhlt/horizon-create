#!/usr/bin/env python3
"""Compare Toolbox menu cursor, filters and stored slots with pinned Java."""

import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

storage = import_module("test-toolbox-storage")
reference = storage.toolbox.reference
mp = storage.postbox.mp
POS = storage.POS
DISPLAY = 300
FIRST = DISPLAY
SECOND = DISPLAY + 4


def describe(stack):
    if not stack:
        return "_"
    item = stack.get("item") or stack["id"]
    return f'{item}={stack["count"]}'


def filters(host):
    raw = storage.block_value(host, POS, "Compartments")
    stacks = storage.toolbox.snbt(raw) if raw else []
    return [describe(stack) for stack in stacks[:2]] + ["_"] * max(0, 2 - len(stacks))


def layout(actor):
    rows = reference("menu-layout")
    visible = {DISPLAY + int(row["slot"]) for row in rows if row["visible"] == "true"}

    def current():
        slots = actor.call("screen").get("slots") or []
        return {slot["slot"] for slot in slots if DISPLAY <= slot["slot"] < DISPLAY + 32}

    mp.until("the eight Toolbox compartments to be shown", lambda: current() == visible)
    assert current() == visible


def open_toolbox(host, actor, player):
    host.commands((
        "/fill 8 99 -12 16 99 -4 minecraft:stone",
        f"/setblock {storage.xyz(POS)} {storage.BROWN}",
        f"/gamemode survival {player}",
        f"/tp {player} 12.5 100 -6.5",
    ))
    mp.until("the player to arrive at the Toolbox", lambda:
        actor.call("state")["player"]["position"] == [12.5, 100.0, -6.5])
    actor.call("interact", *POS, "south")
    layout(actor)


def replay(host, actor, player, confirm):
    open_toolbox(host, actor, player)
    tick = host.clock()
    rows = {row["action"]: row for row in reference("menu-clicks")}

    def observe(action):
        row = rows[action]
        expected = (row["cursor"], [row["filter0"], row["filter1"]], row["first_eight_slots"])

        def state():
            slots = storage.items(host)
            return (
                describe(actor.call("menu")["carried"]),
                filters(host),
                "|".join(slots.get(index, "_") for index in range(8)),
            )

        try:
            mp.until(action, lambda: state() == expected, seconds=3)
        except RuntimeError as error:
            raise AssertionError((row, state())) from error
        assert host.clock() - tick == int(row["tick"]), row
        print(f"{action} matched Java", flush=True)

    def hold(item, count):
        host.command(f"/item replace entity {player} hotbar.0 with minecraft:{item} {count}")
        mp.until(f"the player to receive {item}", lambda:
            any(stack.get("slot") == 0 and stack.get("item") == f"minecraft:{item}" and stack.get("count") == count
                for stack in actor.call("inventory")["hotbar"]))
        actor.call("click-slot", 0)

    def click(slot, button=None):
        actor.call("click-slot", slot, *((button,) if button else ()))

    observe("initial")
    hold("cobblestone", 64)
    click(FIRST)
    observe("insert_first")
    hold("cobblestone", 51)
    click(FIRST)
    observe("append")
    hold("stone", 15)
    click(FIRST)
    observe("wrong_item")
    click(1)
    click(FIRST, "right")
    observe("half_pickup")
    click(2)
    click(FIRST)
    observe("pickup")
    click(3)
    click(FIRST)
    observe("deplete")
    click(4)
    click(FIRST)
    observe("clear_filter")
    hold("dirt", 7)
    click(FIRST, "right")
    observe("insert_one")
    click(5)
    host.command(f"/item replace entity {player} hotbar.0 with minecraft:stone 19")
    mp.until("the player to receive the shift-click stack", lambda:
        actor.call("inventory")["hotbar"][0].get("item") == "minecraft:stone")
    click(0, "shift")
    observe("quick_move_in")
    click(SECOND, "shift")
    observe("quick_move_out")
    if confirm:
        stack = actor.call("inventory")["hotbar"][1]
        assert stack.get("item") == "minecraft:stone", stack
        actor.call("click-slot", 1)
        mp.until("the existing Stone stack to be picked up", lambda:
            describe(actor.call("menu")["carried"]) == describe(stack))
        before = actor.call("inventory")["counts"]
        actor.call("click-button", "Confirm")
        mp.until("Confirm to close the Toolbox and return the cursor", lambda:
            actor.call("screen")["screen"] == "playing" and actor.call("inventory")["carried"] is None)
        assert actor.call("inventory")["counts"] == before
        assert host.clock() == tick
        print("Confirm closed the original window and returned the held stack on the same tick.")
    else:
        actor.call("close")


def deposit(host, actor, player, screenshot):
    open_toolbox(host, actor, player)
    storage.replace(host, 0, "minecraft:cobblestone", 64)
    storage.replace(host, 4, "minecraft:dirt")
    storage.step(host, 1)
    inventory = (
        ("minecraft:cobblestone", 64),
        ("minecraft:cobblestone", 64),
        ("minecraft:cobblestone", 64),
        ("minecraft:cobblestone", 16),
        ("minecraft:dirt", 8),
        ("minecraft:stone", 17),
        ("create:brown_toolbox", 1),
    )
    host.commands(f"/item replace entity {player} hotbar.{slot} with {kind} {count}"
                  for slot, (kind, count) in enumerate(inventory))
    expected = "|".join(f"{kind}={count}" for kind, count in inventory)

    def hotbar():
        return "|".join(describe(stack) if stack.get("item") else "_"
                        for stack in actor.call("inventory")["hotbar"][:7])

    mp.until("the stocked hotbar to reach the player", lambda: hotbar() == expected)
    button = "Return items to Toolbox"
    mp.until("the Deposit All control to render", lambda:
        any(entry["label"] == button for entry in actor.call("screen")["buttons"]))
    tick = host.clock()
    actor.call("click-button", button)
    row, = reference("menu-deposit")

    def end_state():
        slots = storage.items(host)
        return (hotbar(), "|".join(slots.get(index, "_") for index in range(8)))

    expected = (row["player_hotbar"], row["first_eight_slots"])
    try:
        mp.until("the Java Deposit All result", lambda: end_state() == expected, seconds=5)
    except RuntimeError as error:
        raise AssertionError((row, end_state())) from error
    assert host.clock() - tick == int(row["tick"])
    if screenshot:
        actor.call("screenshot", screenshot)
    print("Deposit All filled the locked matching compartments, kept overflow and rejected unfiltered items.")
    actor.call("close")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--deposit", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    env = {"HORIZON_NO_AUDIO": "1"}
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, f"Toolbox-menu-{args.lan}", render=not args.lan, pack=args.pack, env=env))
        actor, player = host, "@s"
        if args.lan:
            player = "ToolboxMenuGuest"
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-toolbox-menu-")))
            actor = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario="toolbox-menu", pack=args.pack, env=env,
            ))
            mp.until("the Toolbox guest to join", lambda: any(
                entry["name"] == player and entry["placed"] for entry in host.call("lan", "status")["guests"]
            ))
        if args.deposit:
            deposit(host, actor, player, args.screenshot)
        else:
            replay(host, actor, player, args.confirm)


if __name__ == "__main__":
    main()
