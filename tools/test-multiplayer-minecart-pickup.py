#!/usr/bin/env python3
"""A survival LAN guest picks up and redeploys a mounted minecart."""
import argparse
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

spec = importlib.util.spec_from_file_location("multiplayer", Path(__file__).with_name("test-multiplayer.py"))
multiplayer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multiplayer)
GUEST = "CartGuest"


def run(args, scratch):
    with fixture_world(args, "MinecartGuest", pack=args.pack) as host:
        host.commands((
            "/fill 4 169 20 16 169 28 minecraft:stone",
            "/setblock 8 170 24 create:cart_assembler[shape=east_west,rail_type=regular]",
            "/setblock 8 171 24 minecraft:stone",
            "/setblock 8 170 25 minecraft:redstone_block",
            "/setblock 10 170 24 minecraft:rail[shape=north_south]",
            "/setblock 12 170 24 minecraft:rail[shape=north_south]",
            "/setblock 14 170 24 create:cart_assembler[shape=east_west,rail_type=regular]",
            '/summon minecraft:minecart 8.5 170.0625 24.5 {Tags:["guest_cart"]}',
        ))
        for _ in range(30):
            host.step_to(host.clock() + 1)
            payload = host.command("/data get entity @e[type=minecraft:marker,tag=create_cart_payload,limit=1] CreateCartPayload")
            if "create:minecart_anchor" in payload:
                break
        else:
            raise RuntimeError(f"Cart did not assemble on the host: {payload}")
        host.command('/tp @e[type=minecraft:minecart,tag=guest_cart,limit=1] 10.5 170.0625 24.5')
        for _ in range(8):
            host.step_to(host.clock() + 1)
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(args, scratch, address, GUEST, render=True,
                                       scenario="multiplayer-minecart-pickup", pack=args.pack) as guest:
            multiplayer.until("the LAN guest to join", lambda: any(
                p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]))
            host.commands((f"/gamemode survival {GUEST}", f"/item replace entity {GUEST} hotbar.0 with create:wrench",
                           f"/tp {GUEST} 10.5 170 22.5"))
            multiplayer.until("the guest to hold the Wrench", lambda: multiplayer.count(guest, "create:wrench") == 1)
            multiplayer.until("the guest to reach the cart", lambda: guest.call("state")["player"]["position"] == [10.5, 170.0, 22.5])
            guest.call("select", "create:wrench")
            guest.call("look-at", 10.5, 170.2, 24.5)
            guest.call("wait", 4)
            guest.call("mouse", "right", "click")
            multiplayer.until("the guest's portable Minecart Contraption", lambda: multiplayer.count(guest, "create:minecart_contraption") == 1)
            inventory = host.command(f"/data get entity {GUEST} Inventory")
            for expected in ('create:minecart_contraption_data', 'minecraft:stone', 'Anchor: [I; 8, 170, 24]', 'InitialOrientation: "WEST"'):
                if expected not in inventory:
                    raise RuntimeError(f"Host did not preserve {expected}: {inventory}")
            cart = host.command('/execute if entity @e[type=minecraft:minecart,tag=guest_cart]')
            if "Test passed" in cart:
                raise RuntimeError(f"Host still has the picked-up cart: {cart}")
            guest.call("select", "create:minecart_contraption")
            host.command(f"/tp {GUEST} 12.5 170 21.5")
            multiplayer.until("the guest at the destination rail", lambda: guest.call("state")["player"]["position"] == [12.5, 170.0, 21.5])
            guest.call("look-at", 12.5, 170.05, 24.5)
            guest.call("wait", 4)
            guest.call("mouse", "right", "click")
            multiplayer.until("the portable item to be consumed", lambda: multiplayer.count(guest, "create:minecart_contraption") == 0)
            for _ in range(8):
                host.step_to(host.clock() + 1)
            payload = host.command("/data get entity @e[type=minecraft:marker,tag=create_cart_payload,limit=1] CreateCartPayload")
            if 'Anchor: [I; 8, 170, 24]' not in payload or 'InitialOrientation: "WEST"' not in payload or 'minecraft:stone' not in payload:
                raise RuntimeError(f"Host did not restore the mounted payload: {payload}")
            # Move the cart to the unpowered assembler to verify server disassembly.
            host.command('/tp @e[type=minecraft:minecart,limit=1] 14.5 170.0625 24.5')
            for _ in range(30):
                host.step_to(host.clock() + 1)
                if host.call("block", 14, 171, 24)["block"] == "minecraft:stone":
                    break
            else:
                raise RuntimeError("The guest-deployed payload did not disassemble on the host")
            if host.call("block", 14, 170, 24)["block"] != "create:cart_assembler":
                raise RuntimeError("Disassembly replaced the host's assembler")
    print("A survival LAN guest picked up and redeployed the stone contraption; the host preserved its anchor and restored the stone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    with TemporaryDirectory(prefix="hc-cart-guest-") as scratch:
        run(parser.parse_args(), Path(scratch))
