#!/usr/bin/env python3
"""Configure a stock Display Board from LAN, remove its target, and reopen the world."""

import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
BOARD = (8, 100, -11)
OBSERVER = (5, 99, -11)
LINK = (5, 99, -10)
STOCK = (6, 99, -11)
SIGNAL = (6, 99, -10)
BOARD_STATE = "create:display_board[facing=north]"
LINK_ITEM = "create:display_link"
COUNT_BUTTON = "Amount of matching Items"
CONTROL_LABELS = {COUNT_BUTTON, "Previous Row", "Next Row"}
GUEST = "DisplayGuest"


def pos(coords):
    return " ".join(map(str, coords))


def set_stock(host, count):
    host.command(f"/item replace block {pos(STOCK)} container.0 with minecraft:iron_ingot {count}")


def step(host, ticks=1):
    start = host.clock()
    for tick in range(start + 1, start + ticks + 1):
        host.step_to(tick)


def board_row(host):
    return host.command(f"/data get block {pos(BOARD)} Display1").replace('\\\"', '"')


def check_row(host, count):
    result = board_row(host)
    assert f'"text":"{count}"' in result, result


def check_link(host):
    state, offset, row, source = host.commands((
        f"/execute if block {pos(LINK)} {LINK_ITEM}[facing=south]",
        f"/data get block {pos(LINK)} TargetOffset",
        f"/data get block {pos(LINK)} TargetLine",
        f"/data get block {pos(LINK)} Source.Id",
    ))
    assert "Test passed" in state, state
    assert offset.endswith("[I; 3, 1, -1]"), offset
    assert row.endswith(": 1"), row
    assert "create:content_observer_source_count_items" in source, source


def guest_move(host, guest, *coords):
    host.command(f"/tp {GUEST} {pos(coords)}")
    mp.until(f"guest to reach {coords}", lambda: guest.call("state")["player"]["position"] == list(coords))


def guest_aim(guest, block, point, face):
    guest.call("look-at", *point)

    def target():
        hit = guest.call("looking-at").get("block") or {}
        return hit.get("pos") == list(block) and hit["face"] == face

    mp.until(f"guest to target the {face} face of {block}", target)


def guest_menu(guest):
    guest_aim(guest, LINK, (5.5, 99.4, -9.5), "up")
    guest.call("mouse", "right", "click")

    def is_link_menu():
        screen = guest.call("screen")
        return screen["screen"] == "container" and any(
            span["text"] == "Display Link" for span in screen.get("title", ()))

    mp.until("guest's Display Link menu", is_link_menu)


