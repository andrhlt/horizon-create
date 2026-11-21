#!/usr/bin/env python3
"""Check Tree Fertilizer results and player inventory after a cold reopen."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world
from importlib import import_module

mp = import_module("test-multiplayer")
ITEM = "create:tree_fertilizer"
SAPLING = (10, 170, 22)


def apply_from_guest(host, guest):
    host.commands((
        "/gamemode survival TreeGuest",
        "/fill 6 169 20 14 169 28 minecraft:dirt",
        "/fill 6 170 20 14 185 28 minecraft:air",
        "/setblock 10 170 22 minecraft:oak_sapling[stage=0]",
        f"/item replace entity TreeGuest hotbar.0 with {ITEM} 2",
        "/tp TreeGuest 10.5 170.0 25.5",
    ))
    mp.until("guest fertilizer delivery", lambda: mp.count(guest, ITEM) == 2)
    guest.call("select", ITEM)
    guest.call("look-at", 10.5, 170.35, 22.5)
    mp.until("guest sapling target", lambda:
             (guest.call("looking-at").get("block") or {}).get("pos") == list(SAPLING))
    guest.call("mouse", "right", "click")
    mp.until("oak growth on host", lambda:
             host.call("block", *SAPLING)["block"] == "minecraft:oak_log")
    mp.until("fertilizer count on guest", lambda: mp.count(guest, ITEM) == 1)
    result_before_save = block_volume(host)
    host.command("/save-all flush")
    return result_before_save


def block_volume(host):
    return {(x, y, z): state for x, y, z, state in
            host.call("blocks", 7, 170, 19, 13, 185, 27)["blocks"]}


def persisted_state(state):
    if "[" not in state:
        return state
    block, raw_properties = state[:-1].split("[", 1)
    properties = sorted(part for part in raw_properties.split(",")
                        if not part.startswith("distance="))
    return block + ("[" + ",".join(properties) + "]" if properties else "")


def verify_reopened(host, guest, result_before_save):
    tree = block_volume(host)
    logs = [(pos, state) for pos, state in tree.items() if state.startswith("minecraft:oak_log")]
    assert logs and host.call("block", *SAPLING)["block"] == "minecraft:oak_log", logs
    differences = [(pos, persisted_state(result_before_save[pos]), persisted_state(tree[pos]))
                   for pos in result_before_save.keys() | tree.keys()
                   if (pos not in result_before_save or pos not in tree
                       or persisted_state(result_before_save[pos]) != persisted_state(tree[pos]))]
    assert not differences, f"The grown tree changed across cold save/reopen: {differences[:12]}"
    assert mp.count(guest, ITEM) == 1, guest.call("inventory")
    host_inventory = host.command("/data get entity TreeGuest Inventory")
    assert f'count: 1' in host_inventory and ITEM in host_inventory, host_inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()

    with TemporaryDirectory(prefix="hc-tree-fertilizer-reopen-") as scratch:
        with fixture_world(args, "TreeFertilizerReopen", pack=args.pack,
                           env={"HORIZON_NO_AUDIO": "1"}) as host:
            network = host.call("lan", "open", 0, "commands", "force")
            with mp.joined_client(args, Path(scratch), f"127.0.0.1:{network['port']}",
                                  "TreeGuest", render=True, scenario="tree-fertilizer-reopen",
                                  pack=args.pack, env={"HORIZON_NO_AUDIO": "1"}) as guest:
                mp.until("guest to join", lambda: any(
                    player["name"] == "TreeGuest" and player["placed"]
                    for player in host.call("lan", "status")["guests"]))
                result_before_save = apply_from_guest(host, guest)
            host.restart()
            network = host.call("lan", "open", 0, "commands", "force")
            with mp.joined_client(args, Path(scratch), f"127.0.0.1:{network['port']}",
                                  "TreeGuest", render=True, scenario="tree-fertilizer-reopen-again",
                                  pack=args.pack, env={"HORIZON_NO_AUDIO": "1"}) as guest:
                mp.until("rejoined guest to appear", lambda: any(
                    player["name"] == "TreeGuest" and player["placed"]
                    for player in host.call("lan", "status")["guests"]))
                verify_reopened(host, guest, result_before_save)

    print("Guest-grown oak and the remaining fertilizer survived host save/reopen and guest rejoin.")


if __name__ == "__main__":
    main()
