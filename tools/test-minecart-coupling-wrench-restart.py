#!/usr/bin/env python3
"""Check that wrenching a chain stays removed across an actual world restart."""
import argparse
import importlib.util
from tempfile import TemporaryDirectory
from pathlib import Path

from fixture_world import fixture_world

spec = importlib.util.spec_from_file_location("multiplayer", Path(__file__).with_name("test-multiplayer.py"))
multiplayer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multiplayer)
GUEST = "CouplingGuest"


def run(args):
    with fixture_world(args, "CouplingWrenchRestart", pack=args.pack, render=True) as world:
        world.commands((
            "/fill 4 169 20 18 169 28 minecraft:stone",
            "/fill 4 170 24 18 170 24 minecraft:rail[shape=east_west]",
            '/summon minecraft:minecart 8.5 170.0625 24.5 {UUID:[I;0,0,0,701],Tags:["chain_a"]}',
            '/summon minecraft:minecart 11.5 170.0625 24.5 {UUID:[I;0,0,0,702],Tags:["chain_b"]}',
            '/summon minecraft:minecart 14.5 170.0625 24.5 {UUID:[I;0,0,0,703],Tags:["chain_c"]}',
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:minecart_coupling 3",
            "/item replace entity @s hotbar.1 with create:wrench",
        ))

        def click(x):
            world.command(f"/tp @s {x} 170 22.5")
            world.call("look-at", x, 170.2, 24.5)
            world.call("wait", 4)
            world.call("mouse", "right", "click")
            world.call("wait", 3)

        def markers():
            return world.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]')

        world.call("select", "create:minecart_coupling")
        for x in (8.5, 11.5, 11.5, 14.5):
            click(x)
        if "Count: 2" not in markers():
            raise RuntimeError("Expected both chain links before wrench")
        if "count: 1" not in world.command("/data get entity @s Inventory"):
            raise RuntimeError("Expected one remaining coupling")

        world.call("select", "create:wrench")
        click(11.5)
        if "Test passed" in markers():
            raise RuntimeError("Wrench left a chain link")
        if "count: 3" not in world.command("/data get entity @s Inventory"):
            raise RuntimeError("Wrench did not return both couplings")

        world.restart()
        if "Test passed" in markers():
            raise RuntimeError("A removed link reappeared after restart")
        if "count: 3" not in world.command("/data get entity @s Inventory"):
            raise RuntimeError("Refund did not survive restart")
        for i, tag in enumerate(("chain_a", "chain_b", "chain_c"), 701):
            uuid = world.command(f"/data get entity @e[type=minecraft:minecart,tag={tag},limit=1] UUID")
            if f"[I; 0, 0, 0, {i}]" not in uuid:
                raise RuntimeError(f"Cart did not survive restart: {uuid}")

        world.call("select", "create:minecart_coupling")
        for x in (8.5, 11.5, 11.5, 14.5):
            click(x)
        if "Count: 2" not in markers():
            raise RuntimeError("Carts could not be coupled again after restart")
        if "count: 1" not in world.command("/data get entity @s Inventory"):
            raise RuntimeError("Re-coupling did not consume two couplings")
    print("Wrench removed both links and refunded them; restart kept carts unlinked and allowed re-coupling.")


