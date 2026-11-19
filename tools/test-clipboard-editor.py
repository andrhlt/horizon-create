#!/usr/bin/env python3
"""Use the actual Horizon Clipboard screen and replay Java item snapshots."""

import argparse
from contextlib import ExitStack
from importlib import import_module
import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
clipboard = import_module("test-clipboard-placement")
ITEM = "create:clipboard"


def anchor(actor, screenshot):
    actor.call("screenshot", screenshot)
    width, height = struct.unpack(">II", screenshot.read_bytes()[16:24])
    return ((width / 2 - 256) // 2, (height / 2 - 256) // 2 - 8)


def editor_open(actor, host, player, expected):
    actor.call("wait", 12)
    actor.call("mouse", "right", "click")
    multiplayer.until("the Clipboard editor to open", lambda: actor.call("state")["screen"] == "mod")
    multiplayer.until("the held Clipboard to match Java editing state", lambda:
                      clipboard.held_clipboard(host, player) == expected)


def editor_close(actor, host, player, expected):
    actor.call("key", "escape", "tap")
    multiplayer.until("the Clipboard screen to close", lambda: actor.call("state")["screen"] == "playing")
    multiplayer.until("the held Clipboard contents to match Java", lambda:
                      clipboard.held_clipboard(host, player) == expected)


def enter_pages(actor, origin):
    x, y = origin
    actor.call("type", "Sort brass")
    actor.call("key", "enter", "tap")
    actor.call("type", "#Warehouse")
    actor.call("click-at", x + 49, y + 55)
    actor.call("key", "pagedown", "tap")
    actor.call("type", "Visit station")


def open_placed(actor, position):
    x, y, z = position
    actor.call("wait", 6)
    actor.call("look-at", x + .5, y + .03125, z + .5)
    multiplayer.until("the placed Clipboard in the player's aim", lambda:
                      bool(clipboard.ray_hit(actor, position, "up")))
    actor.call("mouse", "right", "click")
    multiplayer.until("the placed Clipboard editor to open", lambda: actor.call("state")["screen"] == "mod")


def close_placed(actor):
    actor.call("key", "escape", "tap")
    multiplayer.until("the placed Clipboard screen to close", lambda: actor.call("state")["screen"] == "playing")


def board_item(host, position):
    response = host.command(f"/data get block {clipboard.coords(position)} ClipboardItem")
    _, delimiter, data = response.partition("block data: ")
    if not delimiter:
        return {"id": ITEM, "count": 1}
    item = clipboard.menu.clipboard_snbt(data)
    item.pop("Slot", None)
    return item


def expected_board_state(reference):
    return reference.replace("Block{create:clipboard}", ITEM)


def erase_line(actor, origin, line):
    x, y = origin
    actor.call("click-at", x + 79, y + 55 + line * 12)
    actor.call("key", "ctrl", "down")
    try:
        actor.call("key", "a", "tap")
    finally:
        actor.call("key", "ctrl", "up")
    actor.call("key", "backspace", "tap")


def replay_placed(host, actor, player, screenshot, original, reference):
    position = (8, 101, -7)
    host.commands((
        f"/tp {player} 8.5 101 -9.5",
        f"/gamemode survival {player}",
        f"/setblock {clipboard.coords(position)} create:clipboard[face=floor,facing=north]",
    ))
    actor.call("options-set", "guiScale", "2")
    tick = host.clock()
    open_placed(actor, position)
    initial = anchor(actor, screenshot)
    enter_pages(actor, initial)
    close_placed(actor)
    written_state = expected_board_state(reference["placed_close"]["block"])
    multiplayer.until("the placed Clipboard to save the original written state and item", lambda: (
        host.call("block", *position)["state"] == written_state
        and board_item(host, position) == original["placed_close"]
    ))
    multiplayer.until("the client to see the written Clipboard", lambda:
                      actor.call("block", *position)["state"] == written_state)
    assert host.clock() == tick
    assert clipboard.held_clipboard(host, player) == {}
    print("A placed Clipboard saved the exact Java component and switched to its written block state.")

    if host is actor:
        host.command("/save-all")
        host.restart()
        host.command(f"/tp {player} 8.5 101 -9.5")
        host.call("command", f"/gamemode survival {player}")
        actor.call("options-set", "guiScale", "2")
        multiplayer.until("the written block to load after restart", lambda:
                          host.call("block", *position)["state"] == written_state)
        assert board_item(host, position) == original["placed_close"]
        tick = host.clock()
        print("The placed Clipboard retained the exact written component after restarting the world.")

    open_placed(actor, position)
    close_placed(actor)
    multiplayer.until("the placed Clipboard to preserve both pages across reopening", lambda:
                      board_item(host, position) == original["placed_close"])

    open_placed(actor, position)
    erase_line(actor, initial, 0)
    actor.call("key", "pageup", "tap")
    erase_line(actor, initial, 0)
    erase_line(actor, initial, 1)
    close_placed(actor)
    blank_state = expected_board_state(reference["placed_clear"]["block"])
    multiplayer.until("the placed Clipboard to clear the saved component and block state", lambda: (
        host.call("block", *position)["state"] == blank_state
        and board_item(host, position) == original["placed_clear"]
    ))
    multiplayer.until("the client to see the blank Clipboard", lambda:
                      actor.call("block", *position)["state"] == blank_state)
    assert host.clock() == tick
    assert clipboard.held_clipboard(host, player) == {}
    print("Clearing both pages returned the placed Clipboard and its saved item to the Java blank state.")


def replay(host, actor, player, screenshot, original):
    host.commands((
        f"/tp {player} 8.5 101 -9.5 0 -80",
        f"/gamemode survival {player}",
        f"/item replace entity {player} hotbar.0 with {ITEM}",
    ))
    multiplayer.until("one Clipboard in the player's hotbar", lambda: multiplayer.count(actor, ITEM) == 1)
    actor.call("select", ITEM)
    actor.call("options-set", "guiScale", "2")
    multiplayer.until("the player's camera to face empty space", lambda: not actor.call("looking-at").get("block"))

    editor_open(actor, host, player, original["opening"])
    editor_close(actor, host, player, original["blank_close"])
    print("Blank use and close match Java, including removal of the editing component.")

    editor_open(actor, host, player, original["opening"])
    x, y = anchor(actor, screenshot)
    enter_pages(actor, (x, y))
    editor_close(actor, host, player, original["written_close"])
    print("Two pages, the checked entry and the last viewed page match Java.")

    support = (8, 103, -7)
    host.command("/setblock 8 103 -7 minecraft:stone")
    actor.call("look-at", 8.5, 103.5, -6.99)
    multiplayer.until("the player to aim at the Stone", lambda:
                      (actor.call("looking-at").get("block") or {}).get("pos") == list(support))
    editor_open(actor, host, player, original["reopen"])
    editor_close(actor, host, player, original["written_close"])
    assert host.call("block", 8, 103, -8)["block"] == "minecraft:air"
    print("Reopening while aimed at Stone preserves both pages without placing the Clipboard.")


def replay_layout(host, actor, player, screenshot, original):
    host.commands((
        f"/tp {player} 8.5 101 -9.5 0 -80",
        f"/gamemode survival {player}",
        f"/item replace entity {player} hotbar.0 with {ITEM}",
    ))
    multiplayer.until("one Clipboard in the player's hotbar", lambda: multiplayer.count(actor, ITEM) == 1)
    actor.call("select", ITEM)
    actor.call("options-set", "guiScale", "2")
    multiplayer.until("the player's camera to face empty space", lambda: not actor.call("looking-at").get("block"))
    editor_open(actor, host, player, original["opening"])
    for row in range(1, 16):
        actor.call("type", f"Row {row:02d}")
        actor.call("key", "enter", "tap")
    actor.call("type", "!")
    actor.call("key", "escape", "tap")
    expected = [f"Row {row:02d}" for row in range(1, 15)] + ["Row 15!"]

    def pages():
        return clipboard.held_clipboard(host, player).get("components", {}).get(
            "create:clipboard_content", {},
        ).get("pages", [])

    multiplayer.until("exactly 15 rows on the page under the original height bound", lambda:
                      [[entry["text"] for entry in page] for page in pages()] == [expected])
    print("Fifteen 12-pixel notes fit. Enter at the height limit keeps editing the last row.")

    host.command(f"/item replace entity {player} hotbar.0 with {ITEM}")
    editor_open(actor, host, player, original["opening"])
    x, y = anchor(actor, screenshot)
    long = "W" * 29
    actor.call("type", long)
    actor.call("key", "enter", "tap")
    actor.call("type", "First")
    actor.call("key", "shift", "down")
    try:
        actor.call("wait", 2)
        actor.call("key", "enter", "tap")
        actor.call("wait", 2)
    finally:
        actor.call("key", "shift", "up")
    actor.call("type", "Second")
    actor.call("click-at", x + 49, y + 75)
    actor.call("key", "escape", "tap")
    multiplayer.until("the wrapped first row and checked two-line note to save", lambda:
                      [[(entry["text"], entry["checked"]) for entry in page] for page in pages()]
                      == [[(long, 0), ("First\nSecond", 1)]])
    print("The second checkbox follows the wrapped first note and Shift+Enter saves a line break.")



def replay_controls(host, actor, player, screenshot, original):
    host.commands((
        f"/tp {player} 8.5 101 -9.5 0 -80",
        f"/gamemode survival {player}",
        f"/item replace entity {player} hotbar.0 with {ITEM}",
    ))
    multiplayer.until("one Clipboard in the player's hotbar", lambda: multiplayer.count(actor, ITEM) == 1)
    actor.call("select", ITEM)
    actor.call("options-set", "guiScale", "2")
    multiplayer.until("the player's camera to face empty space", lambda: not actor.call("looking-at").get("block"))
    editor_open(actor, host, player, original["opening"])
    x, y = anchor(actor, screenshot)
    actor.call("type", "Alpha")
    actor.call("key", "shift", "down")
    try:
        actor.call("wait", 2)
        actor.call("key", "enter", "tap")
        actor.call("wait", 2)
    finally:
        actor.call("key", "shift", "up")
    actor.call("type", "Beta")
    actor.call("key", "home", "tap")
    actor.call("type", "x")
    actor.call("key", "left", "tap")
    actor.call("key", "delete", "tap")
    actor.call("type", ">")
    actor.call("key", "end", "tap")
    actor.call("type", "?")
    actor.call("key", "up", "tap")
    actor.call("key", "home", "tap")
    actor.call("type", "[")
    actor.call("key", "down", "tap")
    actor.call("key", "end", "tap")
    actor.call("type", "]")
    actor.call("click-at", x + 185, y + 235)
    actor.call("type", "Next page")
    actor.call("click-at", x + 61, y + 235)

    log = actor.socket.parent / "ctl.log"
    offset = log.stat().st_size
    for event, low, high in (("clipboard_check", .95, 1.0), ("clipboard_erase", .90, 1.10)):
        actor.call("click-at", x + 49, y + 55)
        prefix = f"CREATE_CLIPBOARD_AUDIO create:{event} "
        multiplayer.until(f"the {event} UI cue", lambda: prefix in log.read_text()[offset:])
        pitch = float(log.read_text()[offset:].split(prefix, 1)[1].splitlines()[0])
        assert low <= pitch <= high, (event, pitch)

    actor.call("screenshot", screenshot)
    actor.call("click-at", x + 243, y + 182)
    multiplayer.until("the original Close control to dismiss the editor", lambda: actor.call("state")["screen"] == "playing")

    def saved_pages():
        data = clipboard.held_clipboard(host, player).get("components", {}).get(
            "create:clipboard_content", {},
        )
        return data.get("previously_opened_page"), [
            [(entry["text"], entry["checked"]) for entry in page] for page in data.get("pages", [])
        ]

    expected = 0, [[("[Alpha\n>Beta?]", 0)], [("Next page", 0)]]
    multiplayer.until("the line-navigation and page-button edits to save", lambda: saved_pages() == expected)
    print("Wrapped Home, End, Up, Down and Delete, page arrows, Close and both muted sound cues matched the Java source rules.")



def replay_selection(host, actor, player, screenshot, original):
    host.commands((
        f"/tp {player} 8.5 101 -9.5 0 -80",
        f"/gamemode survival {player}",
        f"/item replace entity {player} hotbar.0 with {ITEM}",
    ))
    multiplayer.until("one Clipboard in the player's hotbar", lambda: multiplayer.count(actor, ITEM) == 1)
    actor.call("select", ITEM)
    actor.call("options-set", "guiScale", "2")
    multiplayer.until("the player's camera to face empty space", lambda: not actor.call("looking-at").get("block"))
    editor_open(actor, host, player, original["opening"])
    x, y = anchor(actor, screenshot)

    def shortcut(letter):
        modifier = "super" if sys.platform == "darwin" else "ctrl"
        actor.call("key", modifier, "down")
        try:
            actor.call("key", letter, "tap")
            actor.call("wait", 2)
        finally:
            actor.call("key", modifier, "up")

    actor.call("type", "alpha beta gamma")
    actor.call("script", script=f"click-at {x+98} {y+55}\nclick-at {x+98} {y+55}\n")
    shortcut("c")
    actor.call("key", "end", "tap")
    actor.call("type", " / ")
    shortcut("v")
    actor.call("key", "enter", "tap")
    actor.call("type", "delta")
    actor.call("drag-at", x + 58, y + 66, x + 70, y + 66, x + 200, y + 66)
    shortcut("x")
    actor.call("type", "Moved ")
    shortcut("v")
    actor.call("scroll-at", x + 241, y + 161, 0)
    actor.call("wait", 2)
    actor.call("screenshot", screenshot)
    actor.call("key", "escape", "tap")

    def saved():
        component = clipboard.held_clipboard(host, player).get("components", {}).get(
            "create:clipboard_content", {},
        )
        return [[entry["text"] for entry in page] for page in component.get("pages", [])]

    expected = [["alpha beta gamma / beta", "Moved delta"]]
    try:
        multiplayer.until("the word and dragged text to paste into the correct notes", lambda:
                          saved() == expected, seconds=6)
    except RuntimeError as error:
        raise AssertionError((saved(), expected)) from error
    print("Double-click copied the selected word. Drag, cut, and paste moved the selected note through the offscreen clipboard.")



def run(args):
    env = {"HORIZON_NO_AUDIO": "1", "CREATE_CLIPBOARD_AUDIO_TRACE": "1"}
    reference = json.loads((ROOT / "fixtures/clipboard-editor-java.json").read_text())
    original = {scenario: clipboard.menu.clipboard_snbt(row["item"]) for scenario, row in reference.items()}
    with ExitStack() as resources:
        scratch = Path(resources.enter_context(TemporaryDirectory(prefix="hc-ce-")))
        mode = "Guest" if args.lan else "Solo"
        host = resources.enter_context(fixture_world(
            args, f"ClipboardEditor{mode}" + ("Placed" if args.placed else "Layout" if args.layout else "Controls" if args.controls else ""),
            pack=args.pack, render=not args.lan, env=env,
        ))
        host.commands((
            "/fill 5 100 -14 16 100 -4 minecraft:smooth_stone",
            "/fill 5 101 -14 16 109 -4 minecraft:air",
        ))
        actor, name = host, "@s"
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            name = "ClipboardGuest"
            actor = resources.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, pack=args.pack, render=True,
                scenario="clipboard-editor", env=env,
            ))
            multiplayer.until("the Clipboard editor guest to join", lambda: any(
                guest["name"] == name and guest["placed"] for guest in host.call("lan", "status")["guests"]
            ))
            host.command("/tp @s 5.5 101 -9.5")
        screenshot = args.screenshot or scratch / "clipboard-editor.png"
        if args.selection:
            replay_selection(host, actor, name, screenshot, original)
            return
        if args.controls:
            replay_controls(host, actor, name, screenshot, original)
            return
        if args.layout:
            replay_layout(host, actor, name, screenshot, original)
            return
        if args.placed:
            replay_placed(host, actor, name, screenshot, original, reference)
        else:
            replay(host, actor, name, screenshot, original)
        target = "placed" if args.placed else "held"
        print(f"{mode} matched the original {target} Clipboard open and close snapshots.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--lan", action="store_true")
    scenario = parser.add_mutually_exclusive_group()
    scenario.add_argument("--placed", action="store_true")
    scenario.add_argument("--layout", action="store_true")
    scenario.add_argument("--controls", action="store_true")
    scenario.add_argument("--selection", action="store_true")
    parser.add_argument("--screenshot", type=Path)
    run(parser.parse_args())
