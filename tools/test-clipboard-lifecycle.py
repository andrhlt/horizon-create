#!/usr/bin/env python3
"""Check Clipboard payload compatibility and persistence after a world restart."""

import argparse
from contextlib import contextmanager
from copy import deepcopy
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

transfer = import_module("test-clipboard-copy")
editor = import_module("test-clipboard-editor")
multiplayer = import_module("test-multiplayer")
clipboard = editor.clipboard
BOARD = transfer.BOARD
SOURCE = transfer.SOURCE
TARGET = transfer.TARGET
RELOAD_TARGET = (16, 101, -11)
CHUTE = (10, 101, -7)
GUEST = "ClipboardGuest"
COMPONENT = "create:clipboard_content"


def connected(host):
    return any(player["name"] == GUEST and player["placed"]
               for player in host.call("lan", "status")["guests"])


@contextmanager
def player_client(args, host, scratch, scenario, env):
    if not args.lan:
        yield host, "@s"
        return
    port = host.call("lan", "open", "0", "commands", "force")["port"]
    with multiplayer.joined_client(args, scratch, f"127.0.0.1:{port}", GUEST,
                                   pack=args.pack, render=True, scenario=scenario, env=env) as guest:
        multiplayer.until("the Clipboard guest to join", lambda: connected(host))
        yield guest, GUEST


def link_data(snapshot):
    return snapshot.replace("First:", "FrequencyFirst:", 1).replace("Last:", "FrequencyLast:", 1)


def chute_settings(host):
    position = clipboard.coords(CHUTE)
    return tuple(host.command(f"/data get block {position} {key}").split("block data: ", 1)[1]
                 for key in ("Filter", "FilterAmount", "UpTo"))


def held_with_link(host, player):
    response = host.command(f"/data get entity {player} SelectedItem")
    _, delimiter, data = response.partition("entity data: ")
    return transfer.link_snbt(data) if delimiter else {}


def prepare(host, actor, player, screenshot, notes, before, after):
    board, source, target, reload_target, chute = map(
        clipboard.coords, (BOARD, SOURCE, TARGET, RELOAD_TARGET, CHUTE),
    )
    host.commands((
        f"/gamemode survival {player}",
        f"/tp {player} 8.5 101 -9.5",
        f"/setblock {board} create:clipboard[face=floor,facing=north]",
        f"/setblock {source} create:redstone_link[facing=up]",
        f"/data merge block {source} {link_data(after)}",
        f"/setblock {target} create:redstone_link[facing=up]",
        f"/data merge block {target} {link_data(before)}",
        f"/setblock {reload_target} create:redstone_link[facing=up]",
        f"/data merge block {reload_target} {link_data(before)}",
        f"/setblock {chute} create:smart_chute",
        "/setblock 10 102 -7 minecraft:barrel",
        f'/data merge block {chute} {{Filter:{{id:"minecraft:gold_ingot",count:1}},FilterAmount:3,UpTo:1b}}',
    ))
    actor.call("options-set", "guiScale", "2")
    editor.open_placed(actor, BOARD)
    editor.enter_pages(actor, editor.anchor(actor, screenshot))
    editor.close_placed(actor)
    multiplayer.until("the placed notes and checked entry to reach the host", lambda:
                      editor.board_item(host, BOARD) == notes["placed_close"])

    host.commands((
        f"/tp {player} 8.5 101 -9.5 0 -80",
        f"/item replace entity {player} hotbar.0 with {editor.ITEM}",
    ))
    multiplayer.until("one Clipboard to reach the player", lambda: multiplayer.count(actor, editor.ITEM) == 1)
    actor.call("select", editor.ITEM)
    multiplayer.until("the player to aim away from the placed board", lambda:
                      not actor.call("looking-at").get("block"))
    editor.editor_open(actor, host, player, notes["opening"])
    editor.enter_pages(actor, editor.anchor(actor, screenshot))
    editor.editor_close(actor, host, player, notes["written_close"])


def paste_link(host, actor, player, target, expected):
    transfer.aim(host, actor, player, target, .15)
    actor.call("mouse", "left", "click")
    multiplayer.until("the Java frequencies to reach the target Link", lambda:
                      transfer.link_frequencies(host, target) == expected)


