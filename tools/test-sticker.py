#!/usr/bin/env python3
"""Exercise Sticker's rising-edge toggle in a headless world."""
import argparse
from pathlib import Path
import re
from fixture_world import fixture_world
from importlib import import_module

until = import_module("test-multiplayer").until

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with fixture_world(args, "Sticker", pack=args.pack) as host:
        host.commands(("/setblock 10 171 20 create:sticker[facing=up]", "/setblock 10 171 19 minecraft:air"))
        def state():
            return dict(re.findall(r"(\w+)=(\w+)", host.call("block", 10, 171, 20)["state"]))
        for source, powered, extended in (("redstone_block", "true", "true"), ("air", "false", "true"), ("redstone_block", "true", "false"), ("air", "false", "false")):
            host.command(f"/setblock 10 171 19 minecraft:{source}")
            until(f"Sticker powered={powered}, extended={extended}", lambda: state().get("powered") == powered and state().get("extended") == extended)
        host.commands((
            "/setblock 13 170 20 minecraft:stone",
            "/setblock 13 171 19 minecraft:redstone_block",
            "/setblock 13 171 22 minecraft:stone",
            "/tp @s 13.5 172 22.5 0 0",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:sticker",
        ))
        until("the actor to hold a Sticker", lambda: host.call("inventory")["counts"].get("create:sticker") == 1)
        host.call("interact", 13, 170, 20, "up")
        placed = host.call("block", 13, 171, 20)["state"]
        assert placed.startswith("create:sticker["), placed
        assert dict(re.findall(r"(\w+)=(\w+)", placed)) == {
            "extended": "false", "facing": "north", "powered": "true",
        }, placed
        assert "create:sticker" not in host.call("inventory")["counts"]
    print("Sticker toggled once per rising edge and stayed retracted on powered placement.")

if __name__ == "__main__":
    main()
