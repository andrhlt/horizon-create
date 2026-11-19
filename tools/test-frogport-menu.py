#!/usr/bin/env python3
"""Use a Frogport inventory or edit its settings through normal menu input."""

import argparse
import csv
import json
import re
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
chain = import_module("test-chain-conveyor-packages")
FROGPORT = "create:package_frogport"
PACKAGE = "create:cardboard_package_12x12"
PORT = (12, 100, -9)
FEET = (12.5, 100.0, -6.5)


def stack_item(actor, slot):
    return next(((entry.get("stack") or {}).get("item") for entry in actor.call("menu")["slots"]
                 if entry["slot"] == slot), None)


def address(host):
    output = host.command("/data get block 12 100 -9 AddressFilter")
    return output.rsplit("data: ", 1)[-1]


def receiving(host):
    output = host.command("/data get block 12 100 -9 AcceptsPackages")
    return output.rsplit("data: ", 1)[-1]


def edit_settings(host, actor):
    send_only = "Only send packages"
    send_receive = "Send and receive packages"
    with (ROOT / "fixtures/frogport-settings-java.csv").open(newline="") as stream:
        java = {int(row["tick"]): row for row in csv.DictReader(stream)}

    def saved(tick):
        row = java[tick]
        return (address(host) == f'"{row["saved_address"]}"'
                and receiving(host) == ("1b" if row["saved_receive"] == "true" else "0b"))

    host.command('/data merge block 12 100 -9 {AddressFilter:"",AcceptsPackages:1b}')
    actor.call("interact", *PORT, "south")
    actor.call("wait", 4)
    names = str(actor.call("screen"))
    assert "Frogport Address" in names and send_only not in names and send_receive not in names, names
    actor.call("click-button", "Frogport Address")
    actor.call("type", "Warehouse")
    actor.call("key", "enter", "tap")
    actor.call("wait", 4)
    assert saved(2), (address(host), receiving(host))
    assert "Frogport Address" in str(actor.call("screen"))
    actor.call("click-button", "Confirm")
    multiplayer.until("the unlinked address to save on confirm", lambda: saved(3))

    host.commands((
        "/setblock 10 102 -9 create:chain_conveyor",
        '/data merge block 12 100 -9 {Target:{RelativePos:[I;-2,2,0],ChainPosition:150f}}',
    ))
    actor.call("interact", *PORT, "south")
    actor.call("wait", 4)
    names = str(actor.call("screen"))
    assert send_only in names and send_receive in names, names
    actor.call("click-button", send_only)
    actor.call("wait", 4)
    assert saved(4), (address(host), receiving(host))
    actor.call("key", "escape", "tap")
    multiplayer.until("send-only to save on Escape", lambda: saved(5))

    wheel = (10, 102, -9)
    host.commands((
        "/setblock 10 101 -9 create:creative_motor[facing=up]",
        "/data merge block 10 101 -9 {ScrollValue:128}",
        "/data merge block 12 100 -9 {Items:[]}",
        "/data merge block 10 102 -9 {PackagePorts:[{Port:[I;2,-2,0],ChainPosition:150f}]}",
    ))
    old_package = chain.stack("Warehouse", "string", 2)
    chain.merge(host, wheel, f"{{Packages:[{{Item:{old_package},Position:140f}}]}}")
    actor.call("wait", 12)
    assert "Warehouse" in host.command("/data get block 10 102 -9 Packages")
    assert "minecraft:string" not in host.command("/data get block 12 100 -9 Items")
    assert saved(6), (address(host), receiving(host))

    actor.call("interact", *PORT, "south")
    actor.call("wait", 4)
    actor.call("click-button", "Frogport Address")
    actor.call("type", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    actor.call("click-button", send_receive)
    actor.call("click-button", "Confirm")
    multiplayer.until("the capped address and receive mode to save", lambda:
                      saved(7))
    new_package = chain.stack(java[8]["loop_filter"], "paper", 3)
    chain.merge(host, wheel, f"{{Packages:[{{Item:{old_package},Position:140f}},{{Item:{new_package},Position:140f}}]}}")
    inventory = lambda: host.command("/data get block 12 100 -9 Items")
    multiplayer.until("the newly addressed package to reach the Frogport", lambda:
                      java[8]["loop_filter"] in inventory())
    assert saved(8), (address(host), receiving(host))
    assert "minecraft:string" not in inventory()
    assert "minecraft:string" in host.command("/data get block 10 102 -9 Packages")
    host.restart()
    assert saved(8), (address(host), receiving(host))
    print("Frogport: Java settings, save-on-close, receive routing and persistence across restart")


def put_goggles_on_frogport(host, actor, name):
    with (ROOT / "fixtures/frogport-goggles-java.csv").open(newline="") as stream:
        java = list(csv.DictReader(stream))

    def saved(click, check_hand=True):
        port = host.command("/data get block 12 100 -9 Goggles").endswith("1b")
        if port != (java[click]["saved_decorated"] == "true"):
            return False
        if not check_hand:
            return True
        count = host.command(f"/data get entity {name} SelectedItem.count").rsplit("data: ", 1)[-1]
        return count == java[click]["held_count"]

    log = actor.socket.parent / "ctl.log"
    offset = len(log.read_text())
    host.command(f"/item replace entity {name} hotbar.0 with create:goggles")
    multiplayer.until("goggles in the player's hotbar", lambda:
                      actor.call("inventory")["counts"].get("create:goggles") == 1)
    actor.call("select", "create:goggles")
    actor.call("look-at", 12.5, 100.55, -8.5)
    assert saved(0)
    actor.call("use-item")
    multiplayer.until("the Frogport to keep its goggles and leave the held stack", lambda: saved(1))
    assert stack_item(actor, 317) is None, "first click opened the inventory"
    multiplayer.until("the owner's Frogport to render the goggles", lambda:
                      "CREATE_FROGPORT_GOGGLES_MODEL [12, 100, -9]" in log.read_text()[offset:])
    actor.call("wait", 5)
    actor.call("use-item")
    multiplayer.until("the second click to open the inventory", lambda:
                      stack_item(actor, 317) == PACKAGE)
    assert saved(2)
    actor.call("close")
    host.restart()
    assert saved(2, check_hand=False)
    print("Frogport goggles: the first click decorated it without spending the item, the second opened its menu, and the decoration survived restart.")


def clipboard_snbt(data):
    quoted = re.sub(r'([,{])\s*([A-Za-z_][A-Za-z0-9_]*):', r'\1"\2":', data)
    return json.loads(re.sub(r'\b(-?\d+)b(?=\s*[,}])', r'\1', quoted))


def copy_to_clipboard(host, actor, name):
    item = "create:clipboard"
    host.commands((
        "/setblock 14 100 -7 minecraft:crafting_table",
        f"/item replace entity {name} hotbar.2 with create:andesite_alloy",
        f"/item replace entity {name} hotbar.3 with minecraft:paper",
        f"/item replace entity {name} hotbar.4 with minecraft:oak_planks",
    ))
    actor.call("interact", 14, 100, -7, "west")
    for hotbar, grid in ((2, 100), (3, 103), (4, 106)):
        actor.call("click-slot", hotbar)
        actor.call("click-slot", grid)
    multiplayer.until("the original Clipboard recipe to appear", lambda: stack_item(actor, 200) == item)
    actor.call("click-slot", 200, "shift")
    multiplayer.until("the Clipboard to be crafted", lambda:
                      actor.call("inventory")["counts"].get(item) == 1)
    actor.call("close")
    actor.call("look-at", 12.5, 100.55, -8.5)

    model_log = actor.socket.parent / "ctl.log"
    for row in json.loads((ROOT / "fixtures/frogport-clipboard-java.json").read_text()):
        expected = clipboard_snbt(row["after"])
        initial = clipboard_snbt(row["before"])
        if row["scenario"] != "duplicate":
            host.command(f"/clear {name} {item}")
            if initial.get("components"):
                host.command("/setblock 14 100 -7 minecraft:barrel")
                host.command("/data merge block 14 100 -7 {Items:[{Slot:0b," + row["before"][1:] + "]}")
                actor.call("interact", 14, 100, -7, "west")
                multiplayer.until("the original Clipboard in its supply barrel", lambda: stack_item(actor, 300) == item)
                actor.call("click-slot", 300)
                actor.call("click-slot", 0)
                actor.call("close")
            else:
                host.command(f"/item replace entity {name} hotbar.0 with {item}")
        host.command(f'/data merge block 12 100 -9 {{AddressFilter:{json.dumps(row["address"], ensure_ascii=False)}}}')
        multiplayer.until("the Clipboard to reach the hotbar", lambda:
                          actor.call("inventory")["counts"].get(item) == 1)
        actor.call("select", item)
        actor.call("look-at", 12.5, 100.55, -8.5)
        actor.call("wait", 2)
        offset = len(model_log.read_text())
        actor.call("use-item")
        actor.call("wait", 5)
        actual = host.command(f"/data get entity {name} SelectedItem")
        actual = clipboard_snbt(actual.split("entity data: ", 1)[1])
        assert actual == expected, (row["scenario"], actual, expected)
        hotbar = next(stack for stack in actor.call("inventory")["hotbar"] if stack["slot"] == 0)
        visible = clipboard_snbt(hotbar.get("components") or "{}")
        assert visible == expected.get("components", {}), (row["scenario"], visible, expected)
        assert stack_item(actor, 317) is None, row["scenario"]
        if row["scenario"] in ("blank", "first"):
            rendered = "true" if row["scenario"] == "first" else "false"
            multiplayer.until("the original Clipboard model to resolve", lambda:
                              f"CREATE_CLIPBOARD_MODEL written,{rendered}" in model_log.read_text()[offset:])
        print(f'Clipboard {row["scenario"]}: held and client component matched Java')

def run(args):
    mode = "Lan" if args.lan else "Solo"
    if args.settings:
        mode += "Settings"
    if args.goggles:
        mode += "Goggles"
    if args.clipboard:
        mode += "Clipboard"
    env = None
    if args.goggles:
        env = {"CREATE_CHAIN_RENDER": "1", "HORIZON_NO_AUDIO": "1"}
    if args.clipboard:
        env = {"CREATE_CLIPBOARD_MODEL": "1", "HORIZON_NO_AUDIO": "1"}
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, f"FrogportMenu{mode}", pack=args.pack, render=not args.lan, env=env))
        host.commands((
            "/fill 9 99 -10 14 99 -6 minecraft:stone",
            "/setblock 12 100 -9 " + FROGPORT,
            "/item replace block 12 100 -9 container.17 with " + PACKAGE,
        ))
        actor, name = host, "@s"
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            name = "FrogportGuest"
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-frogport-")))
            actor = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, scenario=f"frogport-menu-{mode}", pack=args.pack, render=True, env=env,
            ))
            multiplayer.until("the Frogport guest to join", lambda: any(
                guest["name"] == name and guest["placed"] for guest in host.call("lan", "status")["guests"]
            ))
        host.commands((
            f"/gamemode survival {name}",
            f"/tp {name} {' '.join(map(str, FEET))}",
            f"/item replace entity {name} hotbar.1 with minecraft:stone",
            "/tick unfreeze",
        ))
        multiplayer.until("the player to reach the Frogport", lambda:
                          actor.call("state")["player"]["position"] == list(FEET))
        multiplayer.until("the player to see the Frogport", lambda:
                          actor.call("block", *PORT)["block"] == FROGPORT)
        if args.clipboard:
            copy_to_clipboard(host, actor, name)
            return
        if args.goggles:
            put_goggles_on_frogport(host, actor, name)
            return
        if args.settings:
            edit_settings(host, actor)
            return
        actor.call("interact", *PORT, "south")
        multiplayer.until("the Frogport's last slot to show the package", lambda:
                          stack_item(actor, 317) == PACKAGE)
        actor.call("click-slot", 317)
        actor.call("click-slot", 0)
        multiplayer.until("the package to move to the hotbar", lambda:
                          stack_item(actor, 0) == PACKAGE and stack_item(actor, 317) is None)
        actor.call("click-slot", 1)
        actor.call("click-slot", 317)
        multiplayer.until("the Frogport to reject the stone", lambda:
                          (actor.call("menu")["carried"] or {}).get("item") == "minecraft:stone"
                          and stack_item(actor, 317) is None)
        actor.call("click-slot", 1)
        actor.call("click-slot", 0)
        actor.call("click-slot", 317)
        multiplayer.until("the Frogport to accept the package", lambda:
                          stack_item(actor, 317) == PACKAGE)
        actor.call("close")
        actor.call("interact", *PORT, "south")
        multiplayer.until("the reopened Frogport to retain the package", lambda:
                          stack_item(actor, 317) == PACKAGE)
        print(f"{mode}: Frogport slot 18 extracted, rejected stone, accepted and retained the package")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--lan", action="store_true")
    scenario = parser.add_mutually_exclusive_group()
    scenario.add_argument("--settings", action="store_true")
    scenario.add_argument("--goggles", action="store_true")
    scenario.add_argument("--clipboard", action="store_true")
    run(parser.parse_args())
