#!/usr/bin/env python3
"""Check mounted dispenser LAN visibility and idle/active save conservation."""
import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
import re

from fixture_world import fixture_world

mp = import_module("test-multiplayer")
TEMPLATE = Path("gametest/contraptions/arrow_dispenser.nbt")
ARROWS = "minecraft:arrow"
LEVER = "/setblock 5 98 -11 minecraft:lever[face=wall,facing=north,powered={}]"
ARTIFACTS = Path(__file__).resolve().parents[1] / ".local/app-2008-dispenser-fix"


def count_arrows(client):
    try:
        reply = client.command("/execute if entity @e[type=minecraft:arrow,x=3,y=100,z=-12,dx=4,dy=0,dz=4]")
        return int("Test passed" in reply)
    except (KeyError, RuntimeError):
        return len(client.call("entities", 100, ARROWS)["entities"])


def ammo(host):
    replies = host.commands((
        "/data get block 5 100 -10 Items",
        "/data get block 5 99 -10 MovedBlocks[0].VanillaEntity.Items",
    ))
    return sum(int(value) for reply in replies for value in re.findall(r"(?:Count|count): (\d+)", reply))


def wait_guest(host, name):
    mp.until("the LAN guest to join", lambda: any(
        item["name"] == name and item["placed"] for item in host.call("lan", "status")["guests"]))


def step_ticks(host, count):
    for _ in range(count):
        host.step_to(host.clock() + 1)


def count_items(client):
    return len(client.call("entities", 100, "minecraft:item")["entities"])


def dropper_stack(host):
    replies = host.commands((
        "/data get block 5 100 -10 Items",
        "/data get block 5 99 -10 MovedBlocks[0].VanillaEntity.Items",
    ))
    return sum(int(value) for reply in replies for value in re.findall(r"(?:Count|count): (\d+)", reply)
               if "cobblestone" in reply)


def gantry_data(host):
    try:
        return host.command("/data get entity @e[type=marker,tag=create_gantry_payload,limit=1] CreateGantry.Blocks")
    except RuntimeError:
        return ""


def run_dropper(args):
    with TemporaryDirectory(prefix="hc-mounted-dropper-") as raw:
        scratch = Path(raw)
        with ExitStack() as stack:
            host = stack.enter_context(fixture_world(args, "mounted-dropper-gates", TEMPLATE, pack=args.pack,
                                                     artifact_dir=ARTIFACTS))
            name = "DropperGuest"
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            guest = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, scenario="mounted-dropper-gates",
                artifact_dir=ARTIFACTS))
            wait_guest(host, name)
            host.commands((
                "/tp @s 5.5 99 -9.5", f"/tp {name} 5.5 99 -9.5",
                "/place template create:gametest/contraptions/arrow_dispenser 3 96 -12",
                LEVER.format("false"),
            ))
            mp.until("the guest to receive the mounted Dropper", lambda:
                     guest.call("block", 5, 99, -10).get("state", "") != "minecraft:air")
            step_ticks(host, 1)
            host.commands((
                "/data modify block 5 99 -10 MovedBlocks[0].BlockState.Name set value \"minecraft:dropper\"",
                "/data modify block 5 99 -10 MovedBlocks[0].BlockState.Properties.facing set value \"up\"",
                "/data modify block 5 99 -10 MovedBlocks[0].VanillaEntity.Items set value [{count:1,Slot:0b,id:\"minecraft:cobblestone\"}]",
                "/data remove block 5 99 -10 MovedBlocks[0].DispenseStarted",
                "/fill 3 101 -13 8 105 -6 minecraft:air",
            ))
            if args.diagnose:
                print("DIAGNOSTIC bearing Dropper payload:", host.command("/data get block 5 99 -10 MovedBlocks[0]"))
            before = count_items(host)
            before_stack = dropper_stack(host)
            for _ in range(200):
                step_ticks(host, 1)
                if dropper_stack(host) < before_stack:
                    break
            after = count_items(host)
            if dropper_stack(host) >= before_stack:
                raise RuntimeError(f"Mounted Dropper did not decrement its stack: before={before_stack}, after={dropper_stack(host)}")
            guest.call("screenshot", "/private/tmp/app2008-guest-mounted-dropper.png")
            try:
                mp.until("the guest Dropper item to converge", lambda: count_items(guest) >= 1)
            except RuntimeError as error:
                if not args.diagnose:
                    raise RuntimeError(f"{error}; guest_state={guest.call('state')}") from error
                print(f"DIAGNOSTIC guest Dropper replication: {error}")
    print("Mounted Dropper host ejection completed; guest convergence recorded.")


