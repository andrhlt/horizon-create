#!/usr/bin/env python3
"""Prime and detonate a coupled TNT cart, checking the Java link lifecycle."""
import argparse
import importlib.util
from pathlib import Path

from fixture_world import fixture_world

spec = importlib.util.spec_from_file_location(
    "chain_curve", Path(__file__).with_name("test-minecart-coupling-chain-curve.py")
)
chain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chain)


def run(args):
    with fixture_world(args, "MinecartChainDestroy", pack=args.pack, render=not args.lan,
                       env={"HORIZON_NO_AUDIO": "1", "SDL_AUDIODRIVER": "dummy"}) as world:
        world.commands((
            "/fill 4 169 20 18 169 28 minecraft:stone",
            "/fill 4 170 24 18 170 24 minecraft:rail[shape=east_west]",
            '/summon minecraft:minecart 8.5 170.0625 24.5 {UUID:[I;0,0,0,1501],Tags:["chain_a"],Invulnerable:1b}',
            '/summon minecraft:tnt_minecart 11.5 170.0625 24.5 {UUID:[I;0,0,0,1502],Tags:["chain_b"]}',
            '/summon minecraft:minecart 14.5 170.0625 24.5 {UUID:[I;0,0,0,1503],Tags:["chain_c"],Invulnerable:1b}',
        ))
        positions = ((8.5, 24.5), (11.5, 24.5), (11.5, 24.5), (14.5, 24.5))
        with chain.player_chain(world, args, positions) as player:
            def present(selector):
                return world.command(f"/execute if entity {selector}")

            markers = '@e[type=minecraft:marker,tag=create_minecart_coupling]'
            middle = '@e[type=minecraft:tnt_minecart,tag=chain_b]'
            drops = '@e[type=minecraft:item,nbt={Item:{id:"create:minecart_coupling"}}]'
            if "Count: 2" not in present(markers):
                raise RuntimeError("Expected two links before destruction")
            target = chain.GUEST if args.lan else "@s"
            def step(count):
                for _ in range(count):
                    world.step_to(world.clock() + 1)

            world.command(f"/item replace entity {target} hotbar.1 with minecraft:flint_and_steel")
            if args.lan:
                chain.multiplayer.until("guest lighter", lambda: chain.multiplayer.count(player, "minecraft:flint_and_steel") == 1)
            player.call("select", "minecraft:flint_and_steel")
            world.command(f"/tp {target} 11.5 170 22.5")
            if args.lan:
                chain.multiplayer.until("guest near cart", lambda: player.call("state")["player"]["position"] == [11.5, 170.0, 22.5])
            player.call("look-at", 11.5, 170.2, 24.5)
            player.call("wait", 4)
            player.call("mouse", "right", "click")
            player.call("wait", 3)
            step(1)
            print(f"After priming: middle={present(middle)}; links={present(markers)}", flush=True)
            if "Test passed" not in present(middle) or "Count: 2" not in present(markers):
                raise RuntimeError("Priming must retain the middle cart and both links")
            world.commands(("/fill 10 170 22 10 173 26 minecraft:obsidian", "/fill 13 170 22 13 173 26 minecraft:obsidian"))
            world.command(f"/tp {target} 4.5 170 20.5")
            step(84)
            if "Test passed" in present(middle):
                raise RuntimeError("TNT cart failed to detonate")

            link_result = present(markers)
            drop_result = present(drops)
            print(f"After destruction: links={link_result}; coupling drops={drop_result}", flush=True)
            for tag in ("chain_a", "chain_c"):
                print(f"Endpoint {tag}: {present(f'@e[type=minecraft:minecart,tag={tag}]')}", flush=True)
            print(f"Coupling item: {world.command(f'/data get entity {drops[:-1]},limit=1]')}", flush=True)
            if "Test passed" in link_result:
                raise RuntimeError(f"Surviving links remained after middle cart destruction: {link_result}; drops={drop_result}")
            if "Count: 2" not in drop_result:
                raise RuntimeError(f"Expected two coupling drops: {drop_result}")
            for tag in ("chain_a", "chain_c"):
                if "Test passed" not in present(f'@e[type=minecraft:minecart,tag={tag}]'):
                    raise RuntimeError(f"Surviving cart missing: {tag}")

            step(20)
            for _ in range(2):
                result = world.command(f"/execute as {drops[:-1]},limit=1] at @s run tp {chain.GUEST if args.lan else '@p'} ~ ~ ~")
                print(f"Approach drop: {result}", flush=True)
                step(3)
            if args.lan:
                chain.multiplayer.until("guest collected couplings", lambda: chain.multiplayer.count(player, "create:minecart_coupling") == 3)
            count = player.call("inventory")["counts"].get("create:minecart_coupling", 0)
            print(f"After pickup: inventory={count}; drops={present(drops)}", flush=True)
            if count != 3 or "Test passed" in present(drops):
                raise RuntimeError("Expected both post-blast coupling drops to be collected")
    print(f"TNT detonation drops collected ({'guest LAN' if args.lan else 'solo'}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--lan", action="store_true")
    run(parser.parse_args())
