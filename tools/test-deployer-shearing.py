#!/usr/bin/env python3
"""Check Deployer shearing, rejected targets, tool wear, and active reopen."""

import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
DEPLOYER = (9, 97, 16)
SHEEP = (11.5, 97, 16.5)


def at(pos):
    return " ".join(map(str, pos))


def data(world, path=""):
    suffix = f" {path}" if path else ""
    return world.command(f"/data get block {at(DEPLOYER)}{suffix}")


def has_entity(world, predicate):
    return world.command(f"/execute if entity {predicate}") == "Test passed"


def damage(world):
    value = data(world, "Items")
    match = re.search(r"(?:Damage|minecraft:damage)[:=]\s*(\d+)", value)
    return int(match[1]) if match else 0


def setup(world, age=0, enchantment=False, sheared=False, load_tool=True):
    stack = (
        'minecraft:shears[minecraft:enchantments={"minecraft:unbreaking":3}]'
        if enchantment else "minecraft:shears"
    )
    world.commands((
        "/setblock 9 96 16 minecraft:smooth_stone",
        "/setblock 11 96 16 minecraft:smooth_stone",
        f"/setblock {at(DEPLOYER)} create:deployer[facing=east,axis_along_first=true]",
        "/setblock 9 96 16 create:creative_motor[facing=up]{ScrollValue:64}",
        "/setblock 9 98 16 minecraft:redstone_block",
        f"/summon minecraft:sheep {SHEEP[0]} {SHEEP[1]} {SHEEP[2]} "
        f"{{Age:{age},Sheared:{1 if sheared else 0}b}}",
        *((f"/item replace block {at(DEPLOYER)} container.0 with {stack}",) if load_tool else ()),
    ))
    world.command("/tick step 3")
    if load_tool:
        world.command("/setblock 9 98 16 minecraft:air")
        world.command("/tick step 1")


def item_count(text, item):
    match = re.search(rf'\bid: "{re.escape(item)}"[^\]]*?\b(?:Count|count): (\d+)', text)
    return int(match[1]) if match else 0


def wool_count(world):
    return sum(
        entry["item"]["count"]
        for entry in world.call("entities", 8, "minecraft:item")["entities"]
        if (entry.get("item") or {}).get("item") == "minecraft:white_wool"
    )


def run_case(args, name, age=0, *, enchantment=False, reopen=False,
             sheared=False, should_shear=True):
    with fixture_world(args, f"DeployerShearing{name}", pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        setup(world, age, enchantment, sheared)
        if reopen:
            state = data(world)
            if 'State: "EXPANDING"' not in state:
                raise RuntimeError(f"Deployer did not begin its active stroke before save: {state}")
            world.command("/save-all flush")
            world.restart()
        world.command("/tick step 30")
        sheared = has_entity(world, '@e[type=minecraft:sheep,limit=1,nbt={Sheared:1b}]')
        wool = has_entity(world, '@e[type=minecraft:item,nbt={Item:{id:"minecraft:white_wool"}}]')
        output = wool_count(world)
        wear = damage(world)
        if should_shear:
            if not sheared or not wool or not 1 <= output <= 3 or (wear != 1 and not enchantment):
                raise RuntimeError(f"{name}: expected one shearing, wool output and one tool wear; "
                                   f"sheared={sheared}, wool={output}, damage={wear}, deployer={data(world)}")
            if enchantment and wear not in (0, 1):
                raise RuntimeError(f"{name}: Unbreaking III produced invalid wear {wear}")
        elif sheared or wool or wear:
            raise RuntimeError(f"{name}: rejected sheep changed state or consumed shears; "
                               f"sheared={sheared}, wool={wool}, damage={wear}")
    return name


def run_guest_case(args):
    name = "DeployerShearingGuest"
    player = "ShearGuest"
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, name, pack=args.pack,
                                                   env={"HORIZON_NO_AUDIO": "1"}))
        setup(world, load_tool=False)
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-deployer-shear-")))
        guest = stack.enter_context(mp.joined_client(
            args, scratch, f"127.0.0.1:{port}", player, scenario="deployer-shearing-lan", pack=args.pack,
        ))
        mp.until("the guest to join", lambda: any(
            item["name"] == player and item["placed"] for item in world.call("lan", "status")["guests"]
        ))
        world.commands((
            f"/tp {player} 10.5 97 16.5",
            f"/gamemode survival {player}",
            f"/give {player} minecraft:shears 1",
        ))
        mp.until("the guest to receive shears", lambda: mp.count(guest, "minecraft:shears") == 1)
        guest.call("select", "minecraft:shears")
        guest.call("look-at", 9.5, 97.5, 16.5)
        guest.call("interact", *DEPLOYER, "east")
        mp.until("the guest's shears to enter the Deployer", lambda:
                 item_count(data(world, "Items"), "minecraft:shears") == 1
                 and mp.count(guest, "minecraft:shears") == 0)
        world.command("/setblock 9 98 16 minecraft:air")
        world.command("/tick step 31")
        if not has_entity(world, '@e[type=minecraft:sheep,limit=1,nbt={Sheared:1b}]'):
            raise RuntimeError("The host did not observe the guest-loaded Deployer shearing its sheep")
        if not has_entity(world, '@e[type=minecraft:item,nbt={Item:{id:"minecraft:white_wool"}}]'):
            raise RuntimeError("The host did not observe wool produced by the guest-loaded Deployer")
        if not 1 <= wool_count(world) <= 3:
            raise RuntimeError(f"The guest-loaded Deployer produced an invalid wool count: {wool_count(world)}")
        if damage(world) != 1:
            raise RuntimeError(f"The guest-loaded shears did not retain their one point of wear: {data(world)}")
        mp.until("the guest to observe the wool output", lambda: any(
            (entry.get("item") or {}).get("item") == "minecraft:white_wool"
            for entry in guest.call("entities", 8, "minecraft:item")["entities"]
        ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=lambda path: Path(path).resolve(strict=True),
                        default=ROOT / ".local/create.hmod")
    args = parser.parse_args()
    run_case(args, "AdultActiveReopen", reopen=True)
    run_case(args, "BabyReject", age=-24000, should_shear=False)
    run_case(args, "AlreadyShearedReject", sheared=True, should_shear=False)
    run_case(args, "Unbreaking", enchantment=True)
    run_guest_case(args)
    print("Adult, baby control, Unbreaking III, wool output, tool wear and active save/reopen passed.")


if __name__ == "__main__":
    main()
