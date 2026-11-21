#!/usr/bin/env python3
"""Check Cardboard Sword components and player state across a world reopen."""
import argparse
from importlib import import_module
import os
from pathlib import Path
import tempfile
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

placement = import_module("test-package-placement")
SWORD = "create:cardboard_sword"


def main():
    os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ("ctl", "client", "resources"):
        parser.add_argument(parameter, type=Path)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(args.artifacts.resolve())

    with TemporaryDirectory(prefix="hc-sword-reopen-") as scratch:
        with fixture_world(args, "CardboardSwordReopen", render=True, pack=args.pack,
                           artifact_dir=args.artifacts) as host:
            host.commands((
                "/fill 0 100 -5 20 100 15 minecraft:stone",
                "/fill 0 101 -5 20 106 15 minecraft:air",
            ))
            with placement.package.filters.actor_for(host, args, None) as (actor, name):
                host.command(f"/gamemode survival {name}")
                host.commands((
                    f"/tp {name} 8.5 101 1.5",
                    f"/item replace entity {name} weapon.mainhand with {SWORD}[minecraft:damage=3,minecraft:enchantments={{\"minecraft:knockback\":1}}]",
                    "/summon minecraft:pig 8.5 101 3.5 {PersistenceRequired:1b,Tags:[sword_reopen_target]}",
                    "/attribute @e[tag=sword_reopen_target,limit=1] minecraft:movement_speed base set 0",
                    "/attribute @e[tag=sword_reopen_target,limit=1] minecraft:follow_range base set 0",
                ))
                multiplayer.until("the Cardboard Sword in the survival player's hand",
                                  lambda: (actor.call("inventory")["held"] or {}).get("item") == SWORD)
                actor.call("look-at", 8.5, 101.42, 3.5)
                placement.editor.wait_for(actor, "the pig under the crosshair",
                                          lambda: actor.call("looking-at").get("kind") == "entity")
                actor.call("wait", 14)
                actor.call("mouse", "left", "click")
                placement.editor.wait_for(host, "the cardboard Sword's Slowness effect", lambda:
                    "slowness" in host.command(
                        "/data get entity @e[tag=sword_reopen_target,limit=1] active_effects"))
                host.command("/save-all flush")
                host.restart()

                item = host.command(f"/data get entity {name} SelectedItem")
                assert (SWORD in item and '"minecraft:damage": 3' in item
                        and '"minecraft:knockback": 1' in item), item
                target_health = host.command(
                    "/data get entity @e[tag=sword_reopen_target,limit=1] Health")
                target_effects = host.command(
                    "/data get entity @e[tag=sword_reopen_target,limit=1] active_effects")
                assert "10.0f" in target_health, target_health
                assert "slowness" in target_effects, target_effects
                print("Survival owner, Knockback I, sword wear, and non-damaging mob hit survived save/reopen.",
                      flush=True)


if __name__ == "__main__":
    main()
