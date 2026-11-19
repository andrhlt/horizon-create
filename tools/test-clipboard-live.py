#!/usr/bin/env python3
"""Compare live placed Clipboard edits with the two-author Java update trace."""

import argparse
from contextlib import ExitStack
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

editor = import_module("test-clipboard-editor")
multiplayer = import_module("test-multiplayer")
BLOCK = (8, 101, -7)
COMPONENT = "create:clipboard_content"


def authoritative(host):
    state = host.call("block", *BLOCK)["state"]
    item = editor.board_item(host, BLOCK)
    return ("written=true" in state, item.get("components", {}))


def compare(host, row):
    expected = row["written"], editor.clipboard.menu.clipboard_snbt(row["components"])
    multiplayer.until(f"the Java Clipboard update from the {row['author']} author", lambda:
                      authoritative(host) == expected)


def opens(actor):
    editor.open_placed(actor, BLOCK)
    assert actor.call("state")["screen"] == "mod"


def run(args):
    env = {"HORIZON_NO_AUDIO": "1"}
    trace = json.loads((ROOT / "fixtures/clipboard-live-java.json").read_text())
    assert [(row["tick"], row["author"]) for row in trace] == [(0, "first"), (1, "second"), (2, "first")]
    with ExitStack() as resources:
        scratch = Path(resources.enter_context(TemporaryDirectory(prefix="hc-cl-")))
        host = resources.enter_context(fixture_world(
            args, "ClipboardLiveLan", pack=args.pack, render=True, env=env,
        ))
        host.commands((
            "/fill 5 100 -14 16 100 -4 minecraft:smooth_stone",
            "/fill 5 101 -14 16 109 -4 minecraft:air",
            "/setblock 8 101 -7 create:clipboard[face=floor,facing=north]",
            "/tp @s 8.5 101 -9.5",
            "/gamemode survival @s",
        ))
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        name = "ClipboardGuest"
        guest = resources.enter_context(multiplayer.joined_client(
            args, scratch, f"127.0.0.1:{port}", name, pack=args.pack, render=True,
            scenario="clipboard-live", env=env,
        ))
        multiplayer.until("the Clipboard guest to join", lambda: any(
            player["name"] == name and player["placed"] for player in host.call("lan", "status")["guests"]
        ))
        host.commands((f"/tp {name} 8.5 101 -4.5", f"/gamemode survival {name}"))
        for actor in (host, guest):
            actor.call("options-set", "guiScale", "2")
            opens(actor)
        host_panel = editor.anchor(host, scratch / "host.png")
        guest_panel = editor.anchor(guest, scratch / "guest.png")
        tick = host.clock()

        host.call("type", "Sort brss")
        multiplayer.until("the first draft before closing the editor", lambda:
                          "Sort brss" in str(authoritative(host)))
        host.call("key", "left", "tap")
        host.call("key", "left", "tap")
        host.call("type", "a")
        compare(host, trace[0])
        assert host.clock() == tick
        assert host.call("state")["screen"] == "mod"
        print("The host publishes text while open and keeps its own caret after the draft.")

        host.step_to(tick + 1)
        x, y = guest_panel
        guest.call("click-at", x + 49, y + 55)
        compare(host, trace[1])
        assert host.clock() == tick + 1
        assert guest.call("state")["screen"] == "mod"
        print("The guest receives the host’s text and toggles that entry while both editors are open.")

        host.step_to(tick + 2)
        x, y = host_panel
        host.call("click-at", x + 243, y + 161)
        multiplayer.until("the host to erase the guest’s checked entry while still open", lambda:
                          "Sort brass" not in str(authoritative(host)))
        assert host.call("state")["screen"] == "mod"
        editor.close_placed(host)
        compare(host, trace[2])
        assert host.clock() == tick + 2
        assert guest.call("state")["screen"] == "mod"
        editor.close_placed(guest)
        guest.call("wait", 5)
        compare(host, trace[2])
        print("The host receives the guest’s checkmark, clears the entry and leaves both clients blank.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, required=True)
    run(parser.parse_args())