def guest_actions(args, host):
    port = host.call("lan", "open", 0, "commands", "force")["port"]
    with TemporaryDirectory(prefix="hc-board-lan-") as scratch:
        with mp.joined_client(args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                              scenario="display-board-lifecycle", env={"HORIZON_NO_AUDIO": "1"}) as guest:
            mp.until("Display guest to join", lambda: any(
                player["name"] == GUEST and player["placed"] for player in host.call("lan", "status")["guests"]))
            host.commands((f"/gamemode survival {GUEST}", f"/clear {GUEST}",
                           f"/item replace entity {GUEST} hotbar.0 with {LINK_ITEM} 2"))
            guest_move(host, guest, 8.5, 99, -13.5)
            mp.until("guest's two Display Links", lambda: mp.count(guest, LINK_ITEM) == 2)
            guest.call("select", LINK_ITEM)
            guest_aim(guest, BOARD, (8.5, 100.5, -10.99), "north")
            guest.call("mouse", "right", "click")
            mp.until("guest's selected Board on the host", lambda: "create:click_to_link_data" in
                     host.command(f"/data get entity {GUEST} SelectedItem"))
            guest_move(host, guest, 5.5, 99, -8.5)
            guest_aim(guest, OBSERVER, (5.5, 99.5, -10.01), "south")
            guest.call("mouse", "right", "click")
            try:
                mp.until("guest to place and spend one Link", lambda:
                         guest.call("block", *LINK)["block"] == LINK_ITEM and mp.count(guest, LINK_ITEM) == 1)
            except RuntimeError as error:
                observer, link, held = host.commands((f"/data get block {pos(OBSERVER)}",
                                                       f"/data get block {pos(LINK)}",
                                                       f"/data get entity {GUEST} SelectedItem"))
                raise RuntimeError(f"{error}. Host saw Observer {observer}, Link {link}, item {held}") from error
            items = host.command(f"/data get entity {GUEST} Inventory")
            assert "create:click_to_link_data" not in items, items
            guest.call("key", "2", "tap")
            step(host)
            guest_menu(guest)
            mp.until("guest to see the count control", lambda: any(
                button["label"] == COUNT_BUTTON for button in guest.call("screen").get("buttons", ())))
            guest.call("click-button", "Next Row")
            mp.until("the host to save row 2", lambda:
                     host.command(f"/data get block {pos(LINK)} TargetLine").endswith(": 1"))
            guest.call("click-button", COUNT_BUTTON)
            mp.until("the host Board to show 7", lambda: '"text":"7"' in board_row(host))
            check_link(host)
            guest.call("key", "escape", "tap")
            guest_move(host, guest, 8.5, 99, -13.5)
            guest.call("look-at", 8.5, 100.5, -10.99)
            if args.visual:
                guest.call("key", "f1", "tap")
                guest.call("wait", 8)
                guest.call("screenshot", ROOT / ".local/display-board-guest-count.png")
                guest.call("key", "f1", "tap")
            print("Survival guest selected the Board, spent one Link, and published stock 7 to row 2.", flush=True)

            host.command(f"/setblock {pos(BOARD)} minecraft:air")
            step(host)
            mp.until("guest to see the missing Board", lambda: guest.call("block", *BOARD)["block"] == "minecraft:air")
            guest_move(host, guest, 5.5, 99, -8.5)
            guest_menu(guest)
            guest.call("wait", 8)
            labels = {button["label"] for button in guest.call("screen").get("buttons", ())}
            assert not labels & CONTROL_LABELS, labels
            if args.visual:
                guest.call("screenshot", ROOT / ".local/display-board-guest-missing-target.png")
            guest.call("key", "escape", "tap")
            check_link(host)
            host.command(f"/setblock {pos(BOARD)} {BOARD_STATE}")
            step(host, 2)
            guest_menu(guest)
            mp.until("guest to see controls for the restored Board", lambda: any(
                button["label"] == "Previous Row" for button in guest.call("screen").get("buttons", ())))
            guest.call("click-button", COUNT_BUTTON)
            mp.until("the restored Board to show 7", lambda: '"text":"7"' in board_row(host))
            print("Removing the Board hid source and row controls. Restoring it made the saved link usable again.",
                  flush=True)


def run(args):
    with fixture_world(args, "DisplayBoardLifecycle", render=True, env={"HORIZON_NO_AUDIO": "1"}) as host:
        host.commands((
            "/fill 3 98 -15 11 98 -7 minecraft:smooth_stone",
            "/tp @s 11.5 99 -8.5",
            f"/setblock {pos(BOARD)} {BOARD_STATE}",
            "/setblock 9 100 -11 create:cogwheel[axis=z]",
            "/setblock 9 100 -10 create:creative_motor[facing=north]{ScrollValue:64}",
            f"/setblock {pos(STOCK)} minecraft:chest",
            f"/setblock {pos(OBSERVER)} create:content_observer[target=wall,facing=east]",
        ))
        set_stock(host, 7)
        step(host, 2)
        guest_actions(args, host)

        host.command(f"/setblock {pos(SIGNAL)} minecraft:redstone_block")
        set_stock(host, 11)
        step(host)
        host.command("/save-all flush")
        host.restart()
        check_link(host)
        check_row(host, 7)
        assert "powered=true" in host.call("block", *LINK)["state"]
        host.command(f"/setblock {pos(SIGNAL)} minecraft:air")
        step(host)
        check_row(host, 11)
        print("Idle reopen retained the gated link and previous display of 7, then unpowering it published 11.",
              flush=True)

        host.command("/save-all flush")
        host.restart()
        check_link(host)
        check_row(host, 11)
        assert "powered=false" in host.call("block", *LINK)["state"]
        set_stock(host, 4)
        step(host, 100)
        check_row(host, 4)
    print("Active reopen retained the ungated link and display of 11, then passively published 4.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    run(parser.parse_args())
