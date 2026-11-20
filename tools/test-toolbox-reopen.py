#!/usr/bin/env python3
"""Check that Toolbox contents and player links survive a cold world reopen."""

import argparse
import json
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

storage = import_module("test-toolbox-storage")
mp = storage.postbox.mp
POS = storage.POS
NEAR = (12.5, 100.0, -6.5)


def replay(args):
    with fixture_world(args, "ToolboxReopen", render=True, pack=args.pack) as control:
        control.commands((
            f"/setblock {storage.xyz(POS)} {storage.BROWN}",
            f"/item replace block {storage.xyz(POS)} container.0 with minecraft:cobblestone 64",
            "/gamemode survival",
            f"/tp @s {storage.xyz(NEAR)}",
        ))
        control.step_to(control.clock() + 1)
        control.call("key", "key.keyboard.left.alt", "down")
        mp.until("the Toolbox radial menu", lambda: control.call("screen")["screen"] == "mod")
        control.call("key", "1", "tap")
        mp.until("the Toolbox radial menu to close", lambda: control.call("screen")["screen"] == "playing")
        control.call("key", "key.keyboard.left.alt", "up")
        control.step_to(control.clock() + 1)

        mp.until("the initial Toolbox resupply", lambda:
            control.call("inventory")["hotbar"][0].get("count") == 32
            and storage.items(control).get(0) == "minecraft:cobblestone=32"
        )
        held = control.call("inventory")["hotbar"][0]
        assert held.get("item") == "minecraft:cobblestone" and held["count"] == 32, held
        assert storage.items(control).get(0) == "minecraft:cobblestone=32", storage.items(control)

        before = (held["item"], held["count"], storage.items(control).get(0))
        control.stop()
        player_data = control.socket.parent / "game" / "saves" / "ToolboxReopen" / "players" / "data"
        files = list(player_data.glob("*.create-toolbox.json"))
        assert len(files) == 1, files
        saved_links = json.loads(files[0].read_text(encoding="utf-8"))
        assert saved_links[0] == {"pos": list(POS), "compartment": 0}, saved_links
        control.open()
        reopened = control.call("inventory")["hotbar"][0]
        assert (reopened.get("item"), reopened.get("count"), storage.items(control).get(0)) == before
        saved_filters = storage.block_value(control, POS, "Compartments")
        assert saved_filters and "minecraft:cobblestone" in saved_filters, saved_filters

        control.command("/item replace entity @s hotbar.0 with minecraft:cobblestone 10")
        mp.until("the hotbar stack to be set to 10", lambda:
            control.call("inventory")["hotbar"][0].get("count") == 10
        )
        control.step_to(control.clock() + 1)
        try:
            mp.until("the saved Toolbox link to refill the hotbar", lambda:
                control.call("inventory")["hotbar"][0].get("count") == 32
                and storage.items(control).get(0) == "minecraft:cobblestone=10"
            )
        except RuntimeError as error:
            raise AssertionError((control.clock(), control.call("inventory")["hotbar"][0],
                                  storage.items(control), saved_filters)) from error
        after = control.call("inventory")["hotbar"][0]
        stored = storage.items(control).get(0)
        assert after.get("item") == "minecraft:cobblestone" and after["count"] == 32, after
        assert stored == "minecraft:cobblestone=10", stored

    print(
        "Toolbox inventory and player binding survived cold reopen; "
        "the saved link refilled the hotbar from the saved compartment."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ctl", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("client", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("resources", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    replay(parser.parse_args())