def run_lan(args):
    with TemporaryDirectory(prefix="wr-", dir="/tmp") as scratch:
        with fixture_world(args, "CouplingWrenchRestartLan", pack=args.pack, render=False, env={"HORIZON_NO_AUDIO": "1", "SDL_AUDIODRIVER": "dummy"}) as world:
            world.commands((
                "/fill 4 169 20 18 169 28 minecraft:stone",
                "/fill 4 170 24 18 170 24 minecraft:rail[shape=east_west]",
                '/summon minecraft:minecart 8.5 170.0625 24.5 {UUID:[I;0,0,0,701],Tags:["chain_a"]}',
                '/summon minecraft:minecart 11.5 170.0625 24.5 {UUID:[I;0,0,0,702],Tags:["chain_b"]}',
                '/summon minecraft:minecart 14.5 170.0625 24.5 {UUID:[I;0,0,0,703],Tags:["chain_c"]}',
            ))

            def open_guest(stage):
                network = world.call("lan", "open", "0", "commands")
                return multiplayer.joined_client(
                    args, Path(scratch) / stage, f"127.0.0.1:{network['port']}", GUEST,
                    render=True, scenario="minecart-wrench-rejoin", pack=args.pack,
                    env={"HORIZON_NO_AUDIO": "1", "SDL_AUDIODRIVER": "dummy"},
                )

            def wait_join():
                multiplayer.until(
                    "guest to join",
                    lambda: any(p["name"] == GUEST and p["placed"] for p in world.call("lan", "status")["guests"]),
                )

            def click(guest, x):
                world.command(f"/tp {GUEST} {x} 170 22.5")
                multiplayer.until(
                    "guest to reach cart",
                    lambda: guest.call("state")["player"]["position"] == [x, 170.0, 22.5],
                )
                guest.call("look-at", x, 170.2, 24.5)
                guest.call("wait", 4)
                guest.call("mouse", "right", "click")
                guest.call("wait", 3)

            def markers():
                return world.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]')

            with open_guest("first") as guest:
                wait_join()
                world.commands((
                    f"/gamemode survival {GUEST}",
                    f"/item replace entity {GUEST} hotbar.0 with create:minecart_coupling 3",
                    f"/item replace entity {GUEST} hotbar.1 with create:wrench",
                ))
                multiplayer.until("guest supplies", lambda: multiplayer.count(guest, "create:minecart_coupling") == 3 and multiplayer.count(guest, "create:wrench") == 1)
                guest_uuid = world.command(f"/data get entity {GUEST} UUID")
                guest.call("select", "create:minecart_coupling")
                for x in (8.5, 11.5, 11.5, 14.5):
                    click(guest, x)
                multiplayer.until("two chain links", lambda: "Count: 2" in markers())
                multiplayer.until("one remaining coupling", lambda: multiplayer.count(guest, "create:minecart_coupling") == 1)
                guest.call("select", "create:wrench")
                click(guest, 11.5)
                multiplayer.until("both links removed", lambda: "Test passed" not in markers())
                multiplayer.until("two couplings refunded", lambda: multiplayer.count(guest, "create:minecart_coupling") == 3)

            world.restart()
            if "Test passed" in markers():
                raise RuntimeError("A removed link reappeared after restart")
            for i, tag in enumerate(("chain_a", "chain_b", "chain_c"), 701):
                uuid = world.command(f"/data get entity @e[type=minecraft:minecart,tag={tag},limit=1] UUID")
                if f"[I; 0, 0, 0, {i}]" not in uuid:
                    raise RuntimeError(f"Cart did not survive restart: {uuid}")

            with open_guest("rejoin") as guest:
                wait_join()
                if world.command(f"/data get entity {GUEST} UUID") != guest_uuid:
                    raise RuntimeError("Guest identity changed on rejoin")
                multiplayer.until("refunded couplings after rejoin", lambda: multiplayer.count(guest, "create:minecart_coupling") == 3)
                survival = world.command(f"/execute if entity @a[name={GUEST},gamemode=survival]")
                if "Test passed" not in survival:
                    if not args.restore_survival:
                        raise RuntimeError(f"Guest did not retain survival mode after restart: {survival}")
                    world.command(f"/gamemode survival {GUEST}")
                    multiplayer.until("guest survival restored", lambda: "Test passed" in world.command(f"/execute if entity @a[name={GUEST},gamemode=survival]"))
                guest.call("select", "create:minecart_coupling")
                for x in (8.5, 11.5, 11.5, 14.5):
                    click(guest, x)
                multiplayer.until("two links recreated", lambda: "Count: 2" in markers())
                try:
                    multiplayer.until("re-coupling consumed two", lambda: multiplayer.count(guest, "create:minecart_coupling") == 1)
                except RuntimeError as error:
                    host_inventory = world.command(f"/data get entity {GUEST} Inventory")
                    client_inventory = guest.call("inventory")
                    creative = world.command(f"/execute if entity @a[name={GUEST},gamemode=creative]")
                    survival = world.command(f"/execute if entity @a[name={GUEST},gamemode=survival]")
                    raise RuntimeError(f"Guest re-coupling inventory mismatch: host={host_inventory}; client={client_inventory}; creative={creative}; survival={survival}") from error
    mode_note = " with survival explicitly restored" if args.restore_survival else " in retained survival mode"
    print(f"Guest removed both links, rejoined after restart with the refund{mode_note}, and coupled the carts again.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--restore-survival", action="store_true", help="explicitly restore guest survival after rejoin for coupling isolation")
    args = parser.parse_args()
    run_lan(args) if args.lan else run(args)
