#!/usr/bin/env python3
"""Check guest sandpaper polishing, host observation, and inventory after LAN rejoin."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

mp = import_module("test-multiplayer")
snbt = import_module("test-train-schedule-entry").snbt
GUEST = "SandpaperGuest"
PAPER = "create:sand_paper"
RAW = "create:rose_quartz"
POLISHED = "create:polished_rose_quartz"


def wait_for_guest(host):
    mp.until("the sandpaper guest to join", lambda: any(
        player["name"] == GUEST and player["placed"]
        for player in host.call("lan", "status")["guests"]
    ))


def guest_inventory(guest):
    return guest.call("inventory")


def polished_state(guest):
    inventory = guest_inventory(guest)
    counts = inventory["counts"]
    paper = inventory["hotbar"][0]
    return (
        counts.get(RAW, 0), counts.get(POLISHED, 0), counts.get(PAPER, 0),
        paper.get("damage", 0),
    )


def assert_polished(guest, stage):
    try:
        mp.until(f"guest sandpaper result {stage}", lambda: polished_state(guest) == (1, 1, 1, 1))
    except RuntimeError as error:
        raise RuntimeError(f"{error}; observed inventory state: {polished_state(guest)}") from error


def host_inventory_state(host):
    response = host.command(f"/data get entity {GUEST} Inventory")
    raw = response.partition("entity data: ")[2]
    if not raw:
        return None, response
    stacks = snbt(raw)
    counts = {item: 0 for item in (RAW, POLISHED, PAPER)}
    damage = 0
    for stack in stacks:
        item = stack.get("id")
        if item not in counts:
            continue
        counts[item] += stack.get("count", stack.get("Count", 1))
        if item == PAPER:
            damage = stack.get("components", {}).get("minecraft:damage", 0)
    return (counts[RAW], counts[POLISHED], counts[PAPER], damage), response


def host_sees_result(host):
    try:
        mp.until("host inventory to converge on the guest result", lambda:
                 (state := host_inventory_state(host)[0]) == (1, 1, 1, 1))
    except RuntimeError as error:
        state, response = host_inventory_state(host)
        raise RuntimeError(f"Host inventory state {state} disagrees with guest's (1 raw, 1 polished, 1 paper, damage 1): {response}") from error


def run(args):
    with fixture_world(args, "SandpaperLAN", render=False, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as host:
        host.commands((
            "/fill 3 111 -10 9 111 -4 minecraft:smooth_stone",
            "/tp @s 15.5 112 -7.5",
        ))
        address = f"127.0.0.1:{host.call('lan', 'open', 0, 'commands', 'force')['port']}"
        host.command("/tick unfreeze")
        for stage, act in (("first", True), ("rejoin", False)):
            with TemporaryDirectory(prefix=f"hc-sandpaper-{stage}-") as tmp:
                scratch = Path(tmp)
                if act:
                    with mp.joined_client(
                        args, scratch, address, GUEST, render=False,
                        scenario="sandpaper-lan-first", pack=args.pack,
                        env={"HORIZON_NO_AUDIO": "1"},
                    ) as guest:
                        wait_for_guest(host)
                        host.commands((
                            f"/gamemode survival {GUEST}",
                            f"/tp {GUEST} 6.5 112 -7.5 90 -10",
                            f"/item replace entity {GUEST} hotbar.0 with {PAPER} 1",
                            f"/item replace entity {GUEST} weapon.offhand with {RAW} 2",
                        ))
                        mp.until("guest sandpaper supplies", lambda:
                                 mp.count(guest, PAPER) == 1 and mp.count(guest, RAW) == 2)
                        guest.call("select", PAPER)
                        guest.call("mouse", "right", "down")
                        mp.until("first polished output to reach the guest", lambda:
                                 mp.count(guest, POLISHED) == 1)
                        guest.call("mouse", "right", "up")
                        assert_polished(guest, "before disconnect")
                        host_sees_result(host)
                else:
                    with mp.joined_client(
                        args, scratch, address, GUEST, render=False,
                        scenario="sandpaper-lan-rejoin", pack=args.pack,
                        env={"HORIZON_NO_AUDIO": "1"},
                    ) as guest:
                        wait_for_guest(host)
                        assert_polished(guest, "after rejoin")
                        host_sees_result(host)
            if act:
                mp.until("the guest to disconnect from LAN", lambda: not any(
                    player["name"] == GUEST and player["placed"]
                    for player in host.call("lan", "status")["guests"]
                ))
    print("LAN guest polished Rose Quartz; the host saw the result, and item counts and Sand Paper wear survived rejoin.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())


if __name__ == "__main__":
    main()
