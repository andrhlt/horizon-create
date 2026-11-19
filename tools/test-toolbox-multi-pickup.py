#!/usr/bin/env python3
"""Check that Toolbox pickup returns every linked player's stack before packing."""

import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

link = import_module("test-toolbox-link")
storage = link.storage
mp = link.mp


def replay(host, actors, attacker, compartments):
    host.commands((
        "/fill 8 99 -12 16 99 8 minecraft:stone",
        f"/setblock {storage.xyz(storage.POS)} {storage.BROWN}",
        "/gamemode survival @a",
        "/tp @s 11.5 100 -6.5",
        *(('/tp ToolboxGuest 13.5 100 -6.5',) if len(actors) == 2 else ()),
    ))
    slots = (0, 1, 4) if compartments == "distinct" else (0, 1, 2)
    for slot in slots:
        storage.replace(host, slot, "minecraft:cobblestone", 64)
    storage.step(host, 1)

    for index, actor in enumerate(actors.values()):
        actor.call("key", "1", "tap")
        actor.call("key", link.ALT, "down")
        mp.until("the Toolbox radial menu", lambda: actor.call("screen")["screen"] == "mod")
        actor.call("key", "2" if compartments == "distinct" and index else "1", "tap")
        mp.until("the radial menu to close", lambda: actor.call("screen")["screen"] == "playing")
        actor.call("key", link.ALT, "up")
        actor.call("wait", 3)
        storage.step(host, 1)
        mp.until("the linked stack to replenish", lambda:
            actor.call("inventory")["hotbar"][0].get("count") == 32)

    pickup = actors[attacker]
    pos = storage.POS
    pickup.call("look-at", pos[0] + .5, pos[1] + .3, pos[2] + .5)
    pickup.call("mouse", "left", "click")
    mp.until("the Toolbox pickup", lambda:
        pickup.call("inventory")["counts"].get(storage.BROWN) == 1)
    packed = next(item for item in pickup.call("inventory")["hotbar"]
                  if item.get("item") == storage.BROWN)
    contents = storage.toolbox.stack_components(packed)["create:toolbox_inventory"]["items"]["items"]
    count = sum(stack["count"] for stack in contents.values())
    assert count == 192, (attacker, count, contents)
    for name, actor in actors.items():
        mp.until(f"{name}'s linked stack to be returned", lambda:
            actor.call("inventory")["counts"].get("minecraft:cobblestone", 0) == 0)
    print(f"{attacker} pickup returned all {compartments}-compartment linked stacks before packing.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--attacker", choices=("solo", "host", "guest"), default="guest")
    parser.add_argument("--compartments", choices=("same", "distinct"), default="distinct")
    args = parser.parse_args()
    env = {"HORIZON_NO_AUDIO": "1"}
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(
            args, f"Toolbox-multi-{args.attacker}", render=True, pack=args.pack, env=env))
        actors = {"solo" if args.attacker == "solo" else "host": host}
        if args.attacker != "solo":
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-toolbox-multi-")))
            guest = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", "ToolboxGuest", render=True,
                scenario="toolbox-multi", pack=args.pack, env=env))
            mp.until("the Toolbox guest to join", lambda: any(
                entry["name"] == "ToolboxGuest" and entry["placed"]
                for entry in host.call("lan", "status")["guests"]))
            actors["guest"] = guest
        replay(host, actors, args.attacker, args.compartments)


if __name__ == "__main__":
    main()
