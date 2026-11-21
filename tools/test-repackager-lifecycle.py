#!/usr/bin/env python3
"""Check Repackager address/context retention, backpressure, reopen, and LAN use."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

orders = import_module("test-repackager-orders")
multiplayer = import_module("test-multiplayer")

BARREL = (7, 105, -12)
MACHINE = (8, 105, -12)
POWER = (8, 105, -11)
GUEST = "RepackagerGuest"
LAN_BARREL = (7, 105, -6)
LAN_MACHINE = (8, 105, -6)
LAN_POWER = (8, 105, -5)


def value(world, pos, path):
    return world.command(f"/data get block {' '.join(map(str, pos))} {path}").partition(
        " has the following block data: "
    )[2]


def prepare(world):
    world.commands((
        "/fill 5 104 -15 13 104 -9 minecraft:smooth_stone",
        "/fill 5 105 -15 13 109 -9 minecraft:air",
        f"/setblock {' '.join(map(str, BARREL))} minecraft:barrel",
        f"/setblock {' '.join(map(str, MACHINE))} create:repackager[facing=east]",
    ))


def pulse(world, pos):
    xyz = " ".join(map(str, pos))
    world.command(f"/setblock {xyz} minecraft:redstone_block")


def advance(world, ticks):
    for _ in range(ticks):
        world.step_to(world.clock() + 1)


def add_fragment(world, slot, order, fragment, final, item, address="Factory North", *, barrel=BARREL):
    xyz = " ".join(map(str, barrel))
    world.command(f"/item replace block {xyz} container.{slot} with create:cardboard_package_12x12")
    metadata = (f'{{order_id:{order},link_index:0,is_final_link:1b,'
                f'fragment_index:{fragment},is_final:{int(final)}b}}')
    world.command(f'/data modify block {xyz} Items[{slot}].components."create:package_order_data" set value {metadata}')
    world.command(f'/data modify block {xyz} Items[{slot}].components."create:package_address" set value "{address}"')
    contents = '[{slot:0,item:{id:"minecraft:' + item + '",count:2}}]'
    world.command(f'/data modify block {xyz} Items[{slot}].components."create:package_contents" set value {contents}')


def verify_address_and_queue(world):
    queue = "QueuedExitingPackages"
    state = orders.packager.block_data(world, MACHINE)
    if "QueuedExitingPackages: [{" in state:
        packet = f'{queue}[0].item_stack.components'
        assert int(value(world, MACHINE, f"{queue}[0].count")) == 1
    elif "HeldBox: {" in state:
        packet = "HeldBox.components"
    else:
        raise AssertionError(f"The Repackager lost its active output: {state}")
    assert value(world, MACHINE, f'{packet}."create:package_address"').strip('"') == "Factory North"
    contents = f'{packet}."create:package_contents"'
    assert value(world, MACHINE, f"{contents}[0].item.id").strip('"') == "minecraft:iron_ingot"
    assert int(value(world, MACHINE, f"{contents}[0].item.count")) == 2
    assert value(world, MACHINE, f'{packet}."create:package_order_data".order_id') == "77"
    assert value(world, MACHINE, f"{contents}[1].item.id").strip('"') == "minecraft:gold_ingot"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda v: Path(v).resolve())
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()

    with fixture_world(args, "RepackagerLifecycle", pack=args.pack,
                       artifact_dir=ROOT / ".local/app-2022-evidence") as host:
        prepare(host)
        # Idle save/reopen retains orientation, attachment, and an incomplete order fragment.
        add_fragment(host, 0, 77, 0, False, "iron_ingot")
        host.command("/save-all flush")
        host.restart()
        assert "facing=east" in host.call("block", *MACHINE)["state"]
        assert "minecraft:iron_ingot" in orders.packager.block_data(host, BARREL)

        # Incomplete input remains untouched. Completing the split order yields one package.
        pulse(host, POWER)
        assert "order_id: 77" in orders.packager.block_data(host, BARREL)
        host.command(f"/setblock {' '.join(map(str, POWER))} minecraft:air")
        advance(host, 41)
        add_fragment(host, 1, 77, 1, True, "gold_ingot")
        pulse(host, POWER)
        verify_address_and_queue(host)
        barrel = orders.packager.block_data(host, BARREL)
        assert "order_id: 77" not in barrel, barrel

        # A second complete order is blocked while the first output occupies the queue.
        add_fragment(host, 0, 88, 0, True, "redstone")
        host.command(f'/data modify block {" ".join(map(str, MACHINE))} ButtonCooldown set value 0')
        host.command(f"/setblock {' '.join(map(str, POWER))} minecraft:air")
        pulse(host, POWER)
        assert "order_id: 88" in orders.packager.block_data(host, BARREL)
        host.command("/save-all flush")
        host.restart()
        verify_address_and_queue(host)
        assert "order_id: 88" in orders.packager.block_data(host, BARREL)
        print("Repackager idle and queued state survived reopen; split order address/content were retained and queued output applied backpressure.", flush=True)

        # A LAN guest toggles a separate machine's redstone input.
        host.commands((f"/setblock {' '.join(map(str, LAN_BARREL))} minecraft:barrel",
                       f"/setblock {' '.join(map(str, LAN_MACHINE))} create:repackager[facing=east]",
                       f"/setblock {' '.join(map(str, LAN_POWER))} minecraft:lever[face=floor,facing=north]"))
        add_fragment(host, 0, 99, 0, False, "iron_ingot", barrel=LAN_BARREL)
        add_fragment(host, 1, 99, 1, True, "gold_ingot", barrel=LAN_BARREL)
        network = host.call("lan", "open", "0", "commands", "force")
        with TemporaryDirectory(prefix="hc-repackager-lan-") as scratch:
            with multiplayer.joined_client(args, Path(scratch), f"127.0.0.1:{network['port']}", GUEST,
                                           scenario="repackager-lan", artifact_dir=ROOT / ".local/app-2022-evidence") as guest:
                multiplayer.until("Repackager guest to join", lambda: any(
                    p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]))
                host.command(f"/gamemode survival {GUEST}")
                host.command(f"/tp {GUEST} 8.5 106 -5.5")
                host.step_to(host.clock() + 1)
                multiplayer.until("guest to teleport", lambda: (
                    guest.call("state")["player"]["position"][0] == 8.5
                    and guest.call("state")["player"]["position"][2] == -5.5
                ))
                multiplayer.until("guest to see Repackager", lambda: guest.call("block", *LAN_MACHINE)["state"].startswith("create:repackager"))
                guest.call("interact", *LAN_POWER)
                multiplayer.until("host to observe guest redstone pulse", lambda: (
                    "powered=true" in host.call("block", *LAN_MACHINE)["state"]
                ))
                assert "order_id: 99" not in orders.packager.block_data(host, LAN_BARREL)
                assert "QueuedExitingPackages:" in orders.packager.block_data(host, LAN_MACHINE)
        print("LAN guest toggled the Repackager input; host observed the consumed order and queued package.", flush=True)


if __name__ == "__main__":
    main()
