#!/usr/bin/env python3
"""Read back the detector, its inventory pickup, and Java's original dropped filter."""

import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


POS = (8, 102, -9)
CENTER = (8.5, 102.5, -8.5)
FILTER = "create:filter"
WRENCH = "create:wrench"
DROPPED_FILTER = '@e[type=minecraft:item,nbt={Item:{id:"create:filter"}},limit=1]'
spec = spec_from_file_location("observer_filter", ROOT / "tools/test-smart-observer-filter.py")
observer = module_from_spec(spec)
spec.loader.exec_module(observer)
filters = observer.filters
editor = filters.editor


def drop_counts(host, detector):
    items = host.call("entities", 9, "minecraft:item")["entities"]
    filters = [data for data in items if data["item"]["item"] == FILTER]
    ordinary = sum(data["item"]["count"] for data in items if data["item"]["item"] == detector)
    stored = sum(data["item"]["count"] for data in filters)
    centered_ready = 0
    if stored:
        delay = host.command(f"/data get entity {DROPPED_FILTER} PickupDelay")
        if re.search(r"\b0s$", delay):
            centered_ready = sum(data["item"]["count"] for data in filters if tuple(data["pos"]) == CENTER)
    return stored, centered_ready, ordinary


def verify(args, scratch):
    with (ROOT / "fixtures/smart-observer-recovery-java.csv").open(newline="") as source:
        rows = list(csv.reader(source))
    assert len(rows) == 6
    with fixture_world(args, "SmartObserverRecovery", render=True, pack=args.pack) as host:
        filters.wrench.arena(host)
        with filters.actor_for(host, args, scratch) as (actor, name):
            host.commands((f"/gamemode survival {name}", f"/tp {name} 8.5 101 -11.5"))
            editor.wait_for(actor, "the observer recovery actor to arrive", lambda:
                actor.call("state")["player"]["position"][:3] == [8.5, 101., -11.5]
            )
            for lane, smart, special, wrench, selected, amount, held, drops, ready, block_drop, pickup, removed in rows:
                at = editor.xyz(POS)
                detector = observer.ID if smart == "true" else filters.ITEM
                state = observer.state("south", "wall") if smart == "true" else filters.wrench.state("south", "wall")
                sample = FILTER if special == "true" else "minecraft:stone"
                host.commands((
                    "/kill @e[type=minecraft:item]",
                    f"/clear {name}",
                    f"/setblock {at} {state}",
                ))
                filters.equip(host, actor, name, sample, 2)
                filters.aim(actor, POS, "north", True)
                tick = host.clock()
                actor.call("mouse", "right", "click")
                assert selected == "true"
                editor.wait_for(host, f"the stored sample at {lane}", lambda:
                    filters.filter_data(filters.read(host, POS)) == (sample, int(amount))
                )
                editor.wait_for(actor, f"the hand count after filter selection at {lane}", lambda:
                    actor.call("inventory")["counts"].get(sample) == int(held)
                )
                if wrench == "true":
                    filters.equip(host, actor, name, WRENCH)
                    actor.call("key", "shift", "down")
                    try:
                        filters.aim(actor, POS, "north", True)
                        actor.call("mouse", "right", "click")
                        editor.wait_for(host, "the Wrench to remove the detector", lambda:
                            host.call("block", *POS)["block"] == "minecraft:air"
                        )
                        editor.wait_for(actor, "the Wrench detector item to arrive", lambda:
                            actor.call("inventory")["counts"].get(detector, 0) == int(pickup)
                        )
                    finally:
                        actor.call("key", "shift", "up")
                else:
                    host.command(f"/setblock {at} minecraft:air destroy")
                assert host.clock() == tick
                assert (host.call("block", *POS)["block"] == "minecraft:air") == (removed == "true"), lane
                actual = drop_counts(host, detector)
                wanted = tuple(map(int, (drops, ready, block_drop)))
                assert actual == wanted, (lane, wanted, actual, host.call("entities", 9, "minecraft:item"))
    who = "Guest" if scratch else "Host"
    print(f"{who} matched all six Java detector filter recovery scenarios at the action tick.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ("ctl", "client", "resources"):
        parser.add_argument(parameter, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-obd-") as scratch:
            verify(args, Path(scratch))
    else:
        verify(args, None)


if __name__ == "__main__":
    main()
