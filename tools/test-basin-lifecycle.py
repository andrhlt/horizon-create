#!/usr/bin/env python3
"""Check compacting basin guest input, interruption and save/reopen."""

import argparse
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
recipes = import_module("test-material-recipes")
stack_rows = import_module("test-brass-mixing").stacks
number = import_module("test-fluid-food").number

MOTOR = (4, 106, -11)
PRESS = (5, 106, -11)
BASIN = (5, 104, -11)
CHEST = (6, 103, -11)
GUEST = "BasinGuest"
INPUT = "minecraft:iron_ingot"
OUTPUT = "minecraft:iron_block"


def pos(position):
    return " ".join(map(str, position))


def state(host):
    press = host.command(f"/data get block {pos(PRESS)}")
    basin = host.command(f"/data get block {pos(BASIN)}")
    contents = recipes.inventory(basin)
    return press, basin, contents


def wait_until(host, predicate, description, limit=100):
    for _ in range(limit):
        if predicate():
            return
        host.step_to(host.clock() + 1)
    raise RuntimeError(f"Timed out waiting for {description}.")


def near_player(client, target, tolerance=0.75):
    position = client.call("state")["player"]["position"]
    return all(abs(actual - expected) <= tolerance for actual, expected in zip(position, target, strict=True))


def setup(host):
    chest_slots = ",".join(
        f'{{Slot:{slot}b,id:"minecraft:cobblestone",count:64}}' for slot in range(27)
    )
    host.commands((
        "/fill 2 103 -14 8 103 -8 minecraft:smooth_stone",
        "/fill 2 104 -14 8 111 -8 minecraft:air",
        "/setblock 4 106 -11 create:creative_motor[facing=east]",
        "/data merge block 4 106 -11 {ScrollValue:0}",
        "/setblock 5 106 -11 create:mechanical_press[facing=east]",
        "/setblock 5 104 -11 create:basin[facing=east]",
        "/setblock 6 103 -11 minecraft:chest",
        f"/data merge block 6 103 -11 {{Items:[{chest_slots}]}}",
    ))


@contextmanager
def join_guest(args, host, phase, *, render=False):
    port = host.call("lan", "open", 0, "commands", "force")["port"]
    with TemporaryDirectory(prefix=f"hc-basin-{phase}-") as scratch, mp.joined_client(
        args, Path(scratch), f"127.0.0.1:{port}", GUEST,
        render=render, scenario=f"basin-lifecycle-{phase}", pack=args.pack,
    ) as guest:
        mp.until("the Basin guest joins", lambda: any(
            player["name"] == GUEST and player["placed"]
            for player in host.call("lan", "status")["guests"]
        ))
        yield guest


