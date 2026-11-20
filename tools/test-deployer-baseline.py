#!/usr/bin/env python3
"""Check Deployer controls, guest inventory, filters, and save/reopen."""

import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

mp = import_module("test-multiplayer")
DEPLOYER = (9, 97, 16)
ACTIVE_DEPLOYER = (9, 172, 16)


def at(pos):
    return " ".join(map(str, pos))


def data(world, key=None, pos=DEPLOYER):
    command = f"/data get block {at(pos)}"
    if key:
        command += f" {key}"
    return world.command(command)


def field(text, key):
    match = re.search(rf'\b{re.escape(key)}:\s*"?([A-Z_]+)', text)
    return match[1] if match else None


def item_count(text, item):
    for stack in re.findall(r"\{([^{}]*)\}", text):
        identity = re.search(r'\bid: "([\w:]+)"', stack)
        count = re.search(r"\b(?:Count|count): (\d+)", stack)
        if identity and identity[1] == item:
            return int(count[1]) if count else 1
    return 0


def interact(actor, face):
    actor.call("look-at", DEPLOYER[0] + .5, DEPLOYER[1] + .5, DEPLOYER[2] + .5)
    actor.call("interact", *DEPLOYER, face)


def controls(args, lan):
    mode = "LAN" if lan else "Solo"
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, f"DeployerBaseline{mode}", pack=args.pack,
                                                   env={"HORIZON_NO_AUDIO": "1"}))
        actor, player = host, "@s"
        if lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-deployer-baseline-")))
            player = "DeployerGuest"
            actor = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, scenario="deployer-baseline-lan", pack=args.pack,
            ))
            mp.until("the Deployer guest to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]
            ))
        host.commands((
            "/setblock 10 96 16 minecraft:smooth_stone",
            f"/setblock {at(DEPLOYER)} create:deployer[facing=east,axis_along_first=true]",
            f"/tp {player} 10.5 97 16.5",
            f"/gamemode survival {player}",
            f"/give {player} create:wrench 1",
        ))
        mp.until("the actor to hold a Wrench", lambda: mp.count(actor, "create:wrench") == 1)
        actor.call("wait", 3)
        actor.call("select", "create:wrench")
        interact(actor, "east")
        mp.until("the host to apply Deployer PUNCH mode", lambda: field(data(host), "Mode") == "PUNCH")
        deployer_state = actor.call("block", *DEPLOYER)["state"]
        assert deployer_state.startswith("create:deployer[") and "facing=east" in deployer_state, deployer_state
        interact(actor, "east")
        mp.until("the host to restore Deployer USE mode", lambda: field(data(host), "Mode") == "USE")
        assert mp.count(actor, "create:wrench") == 1, "Wrench use consumed the tool"

        host.command(f"/give {player} minecraft:iron_ingot 3")
        mp.until("the actor to receive three iron ingots", lambda: mp.count(actor, "minecraft:iron_ingot") == 3)
        actor.call("select", "minecraft:iron_ingot")
        interact(actor, "east")
        try:
            mp.until("the host to hold the guest's three iron ingots", lambda:
                     item_count(data(host, "Items"), "minecraft:iron_ingot") == 3)
        except RuntimeError as error:
            raise RuntimeError(f"{error}; deployer={data(host)} inventory={actor.call('inventory')}") from error
        assert mp.count(actor, "minecraft:iron_ingot") == 0, "Guest inventory kept a duplicate stack"
        interact(actor, "east")
        mp.until("the guest to recover the Deployer's held stack", lambda:
                 mp.count(actor, "minecraft:iron_ingot") == 3
                 and item_count(data(host, "Items"), "minecraft:iron_ingot") == 0)

        actor.call("select", "minecraft:iron_ingot")
        interact(actor, "north")
        mp.until("the host to store the Deployer filter sample", lambda:
                 item_count(data(host, "Filter"), "minecraft:iron_ingot") == 1)
        assert mp.count(actor, "minecraft:iron_ingot") == 3, "Ordinary filter samples should not be consumed"
        assert field(data(host), "Mode") == "USE"
    print(f"{mode}: Wrench mode, hand exchange, filter sample, and guest/host inventory convergence passed.")


def persistence(args):
    with fixture_world(args, "DeployerIdleReopen", pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        world.commands((
            f"/setblock {at(DEPLOYER)} create:deployer[facing=east,axis_along_first=true]",
            f"/data merge block {at(DEPLOYER)} {{Mode:\"PUNCH\",Filter:{{id:\"minecraft:iron_ingot\",count:1}}}}",
            f"/item replace block {at(DEPLOYER)} container.0 with create:brass_ingot 2",
        ))
        before = data(world)
        world.command("/save-all flush")
        world.restart()
        after = data(world)
        assert field(after, "Mode") == "PUNCH", (before, after)
        assert item_count(data(world, "Items"), "create:brass_ingot") == 2, (before, after)
        assert item_count(data(world, "Filter"), "minecraft:iron_ingot") == 1, (before, after)

    with fixture_world(args, "DeployerActiveReopen", pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        world.commands((
            f"/setblock {at(ACTIVE_DEPLOYER)} create:deployer[facing=east,axis_along_first=true]",
            f"/setblock 9 171 16 create:creative_motor[facing=up]{{ScrollValue:64}}",
            "/setblock 9 173 16 minecraft:redstone_block",
            f"/setblock 11 172 16 minecraft:stripped_acacia_log[axis=z]",
            f"/item replace block {at(ACTIVE_DEPLOYER)} container.0 with create:andesite_alloy 2",
        ))
        world.commands(("/tick step 3", "/setblock 9 173 16 minecraft:air"))
        world.clock()
        world.command("/tick step 1")
        active = data(world, pos=ACTIVE_DEPLOYER)
        assert field(active, "State") == "EXPANDING", active
        world.command(f"/data merge block {at(ACTIVE_DEPLOYER)} {{Timer:0}}")
        world.command("/save-all flush")
        world.restart()
        reopened = data(world, pos=ACTIVE_DEPLOYER)
        assert field(reopened, "State") in {"EXPANDING", "RETRACTING", "WAITING"}, (active, reopened)
        if world.call("block", 11, 172, 16)["block"] != "create:andesite_casing":
            world.command("/tick step 1")
        if world.call("block", 11, 172, 16)["block"] != "create:andesite_casing":
            raise RuntimeError(f"The active Deployer did not resume its casing application after reopening: {data(world, pos=ACTIVE_DEPLOYER)}")
        assert item_count(data(world, "Items", ACTIVE_DEPLOYER), "create:andesite_alloy") == 1, data(world, "Items", ACTIVE_DEPLOYER)
    print("Idle mode, filter and held item survived reopen; active application resumed and consumed once.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=None)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--persistence", action="store_true")
    args = parser.parse_args()
    args.ctl = args.ctl.resolve()
    args.client = args.client.resolve()
    args.resources = args.resources.resolve()
    if args.pack is not None:
        args.pack = args.pack.resolve()
    if args.persistence:
        persistence(args)
    else:
        controls(args, args.lan)


if __name__ == "__main__":
    main()