def run(args):
    def reference(name):
        return json.loads((ROOT / "fixtures" / f"clipboard-{name}-java.json").read_text())

    raw_notes = reference("editor")
    notes = {label: clipboard.menu.clipboard_snbt(row["item"]) for label, row in raw_notes.items()}
    link = reference("link")
    link_data_before, link_data_after = link["paste"]["snapshots"]
    before, after = map(transfer.link_snbt, (link_data_before, link_data_after))
    payload = transfer.link_snbt(link["copy"]["snapshots"][0])["components"][COMPONENT]["copied_values"]
    written = deepcopy(notes["written_close"])
    written["components"][COMPONENT]["copied_values"] = payload
    env = {"HORIZON_NO_AUDIO": "1", "HORIZON_NO_DISCORD": "1"}
    mode = "Lan" if args.lan else "Solo"
    with (TemporaryDirectory(prefix="hc-cl-") as scratch,
          fixture_world(args, "ClipboardLifecycle" + mode, pack=args.pack,
                        render=not args.lan, env=env) as host):
        scratch = Path(scratch)
        screenshot = scratch / "editor.png"
        host.commands((
            "/fill 5 100 -14 18 100 -4 minecraft:smooth_stone",
            "/fill 5 101 -14 18 109 -4 minecraft:air",
        ))
        with player_client(args, host, scratch, "clipboard-lifecycle", env) as (actor, player):
            prepare(host, actor, player, screenshot, notes, link_data_before, link_data_after)
            tick = host.clock()
            transfer.aim(host, actor, player, SOURCE, .15)
            actor.call("mouse", "right", "click")
            multiplayer.until("the copied Link payload alongside both notes pages", lambda:
                              held_with_link(host, player) == written)

            # Java supplies an empty compound to FilteringBehaviour for a Frequencies-only payload.
            previous = chute_settings(host)
            chute_state = host.call("block", *CHUTE)["state"]
            transfer.aim(host, actor, player, CHUTE, .42, face=None)
            actor.call("mouse", "left", "click")
            actor.call("wait", 6)
            assert chute_settings(host) == previous
            assert host.call("block", *CHUTE)["state"] == chute_state
            assert held_with_link(host, player) == written
            assert actor.call("block", *CHUTE)["state"] == chute_state
            print("The Smart Chute rejected the Redstone Link payload and kept its filter, amount and mode.")

            assert transfer.link_frequencies(host, TARGET) == before
            paste_link(host, actor, player, TARGET, after)
            assert host.clock() == tick
        if args.lan:
            multiplayer.until("the Clipboard guest to disconnect", lambda: not connected(host))
        host.command("/save-all")
        host.restart()

        with player_client(args, host, scratch, "clipboard-lifecycle-rejoin", env) as (actor, player):
            multiplayer.until("the held Clipboard to return after loading", lambda:
                              multiplayer.count(actor, editor.ITEM) == 1)
            actor.call("select", editor.ITEM)
            host.call("command", f"/gamemode survival {player}")
            multiplayer.until("the saved notes and Link payload to return in the selected slot", lambda:
                              held_with_link(host, player) == written)
            assert editor.board_item(host, BOARD) == notes["placed_close"]
            assert transfer.link_frequencies(host, TARGET) == after
            assert chute_settings(host) == previous
            assert transfer.link_frequencies(host, RELOAD_TARGET) == before
            paste_link(host, actor, player, RELOAD_TARGET, after)
            assert held_with_link(host, player) == written
            print("The reopened world retained both notes pages, the copied payload and the pasted Link frequencies.")

            actor.call("key", "2", "tap")
            multiplayer.until("the actor to hold an empty slot", lambda:
                              held_with_link(host, player) == {})
            host.command(f"/tp {player} 8.5 101 -9.5")
            actor.call("options-set", "guiScale", "2")
            written_state = editor.expected_board_state(raw_notes["placed_close"]["block"])
            multiplayer.until("the actor to see the written board", lambda:
                              actor.call("block", *BOARD)["state"] == written_state)
            editor.open_placed(actor, BOARD)
            x, y = editor.anchor(actor, screenshot)
            actor.call("click-at", x + 49, y + 55)
            editor.close_placed(actor)
            toggled = deepcopy(notes["placed_close"])
            toggled["components"][COMPONENT]["pages"][1][0]["checked"] = 1
            multiplayer.until("the first note on the remembered page to be checked", lambda:
                              editor.board_item(host, BOARD) == toggled)
            print("The reopened placed Clipboard let the player check the existing note on the remembered page.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    run(parser.parse_args())