def run(args):
    with fixture_world(args, "BasinLifecycle", pack=args.pack) as host:
        setup(host)
        with join_guest(args, host, "insert") as guest:
            host.command(f"/gamemode survival {GUEST}")
            host.command(f"/tp {GUEST} 5.5 105 -10.5")
            host.command(f"/give {GUEST} {INPUT} 9")
            mp.until("guest to receive nine iron ingots", lambda: mp.count(guest, INPUT) == 9)
            mp.until("guest to reach the Basin", lambda:
                     near_player(guest, (5.5, 105.0, -10.5)))
            guest.call("select", INPUT)
            guest.call("look-at", 5.5, 104.35, -10.5)
            host.step_to(host.clock() + 1)
            dropped = guest.call("drop", "all")
            assert dropped.get("dropped_from", {}).get("item") == INPUT, dropped
            assert dropped.get("held") is None, dropped

            def basin_has_input():
                return sum(count for item, count in recipes.inventory(
                    host.command(f"/data get block {pos(BASIN)}")
                ).values() if item == INPUT) == 9

            for _ in range(100):
                if basin_has_input():
                    break
                host.step_to(host.clock() + 1)
            else:
                try:
                    nearby_item = host.command(
                        "/execute positioned 5.5 105 -10.5 run data get entity "
                        "@e[type=minecraft:item,distance=..4,sort=nearest,limit=1] Pos"
                    )
                except RuntimeError as error:
                    nearby_item = str(error)
                server_inventory = host.command(f"/data get entity {GUEST} Inventory")
                raise RuntimeError(
                    f"Guest drop did not enter Basin; guest inventory={guest.call('inventory')}, "
                    f"server inventory={server_inventory}, nearby item position={nearby_item}, "
                    f"basin={host.command(f'/data get block {pos(BASIN)}')}"
                )
            press, _, contents = state(host)
            assert contents == {0: (INPUT, 9)}, (press, contents)

        # Idle input state is persisted before power is applied.
        host.restart()
        press, _, contents = state(host)
        assert contents == {0: (INPUT, 9)} and number(press, "Running") == 0, (press, contents)

        host.command(f"/data merge block {pos(MOTOR)} {{ScrollValue:128}}")
        wait_until(host, lambda: number(host.command(f"/data get block {pos(PRESS)}"), "Running") == 1,
                   "compacting to start")
        wait_until(host, lambda: number(host.command(f"/data get block {pos(PRESS)}"), "Ticks") >= 40,
                   "compacting to become active")
        active_press, _, active_contents = state(host)
        assert active_contents == {0: (INPUT, 9)}, (active_press, active_contents)

        # Stop the motor mid-cycle, save the active press, and confirm the
        # same input and operation resume after the world is reopened.
        host.command(f"/data merge block {pos(MOTOR)} {{ScrollValue:0}}")
        wait_until(host, lambda: number(host.command(f"/data get block {pos(PRESS)}"), "Speed") == 0,
                   "press speed to stop")
        stopped = host.command(f"/data get block {pos(PRESS)}")
        host.restart()
        reopened = host.command(f"/data get block {pos(PRESS)}")
        _, _, reopened_contents = state(host)
        assert (number(reopened, "Running"), number(reopened, "Ticks"), reopened_contents) == (
            1, number(stopped, "Ticks"), {0: (INPUT, 9)}
        ), (stopped, reopened, reopened_contents)

        host.command(f"/data merge block {pos(MOTOR)} {{ScrollValue:128}}")
        wait_until(host, lambda: number(host.command(f"/data get block {pos(PRESS)}"), "Running") == 0
                   and recipes.inventory(host.command(f"/data get block {pos(BASIN)}"))
                   .get(0, (None, 0))[0] != INPUT, "compacting to finish")
        overflow = host.command(f"/data get block {pos(BASIN)} Overflow")
        assert list(stack_rows(overflow)) == [(OUTPUT, 1)], overflow

        # Recover from a full output chest through a guest's real chest clicks.
        with join_guest(args, host, "extract", render=True) as guest:
            host.command(f"/gamemode survival {GUEST}")
            host.command(f"/tp {GUEST} 6.5 104 -10.5")
            mp.until("guest to reach the Basin output chest", lambda:
                     near_player(guest, (6.5, 104.0, -10.5))
                     and guest.call("block", *CHEST).get("block") == "minecraft:chest")
            guest.call("interact", *CHEST, "up")
            mp.until("guest to open the output chest", lambda: any(
                slot["slot"] == 300 and slot.get("stack")
                for slot in guest.call("menu").get("slots", [])
            ))
            guest.call("click-slot", "300", "shift")
            try:
                mp.until("guest to free chest output space", lambda:
                         sum(count for item, count in recipes.inventory(
                             host.command(f"/data get block {pos(CHEST)}")).values()
                         if item == "minecraft:cobblestone") == 26 * 64)
            except RuntimeError as error:
                raise RuntimeError(
                    f"{error}; guest inventory={guest.call('inventory')}, "
                    f"menu={guest.call('menu')}, chest={host.command(f'/data get block {pos(CHEST)} Items')}"
                ) from error
            wait_until(host, lambda: not list(stack_rows(
                host.command(f"/data get block {pos(BASIN)} Overflow")
            )), "Basin output to recover after chest space opens")
            chest_contents = recipes.inventory(host.command(f"/data get block {pos(CHEST)}"))
            output_slot = next(slot for slot, stack in chest_contents.items() if stack[0] == OUTPUT)
            guest.call("click-slot", str(300 + output_slot), "shift")
            mp.until("guest to collect the compacted iron block", lambda: mp.count(guest, OUTPUT) == 1)
            remaining = recipes.inventory(host.command(f"/data get block {pos(CHEST)} Items"))
            assert not any(item == OUTPUT for item, _ in remaining.values()), remaining

        host.restart()
        assert number(host.command(f"/data get block {pos(PRESS)}"), "Running") == 0
        assert not list(stack_rows(host.command(f"/data get block {pos(BASIN)} Overflow")))
        print("Guest Basin insertion, idle and interrupted active reopen, resumed compacting, and guest output extraction passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    run(parser.parse_args())