def run(args):
    with TemporaryDirectory(prefix="hc-mounted-dispenser-") as raw:
        scratch = Path(raw)
        with ExitStack() as stack:
            host = stack.enter_context(fixture_world(args, "mounted-dispenser-gates", TEMPLATE, pack=args.pack,
                                                     artifact_dir=ARTIFACTS))
            guest_name = "DispenserGuest"
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            guest = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", guest_name,
                scenario="mounted-dispenser-gates", render=True, artifact_dir=ARTIFACTS))
            wait_guest(host, guest_name)
            host.commands((
                f"/tp @s 5.5 99 -9.5",
                f"/tp {guest_name} 5.5 99 -9.5",
                "/place template create:gametest/contraptions/arrow_dispenser 3 96 -12",
                LEVER.format("true"),
            ))
            host.command("/summon minecraft:arrow 5.5 100 -10 {NoGravity:1b}")
            guest.call("look-at", 5.5, 100, -10)
            if args.diagnose:
                print("DIAGNOSTIC vanilla arrow target:", guest.call("looking-at"))
            guest.call("screenshot", "/private/tmp/app2008-guest-vanilla-arrow.png")
            host.command("/kill @e[type=minecraft:arrow,x=5,y=99,z=-11,dx=1,dy=2,dz=1]")
            mp.until("the LAN guest to receive the mounted dispenser rig", lambda:
                     guest.call("block", 5, 99, -10).get("state", "") != "minecraft:air")

            idle_total = ammo(host) + count_arrows(host)
            guest.call("quit")
            mp.until("the guest to disconnect", lambda: not guest.socket.exists())
            host.command("/save-all")
            host.restart()
            idle_after = ammo(host) + count_arrows(host)
            if idle_after != idle_total:
                raise RuntimeError(f"Idle reopen changed conserved items: {idle_total} -> {idle_after}")

            port = host.call("lan", "open", "0", "commands", "force")["port"]
            guest = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", guest_name,
                scenario="mounted-dispenser-gates-reopen", render=True, artifact_dir=ARTIFACTS))
            wait_guest(host, guest_name)
            host.command(LEVER.format("false"))
            before = count_arrows(host)
            initial_ammo = ammo(host)
            after = before
            for _ in range(12):
                step_ticks(host, 1)
                after = count_arrows(host)
                if after > before:
                    break
            if after <= before or ammo(host) >= initial_ammo:
                raise RuntimeError(f"Active mounted dispenser did not launch a projectile: before={before}, after={after}, ammo={ammo(host)}")
            guest.call("look-at", 5.5, 100, -10.7)
            if args.diagnose:
                print("DIAGNOSTIC mounted arrow target:", guest.call("looking-at"))
            guest.call("screenshot", "/private/tmp/app2008-guest-mounted-arrow.png")
            try:
                guest_arrows = mp.until("the guest projectile state to converge",
                                        lambda: count_arrows(guest) == after)
            except RuntimeError as error:
                if not args.diagnose:
                    raise RuntimeError(f"{error}; guest_state={guest.call('state')}") from error
                print(f"DIAGNOSTIC guest projectile replication: {error}; state={guest.call('state')}")
                guest_arrows = 0
            active_total = initial_ammo + before
            guest.call("quit")
            mp.until("the guest to disconnect after active launch", lambda: not guest.socket.exists())
            host.command("/save-all")
            host.restart()
            reopened = ammo(host) + count_arrows(host)
            if reopened != active_total:
                raise RuntimeError(f"Active reopen duplicated/lost items: {active_total} -> {reopened}")
            reopened_ammo = ammo(host)
            step_ticks(host, 20)
            settled_ammo = ammo(host)
            launched_after_reopen = reopened_ammo - settled_ammo
            settled = settled_ammo + 1 + launched_after_reopen
            if settled != active_total:
                raise RuntimeError(f"Post-reopen action duplicated/lost items: conserved={active_total}, observed={settled}")
    run_dropper(args)
    print("Mounted dispenser idle/active conservation and mounted Dropper action completed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True),
                        default=Path(__file__).resolve().parents[1] / ".local/create.hmod")
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--dropper-only", action="store_true")
    parsed = parser.parse_args()
    run_dropper(parsed) if parsed.dropper_only else run(parsed)
