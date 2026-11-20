#!/usr/bin/env python3
"""Exercise Mixer item rolls across active/idle reopen and LAN pickup."""

import argparse
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
inventory = import_module("test-material-recipes").inventory
stacks = import_module("test-brass-mixing").stacks
number = import_module("test-fluid-food").number
MIXER = "5 106 16"
BASIN = "5 104 16"
DEPOT = "6 103 16"
GUEST = "MixerGuest"
RECIPE = "create:mixing/fixture_chance"
INPUT = "minecraft:diamond"
BONUS = "minecraft:gold_nugget"


def install_recipe(host):
    world = host.socket.parent / "game/saves/MixerChance"
    pack = world / "datapacks/mixer-fixture"
    path = pack / "data/create/recipe/mixing/fixture_chance.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "type": "create:mixing", "processing_time": 200,
        "ingredients": [{"item": INPUT}],
        "results": [
            {"id": BONUS, "count": 64, "chance": 0.5},
            {"id": "minecraft:iron_nugget"},
            {"id": "minecraft:copper_ingot"},
        ],
    }))
    (pack / "pack.mcmeta").write_text('{"pack":{"description":"Mixer chance fixture"}}')
    (world / "datapacks.json").write_text('{"enabled":["vanilla","file/mixer-fixture"],"disabled":[]}')
    host.command("/reload")


def slots(host, block):
    return inventory(host.command(f"/data get block {block}"))


def run(args):
    with fixture_world(args, "MixerChance", pack=args.pack) as host:
        install_recipe(host)
        host.commands((
            "/fill 2 102 13 10 102 21 minecraft:stone",
            "/tp @s 3.5 103 19.5",
            "/setblock 4 105 16 create:creative_motor[facing=up]",
            "/data merge block 4 105 16 {ScrollValue:256}",
            "/setblock 4 106 16 create:cogwheel[axis=y]",
            f"/setblock {MIXER} create:mechanical_mixer",
            f"/setblock {DEPOT} create:depot",
            f"/setblock {BASIN} create:basin[facing=east]",
        ))
        host.command(f"/item replace block {BASIN} container.0 with {INPUT}")
        for _ in range(60):
            host.step_to(host.clock() + 1)
            mixer = host.command(f"/data get block {MIXER}")
            if number(mixer, "ProcessingTicks") >= 20:
                break
        else:
            raise AssertionError(f"Mixer never started processing the fixture: {mixer}")
        assert RECIPE in mixer and slots(host, BASIN) == {0: (INPUT, 1)}, mixer
        assert not slots(host, DEPOT)
        host.restart()
        resumed = host.command(f"/data get block {MIXER}")
        assert RECIPE in resumed and number(resumed, "Running") == 1, resumed
        assert 0 < number(resumed, "ProcessingTicks") <= number(mixer, "ProcessingTicks"), resumed
        assert slots(host, BASIN) == {0: (INPUT, 1)} and not slots(host, DEPOT)

        port = host.call("lan", "open", 0, "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-mixer-lan-") as tmp, mp.joined_client(
            args, Path(tmp), f"127.0.0.1:{port}", GUEST, scenario="mixer-chance", pack=args.pack,
        ) as guest:
            mp.until("guest joins", lambda: any(
                p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]
            ))
            host.commands((f"/gamemode survival {GUEST}", f"/tp {GUEST} 6.5 103 17.5"))
            mp.until("guest loads output depot", lambda: guest.call("block", 6, 103, 16)["block"] == "create:depot")
            mp.until("guest stands beside depot", lambda: guest.call("state")["player"]["position"] == [6.5, 103.0, 17.5])
            for _ in range(80):
                host.step_to(host.clock() + 1)
            output = slots(host, DEPOT)
            bonus = output.get(0, ("", 0))[1]
            assert 0 < bonus < 64 and output == {0: (BONUS, bonus)}, output
            pending = list(stacks(host.command(f"/data get block {BASIN} Overflow")))
            assert pending == [("minecraft:iron_nugget", 1), ("minecraft:copper_ingot", 1)], pending
            assert not slots(host, BASIN)
            assert number(host.command(f"/data get block {MIXER}"), "Running") == 0
            assert mp.count(guest, BONUS) == 0
            guest.call("look-at", 6.5, 103.4, 16.5)
            target = guest.call("looking-at")
            assert (target.get("block") or {}).get("pos") == [6, 103, 16], (target, guest.call("state")["player"])
            guest.call("mouse", "right", "click")
            mp.until("guest receives the rolled output", lambda: mp.count(guest, BONUS) == bonus)
            assert not slots(host, DEPOT)
            host.step_to(host.clock() + 1)
            assert slots(host, DEPOT) == {0: pending[0]}

        host.restart()
        assert slots(host, DEPOT) == {0: pending[0]} and not slots(host, BASIN)
        assert list(stacks(host.command(f"/data get block {BASIN} Overflow"))) == pending[1:]
        assert number(host.command(f"/data get block {MIXER}"), "Running") == 0
        print(f"Active Mixer resumed once; LAN guest collected {bonus}/64 bonus nuggets; "
              "idle reopen retained both guaranteed outputs in order.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    run(parser.parse_args())
