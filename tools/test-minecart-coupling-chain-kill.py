#!/usr/bin/env python3
"""Command-kill the middle cart of a coupled chain and compare Java lifecycle facts."""
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
            '/summon minecraft:minecart 8.5 170.0625 24.5 {UUID:[I;0,0,0,1501],Tags:["chain_a"]}',
            '/summon minecraft:minecart 11.5 170.0625 24.5 {UUID:[I;0,0,0,1502],Tags:["chain_b"]}',
            '/summon minecraft:minecart 14.5 170.0625 24.5 {UUID:[I;0,0,0,1503],Tags:["chain_c"]}',
        ))
        positions = ((8.5, 24.5), (11.5, 24.5), (11.5, 24.5), (14.5, 24.5))
        with chain.player_chain(world, args, positions) as player:
            def present(selector):
                return world.command(f"/execute if entity {selector}")

            markers = '@e[type=minecraft:marker,tag=create_minecart_coupling]'
            middle = '@e[type=minecraft:minecart,tag=chain_b]'
            drops = '@e[type=minecraft:item,nbt={Item:{id:"create:minecart_coupling"}}]'
            if "Count: 2" not in present(markers):
                raise RuntimeError("Expected two links before destruction")
            target = chain.GUEST if args.lan else "@s"
            def step(count):
                for _ in range(count):
                    world.step_to(world.clock() + 1)

            result = world.command(f"/kill {middle}")
            print(f"Command kill: {result}", flush=True)
            if "Test passed" in present(middle):
                raise RuntimeError("Command did not kill the middle cart")

            link_result = present(markers)
            drop_result = present(drops)
            print(f"After destruction: links={link_result}; coupling drops={drop_result}", flush=True)
            if "Test passed" in link_result:
                raise RuntimeError(f"Surviving links remained after middle cart destruction: {link_result}; drops={drop_result}")
            if "Count: 2" not in drop_result:
                raise RuntimeError(f"Expected two coupling drops: {drop_result}")
            for tag in ("chain_a", "chain_c"):
                if "Test passed" not in present(f'@e[type=minecraft:minecart,tag={tag}]'):
                    raise RuntimeError(f"Surviving cart missing: {tag}")

            step(25)
            for x in (10.0, 13.0):
                world.command(f"/tp {target} {x} 170 24.5")
                step(2)
            inventory = player.call("inventory")
            count = inventory["counts"].get("create:minecart_coupling", 0)
            if count != 3:
                raise RuntimeError(f"Expected one held coupling plus two picked-up drops: {inventory}")
    print(f"Middle-cart command kill removed both links and two drops were collected ({'guest LAN' if args.lan else 'solo'}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--lan", action="store_true")
    run(parser.parse_args())
