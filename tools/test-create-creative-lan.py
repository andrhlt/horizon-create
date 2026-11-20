#!/usr/bin/env python3
"""Check Create's creative inventory and tab retention on a LAN guest."""

import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
creative_tabs = import_module("test-create-creative-tabs")
GUEST = "CreativeGuest"
BOOTS = "create:netherite_diving_boots"
ENV = {"HORIZON_NO_AUDIO": "1"}


def creative_grid(client):
    client.call("open-inventory")
    multiplayer.until("creative inventory",
                      lambda: client.call("screen")["screen"] == "creative")
    left, top, *_ = next(widget["bounds"] for widget in client.call("ui")["widgets"]
                         if widget["id"] == "slot-900")
    return left - 9, top - 18


def search(client, x, y, query):
    # Leaving Search clears the old query via the same path as a normal click.
    client.call("click-at", x + 13, y - 13)
    client.call("click-at", x + 181, y - 12)
    client.call("type", query)
    client.call("wait", 5)
    return [widget for widget in client.call("ui")["widgets"]
            if widget["id"].startswith("slot-") and widget.get("stack")
            and 900 <= int(widget["id"][5:]) < 945]


def capture(client, filename, x, y):
    client.call("scroll-at", x, y, 0)
    client.call("wait", 4)
    client.call("screenshot", ROOT / ".local" / filename)


def check_inventory(client, tabs):
    x, y = creative_grid(client)
    client.call("click-at", x + 185, y - 40)
    for column, (name, tab) in enumerate(tabs.items()):
        tab_x = x + 13 + 27 * column
        client.call("click-at", tab_x, y - 13)
        multiplayer.until(f"guest {name} page", lambda: creative_tabs.first_page(client) == tab["items"][:45])
        capture(client, f"creative-lan-tab-{name}.png", tab_x, y - 13)
    client.call("close")
    x, y = creative_grid(client)
    if creative_tabs.first_page(client) != tabs["palettes"]["items"][:45]:
        raise AssertionError("The guest's selected Building Blocks tab changed on inventory reopen.")

    for query, expected in (
        ("netherite diving boots", [BOOTS]),
        ("ornate iron window", ["create:ornate_iron_window", "create:ornate_iron_window_pane"]),
        ("blaze cake base", ["create:blaze_cake_base"]),
        ("chromatic compound", []),
        ("incomplete precision mechanism", []),
        ("incomplete track", []),
    ):
        matches = search(client, x, y, query)
        actual = [widget["stack"]["item"] for widget in matches]
        if set(actual) != set(expected):
            raise AssertionError(f"{query!r}: expected {expected}, saw {actual}.")
        if actual:
            item = next(widget for widget in matches if widget["stack"]["item"] == expected[0])
            left, top, *_ = item["bounds"]
            capture(client, f"creative-lan-{expected[0].removeprefix('create:')}.png", left + 8, top + 8)
    client.call("close")


def run(args):
    tabs = creative_tabs.pack_tabs(args.pack)
    with TemporaryDirectory(prefix="hc-creative-lan-") as scratch, fixture_world(
        args, "Creative inventory LAN", pack=args.pack, env=ENV,
    ) as host:
        host.command("/tick unfreeze")
        port = host.call("lan", "open", 0, "commands", "force")["port"]
        address = f"127.0.0.1:{port}"

        def placed():
            return any(player["name"] == GUEST and player["placed"]
                       for player in host.call("lan", "status")["guests"])

        with multiplayer.joined_client(
            args, Path(scratch), address, GUEST, render=True, scenario="creative-inventory-join",
            pack=args.pack, env=ENV,
        ) as guest:
            multiplayer.until("creative guest to join", placed)
            host.call("command", f"/gamemode creative {GUEST}")
            multiplayer.until("guest Creative mode",
                              lambda: guest.call("state")["gamemode"] == "creative")
            check_inventory(guest, tabs)
    print("Guest opened both Create tabs, kept the selected tab on inventory reopen, "
          "and checked three included and three excluded queries in live Search.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    run(parser.parse_args())
