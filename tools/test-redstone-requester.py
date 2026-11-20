#!/usr/bin/env python3
"""Replay Java Redstone Requester pulses through a linked Horizon Packager."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
packager = import_module("test-packager-redstone")
xyz = packager.xyz

STORAGE = (7, 105, -12)
MACHINE = (8, 105, -12)
LINK = (8, 106, -12)
REQUESTER = (7, 105, -8)
PULSE = (8, 105, -8)
COMPARATOR = (7, 105, -9)
FREQ = "[I;0,115,0,80]"
ITEM = "minecraft:iron_ingot"
BLOCK = "create:redstone_requester"
ADDRESS = "Smelting"


def order(count):
    items = f'{{item_stack:{{id:"{ITEM}",count:1}},count:{count}}}' if count else ""
    return "{ordered_stacks:{entries:[" + items + "]},ordered_crafts:[]}"


def configure(host, size, partial=False):
    command = (
        f'/data merge block {xyz(REQUESTER)} '
        f'{{Freq:{FREQ},EncodedAddress:"{ADDRESS}",AllowPartial:{int(partial)}b,EncodedRequest:{order(size)}}}'
    )
    host.command(command)


def pulse(host, on):
    block = "minecraft:redstone_block" if on else "minecraft:air"
    host.command(f"/setblock {xyz(PULSE)} {block}")


def prepared(host):
    host.commands((
        "/tp @s 9.5 105 -9.5",
        "/fill 5 104 -14 12 104 -7 minecraft:smooth_stone",
        f"/setblock {xyz(STORAGE)} minecraft:barrel",
        f"/item replace block {xyz(STORAGE)} container.0 with {ITEM} 6",
        f"/setblock {xyz(MACHINE)} create:packager[facing=east]",
        f"/setblock {xyz(LINK)} create:stock_link",
        f"/data merge block {xyz(LINK)} {{Freq:{FREQ}}}",
        f"/setblock {xyz(REQUESTER)} {BLOCK}",
        f"/setblock {xyz(COMPARATOR)} minecraft:comparator[facing=south]",
    ))
    configure(host, 8)


def quantity(data):
    return packager.number(data, "(?:[cC]ount)")


def states_match(peer, name, value):
    return peer.call("block", *name)["state"] == value


def replay(host, actor, rows):
    prepared(host)
    offset = host.clock() - 2
    for row in rows:
        tick = int(row["tick"])
        now = offset + tick
        host.step_to(now)
        if tick == 6:
            configure(host, 8, partial=True)
        if tick == 8:
            configure(host, 0, partial=True)
        if tick in range(4, 10):
            pulse(host, tick % 2 == 0)

        expected_state = f'{BLOCK}[axis=x,powered={row["powered"]}]'
        mp.until(f"the original Requester blockstate at tick {tick}",
                 lambda: states_match(host, REQUESTER, expected_state))
        succeeds = int(packager.block_value(host, REQUESTER, "Success").rstrip("b")) != 0
        assert succeeds == (row["success"] == "true"), (tick, succeeds, row)
        assert quantity(packager.block_value(host, STORAGE, "Items")) == int(row["stored_iron"]), (tick, row)
        nbt = packager.block_data(host, MACHINE)
        assert packager.number(nbt, "AnimationTicks") == int(row["animation"]), (tick, nbt, row)
        address, count = "_", 0
        if "HeldBox:" in nbt:
            address = packager.block_value(host, MACHINE, 'HeldBox.components."create:package_address"').strip('"')
            contents = packager.block_value(host, MACHINE, 'HeldBox.components."create:package_contents"')
            assert packager.string(contents, "id") == ITEM, (tick, contents)
            count = quantity(contents)
        assert (address, count) == (row["address"], int(row["packaged_iron"])), (tick, address, count, row)
        if actor is not host:
            mp.until(f"the Java Requester state to reach the guest at tick {tick}",
                     lambda: states_match(actor, REQUESTER, expected_state))
        assert host.clock() == now
        print(f"{tick} {row['powered']} {row['success']} {row['stored_iron']} {count} {address} {row['animation']}")


def verify_output(host, actor):
    host.command(f"/item replace block {xyz(STORAGE)} container.0 with {ITEM} 4")
    configure(host, 3)
    pulse(host, True)
    assert quantity(packager.block_value(host, STORAGE, "Items")) == 1
    queued = packager.block_value(host, MACHINE, "QueuedExitingPackages")
    assert ADDRESS in queued and "package_order_data" in queued, queued
    assert packager.number(queued, "link_index") == 0
    assert packager.number(queued, "is_final_link") == 1, queued
    for _ in range(2):
        host.step_to(host.clock() + 1)
    assert packager.block_value(host, COMPARATOR, "OutputSignal") == "15"
    mp.until("the powered comparator to reach the observer", lambda:
             "powered=true" in actor.call("block", *COMPARATOR)["state"])
    pulse(host, False)
    for _ in range(2):
        host.step_to(host.clock() + 1)
    assert packager.block_value(host, COMPARATOR, "OutputSignal") == "0"
    mp.until("the unpowered comparator to reach the observer", lambda:
             "powered=false" in actor.call("block", *COMPARATOR)["state"])
    print("A second order queued behind the held package and drove the real comparator 15 to 0.")

    animation = packager.number(packager.block_data(host, MACHINE), "AnimationTicks")
    for _ in range(animation):
        host.step_to(host.clock() + 1)
    feet = (9.5, 105, -9.5) if actor is host else (10.5, 105, -11.5)
    name = "@s" if actor is host else "RequesterGuest"
    host.command(f"/tp {name} {xyz(feet)}")
    mp.until("the actor to stand at the Packager", lambda:
             actor.call("state")["player"]["position"] == list(feet))
    if actor is host:
        actor.call("interact", *MACHINE, "south")
    else:
        host.command("/item replace entity RequesterGuest weapon.mainhand with minecraft:stick")
        mp.until("the guest to hold a Stick", lambda:
                 (actor.call("inventory")["held"] or {}).get("item") == "minecraft:stick")
        packager.click(host, actor)

    def received():
        slots = actor.call("inventory")
        return next((slot for slot in slots["hotbar"] + slots["main"]
                     if "create:package_order_data" in (slot.get("components") or "")), None)

    try:
        package = mp.until("the physical order to reach the acting player's inventory", received)
    except RuntimeError as error:
        raise AssertionError((actor.call("inventory"), packager.block_data(host, MACHINE))) from error
    metadata = package["components"]
    assert ADDRESS in metadata and "order_context" in metadata, metadata
    assert packager.number(metadata, "fragment_index") == 0, metadata
    assert packager.number(metadata, "is_final_link") == 0, metadata
    assert "HeldBox:" not in packager.block_data(host, MACHINE)
    host.step_to(host.clock() + 1)
    assert packager.number(packager.block_data(host, MACHINE), "AnimationTicks") == 20
    second = packager.block_value(host, MACHINE, 'HeldBox.components."create:package_contents"')
    assert quantity(second) == 3 and packager.string(second, "id") == ITEM, second
    print("The actor retrieved the first parcel with its order metadata, then the queued parcel began animating.")


def verify_sources(host, reopen=False):
    with (ROOT / "fixtures/stock-link-network-java.csv").open() as source:
        reference = {int(row["tick"]): row for row in csv.DictReader(source)}
    reserve = (7, 105, -15)
    other_network = (7, 105, -18)
    reverse_link = (6, 106, -12)
    host.commands((
        f"/item replace block {xyz(STORAGE)} container.0 with {ITEM} 12",
        f"/setblock 6 105 -12 create:packager[facing=west]",
        f"/setblock {xyz(reverse_link)} create:stock_link",
        f"/data merge block {xyz(reverse_link)} {{Freq:{FREQ}}}",
    ))
    for barrel, count, freq in ((reserve, 5, FREQ), (other_network, 9, "[I;0,91,0,27]")):
        x, y, z = barrel
        host.commands((
            f"/setblock {xyz(barrel)} minecraft:barrel",
            f"/item replace block {xyz(barrel)} container.0 with {ITEM} {count}",
            f"/setblock {x+1} {y} {z} create:packager[facing=east]",
            f"/setblock {x+1} {y+1} {z} create:stock_link",
            f"/data merge block {x+1} {y+1} {z} {{Freq:{freq}}}",
        ))
    host.step_to(host.clock() + 1)

    if reopen:
        # Save an idle but live network before any order changes its stock. The
        # reopened Requester must still see the same two eligible inventories;
        # the unrelated network remains excluded.
        host.restart()
        for pos, amount in ((STORAGE, 12), (reserve, 5), (other_network, 9)):
            assert quantity(packager.block_value(host, pos, "Items")) == amount, (pos, amount)
        for pos, frequency in ((LINK, FREQ), (reverse_link, FREQ),
                               ((8, 106, -15), FREQ), ((8, 106, -18), "[I;0,91,0,27]")):
            actual = "".join(packager.block_value(host, pos, "Freq").split())
            assert actual == "".join(frequency.split()), (pos, actual, frequency)
        configure(host, int(reference[4]["visible_iron"]) + 1)
        pulse(host, True)
        assert int(packager.block_value(host, REQUESTER, "Success").rstrip("b")) == 0
        pulse(host, False)
        print("Idle Stock Link networks, frequencies, inventory contents and eligibility survived host save/reopen.")

    def check_order(count, succeeds):
        configure(host, count)
        pulse(host, True)
        assert int(packager.block_value(host, REQUESTER, "Success").rstrip("b")) == int(succeeds)
        pulse(host, False)

    check_order(int(reference[4]["visible_iron"]) + 1, False)
    assert quantity(packager.block_value(host, STORAGE, "Items")) == 12
    x, y, z = reserve
    host.commands((
        f"/setblock {x+1} {y+2} {z} minecraft:redstone_block",
        f"/setblock {xyz(reverse_link)} minecraft:air",
    ))
    host.step_to(host.clock() + 1)
    host.step_to(host.clock() + 1)
    check_order(int(reference[6]["visible_iron"]) + 1, False)
    check_order(int(reference[8]["packaged_iron"]), True)
    assert quantity(packager.block_value(host, STORAGE, "Items")) == int(reference[8]["stored_iron"])
    assert quantity(packager.block_value(host, reserve, "Items")) == 5
    assert quantity(packager.block_value(host, other_network, "Items")) == 9

    # Reconnect the removed second link to the same inventory. It must restore
    # visibility without counting that Barrel twice.
    animation = packager.number(packager.block_data(host, MACHINE), "AnimationTicks")
    for _ in range(animation):
        host.step_to(host.clock() + 1)
    host.commands((
        f"/setblock {xyz(reverse_link)} create:stock_link",
        f"/data merge block {xyz(reverse_link)} {{Freq:{FREQ}}}",
        f"/item replace block {xyz(STORAGE)} container.0 with {ITEM} 12",
    ))
    host.step_to(host.clock() + 1)
    check_order(13, False)
    if reopen:
        host.restart()
        assert quantity(packager.block_value(host, STORAGE, "Items")) == 12
        actual_frequency = "".join(packager.block_value(host, reverse_link, "Freq").split())
        assert actual_frequency == "".join(FREQ.split()), actual_frequency
        configure(host, 13)
        pulse(host, True)
        assert int(packager.block_value(host, REQUESTER, "Success").rstrip("b")) == 0
        pulse(host, False)
        print("The reconnected, populated Stock Link network retained its single-inventory total after reopen.")
    check_order(12, True)
    assert quantity(packager.block_value(host, STORAGE, "Items")) == 0
    print("The Requester refused orders above Java stock totals, shipped from the eligible Barrel, and restored a removed link without double-counting its inventory.")


def verify_priority(host, actor):
    with (ROOT / "fixtures/stock-link-priority-java.csv").open() as source:
        row = next(csv.DictReader(source))
    lower = (22, 105, -12)
    lower_packager = (23, 105, -12)
    lower_link = (23, 106, -12)
    higher = (22, 105, -16)
    higher_packager = (23, 105, -16)
    higher_link = (23, 106, -16)
    requester = (22, 105, -20)
    pulse_at = (23, 105, -20)
    frequency = "[I;901,2,3,4]"
    host.commands((
        f"/setblock {xyz(lower)} minecraft:barrel",
        f"/item replace block {xyz(lower)} container.0 with {ITEM} 4",
        f"/setblock {xyz(lower_packager)} create:packager[facing=east]",
        f"/setblock {xyz(lower_link)} create:stock_link",
        f"/data merge block {xyz(lower_link)} {{Freq:{frequency}}}",
        "/setblock 23 107 -12 minecraft:target",
        f"/setblock 23 107 -12 minecraft:target[power={row['lower_power']}]",
        f"/setblock {xyz(higher)} minecraft:barrel",
        f"/item replace block {xyz(higher)} container.0 with {ITEM} 9",
        f"/setblock {xyz(higher_packager)} create:packager[facing=east]",
        f"/setblock {xyz(higher_link)} create:stock_link",
        f"/data merge block {xyz(higher_link)} {{Freq:{frequency}}}",
        "/setblock 23 107 -16 minecraft:target",
        f"/setblock 23 107 -16 minecraft:target[power={row['higher_power']}]",
        f"/setblock {xyz(requester)} {BLOCK}",
        f'/data merge block {xyz(requester)} {{Freq:{frequency},EncodedAddress:"Priority",AllowPartial:0b,EncodedRequest:{order(int(row["requested_iron"]))}}}',
    ))
    for _ in range(2):
        host.step_to(host.clock() + 1)
    actual_powers = tuple(int(packager.block_value(host, pos, "Power"))
                          for pos in (lower_link, higher_link))
    wanted_powers = (int(row["lower_power"]), int(row["higher_power"]))
    assert actual_powers == wanted_powers, (actual_powers, wanted_powers)
    host.command(f"/setblock {xyz(pulse_at)} minecraft:redstone_block")
    for _ in range(2):
        host.step_to(host.clock() + 1)
    accepted = int(packager.block_value(host, requester, "Success").rstrip("b")) != 0
    shipped = tuple(quantity(packager.block_value(host, pos, 'HeldBox.components."create:package_contents"'))
                    for pos in (lower_packager, higher_packager))
    remaining = tuple(quantity(packager.block_value(host, pos, "Items"))
                      for pos in (lower, higher))
    actual = (accepted, *actual_powers, sum(shipped), *shipped, *remaining)
    expected = (row["accepted"] == "true", *wanted_powers, int(row["requested_iron"]),
                int(row["shipped_from_lower_power"]), int(row["shipped_from_higher_power"]),
                int(row["lower_inventory_remaining"]), int(row["higher_inventory_remaining"]))
    assert actual == expected, (actual, expected)
    if actor is not host:
        host_state = host.call("block", *requester)["state"]
        mp.until("the priority Requester state to reach the LAN guest", lambda:
                 actor.call("block", *requester)["state"] == host_state)
        assert "powered=true" in host_state
    print(f"Stock Link priority matched Java: powers {actual_powers}, shipments {shipped}, remaining {remaining}.")


def run(args):
    with (ROOT / "fixtures/stock-link-requester-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    mode = "LAN" if args.lan else "Solo"
    with ExitStack() as resources:
        env = {"HORIZON_NO_AUDIO": "1"}
        host = resources.enter_context(fixture_world(args, f"StockRequester{mode}", pack=args.pack, env=env))
        actor = host
        if args.lan:
            name = "RequesterGuest"
            scratch = Path(resources.enter_context(TemporaryDirectory(prefix="hc-requester-")))
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            actor = resources.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, render=True, scenario="stock-requester",
                pack=args.pack, env=env,
            ))
            mp.until("the Requester guest to join", lambda: any(
                g["name"] == name and g["placed"] for g in host.call("lan", "status")["guests"]
            ))
            host.command(f"/tp {name} 9.5 105 -9.5")
        replay(host, actor, rows)
        verify_output(host, actor)
        verify_sources(host, reopen=actor is host)
        verify_priority(host, actor)
    print(f"{mode} matched {len(rows)} Java Requester snapshots.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    run(parser.parse_args())
