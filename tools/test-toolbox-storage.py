#!/usr/bin/env python3
"""Replay Toolbox placement, block recoloring, and selected Java storage cases."""

import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

toolbox = import_module("test-toolbox-crafting")
postbox = import_module("test-postbox")
block_value = postbox.packager.block_value
xyz = postbox.packager.xyz
POS = (12, 100, -9)
HOPPER = (12, 101, -9)
COMPARATOR = (13, 100, -9)
BROWN = "create:brown_toolbox"
SAMPLES = 8


def exact_state(block, facing, wet):
    return f"{block}[facing={facing},waterlogged={wet}]"


def placement(host):
    x, y, z = POS
    look_from = {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}
    for row in toolbox.reference("placement"):
        dx, dz = look_from[int(row["yaw"])]
        feet = (x + 0.5 + dx * 2, y, z + 0.5 + dz * 2)
        fluid = "water" if row["wet"] == "true" else "air"
        host.commands((
            f"/setblock {xyz(POS)} minecraft:{fluid}",
            f"/item replace entity @s hotbar.2 with {BROWN}",
            f"/tp @s {xyz(feet)}",
        ))
        host.call("select", BROWN)
        host.call("look-at", x + 0.5, y, z + 0.5)
        host.call("wait", 3)
        host.call("interact", x, y - 1, z, "up")
        expected = exact_state(BROWN, row["facing"], row["wet"])
        actual = host.call("block", *POS)["state"]
        assert actual == expected, (row, actual)
    print("Eight Toolbox placements matched Java facing and waterlogging.")


def items(host, pos=POS):
    raw = block_value(host, pos, "Items")
    return {entry["Slot"]: f'{entry["id"]}={entry["count"]}'
            for entry in toolbox.snbt(raw or "[]")}


def recolor(host):
    host.commands((
        f"/setblock {xyz(POS)} minecraft:air",
        f"/setblock {xyz(POS)} {exact_state(BROWN, 'east', 'true')}",
        f"/item replace block {xyz(POS)} container.0 with minecraft:cobblestone 16",
        "/gamemode survival",
    ))
    host.step_to(host.clock() + 1)
    before = block_value(host, POS, "Compartments")
    assert items(host) == {0: "minecraft:cobblestone=16"}, items(host)
    for row in toolbox.reference("block-dye"):
        dye_id = f'minecraft:{row["color"]}_dye'
        host.command(f"/item replace entity @s hotbar.2 with {dye_id} 3")
        host.call("wait", 3)
        host.call("select", dye_id)
        host.call("interact", *POS, "south")
        host.call("wait", 4)
        assert host.call("state")["screen"] == "playing", (row, host.call("screen"))
        expected = exact_state(row["block"], row["facing"], row["waterlogged"])
        actual = host.call("block", *POS)["state"]
        assert actual == expected, (row, actual)
        assert items(host) == {0: f'minecraft:cobblestone={row["stored_count"]}'}, (row, items(host))
        assert before and block_value(host, POS, "Compartments") == before, row
        remaining_dye = host.call("inventory")["counts"].get(dye_id)
        assert remaining_dye == int(row["dye_count"]), (row, remaining_dye)
    print("All 16 placed dye colors preserved facing, water, storage, filters and dye count.")


def replace(host, slot, name, count=1, pos=POS):
    host.command(f"/item replace block {xyz(pos)} container.{slot} with {name} {count}")


def step(host, ticks):
    tick = host.clock()
    for offset in range(1, ticks + 1):
        host.step_to(tick + offset)


def sample(host, row):
    step(host, 4)
    contents = items(host)
    observed = "|".join(contents.get(slot, "_") for slot in range(SAMPLES))
    comparator = int(block_value(host, COMPARATOR, "OutputSignal"))
    assert (observed, comparator) == (row["first_eight_slots"], int(row["signal"])), (row, observed, comparator)
    print(f'{row["action"]} matched Java slots and comparator.')


def storage(host):
    rows = {row["action"]: row for row in toolbox.reference("storage")}
    host.commands((
        f"/setblock {xyz(POS)} minecraft:air",
        f"/setblock {xyz(POS)} {BROWN}",
        f"/setblock {xyz(COMPARATOR)} minecraft:comparator[facing=west]",
    ))
    sample(host, rows["empty"])
    replace(host, 0, "minecraft:cobblestone", 64)
    sample(host, rows["insert_first"])
    replace(host, 3, "minecraft:cobblestone", 51)
    sample(host, rows["settle_gap"])
    host.command(f"/data merge block {xyz(POS)} {{Items:[]}}")
    sample(host, rows["depleted"])

    # Give each compartment a filter, drain it, and exercise a real hopper insert.
    for slot in range(4, 32, 4):
        replace(host, slot, "minecraft:cobblestone")
    host.step_to(host.clock() + 1)
    host.command(f"/data merge block {xyz(POS)} {{Items:[]}}")
    host.command(f"/setblock {xyz(HOPPER)} minecraft:hopper[facing=down,enabled=true]")
    replace(host, 0, "minecraft:stone", pos=HOPPER)
    step(host, 10)
    assert items(host, HOPPER) == {0: "minecraft:stone=1"}
    sample(host, rows["remember_filter"])
    replace(host, 0, "minecraft:cobblestone", pos=HOPPER)
    step(host, 10)
    assert items(host) == {0: "minecraft:cobblestone=1"}
    assert not items(host, HOPPER)

    host.commands((f"/setblock {xyz(POS)} minecraft:air", f"/setblock {xyz(POS)} {BROWN}"))
    replace(host, 0, BROWN, pos=HOPPER)
    step(host, 10)
    assert not items(host) and items(host, HOPPER) == {0: f"{BROWN}=1"}
    print("Hopper inserted a matching stack and could not nest a Toolbox.")


def portable(host, actor, player):
    row, = toolbox.reference("portable")
    x, y, z = POS
    item = row["item"]
    named_item = item + '[minecraft:custom_name="Fixture Toolbox"]'
    feet = (x + 2.5, y, z + .5)
    host.command(f"/clear {player}")
    host.commands((
        f"/setblock {xyz(POS)} minecraft:water",
        f"/gamemode survival {player}",
        f"/item replace entity {player} hotbar.2 with {named_item}",
        f"/tp {player} {xyz(feet)}",
    ))
    postbox.mp.until("the Toolbox to reach the player", lambda:
        actor.call("inventory")["counts"].get(item) == 1)
    postbox.mp.until("the player to arrive at the placement point", lambda:
        actor.call("state")["player"]["position"] == list(feet))
    actor.call("select", item)
    actor.call("look-at", x + .5, y, z + .5)
    actor.call("interact", x, y - 1, z, "up")
    expected = exact_state(item, "east", "true")
    postbox.mp.until("the Toolbox placement to reach the host", lambda:
        host.call("block", *POS)["state"] == expected)
    postbox.mp.until("the Toolbox placement to reach the player", lambda:
        actor.call("block", *POS)["state"] == expected)
    replace(host, 0, "minecraft:cobblestone", int(row["carried_stored"]))
    step(host, 1)
    before_uuid = block_value(host, POS, "UniqueId")
    before_filter = block_value(host, POS, "Compartments")
    assert before_uuid and before_filter and "Fixture Toolbox" in block_value(host, POS, "CustomName")
    actor.call("look-at", x + .5, y + .3, z + .5)
    postbox.mp.until("the player to aim at the Toolbox", lambda:
        (actor.call("looking-at").get("block") or {}).get("pos") == list(POS))
    at = host.clock()
    actor.call("mouse", "left", "click")
    postbox.mp.until("the Toolbox to enter the player's inventory", lambda:
        actor.call("inventory")["counts"].get(item) == int(row["count"]))
    assert host.clock() == at, "The pickup waited for a world tick"
    postbox.mp.until("the pickup's source water to reach the player", lambda:
        actor.call("block", *POS)["block"] == row["original_replacement"])
    assert "Test passed" in host.command(f"/execute at {player} unless entity @e[type=minecraft:item,distance=..6]")

    actor.call("select", item)
    recovered = next(entry for entry in actor.call("inventory")["hotbar"] if entry.get("item") == item)
    components = toolbox.stack_components(recovered)
    uuid = [int(value) for value in re.findall(r"-?\d+", before_uuid)]
    carried = components["create:toolbox_inventory"]
    assert components["create:toolbox_uuid"] == uuid
    assert components["minecraft:custom_name"] == "Fixture Toolbox"
    assert carried["items"]["size"] == int(row["slots"])
    assert carried["items"]["items"]["0"]["count"] == int(row["carried_stored"])
    assert carried["filters"][0]["id"] == "minecraft:cobblestone"
    actor.call("interact", x, y - 1, z, "up")
    postbox.mp.until("the portable Toolbox to be restored", lambda:
        block_value(host, POS, "UniqueId") == before_uuid)
    assert block_value(host, POS, "Compartments") == before_filter
    assert "Fixture Toolbox" in block_value(host, POS, "CustomName")
    assert items(host) == {0: f'minecraft:cobblestone={row["restored_stored"]}'}, row
    postbox.mp.until("the placed Toolbox to leave the player's hands", lambda:
        item not in actor.call("inventory")["counts"])
    print("The Toolbox was picked up in one action and replaced with its original UUID, name, filter and inventory.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--dye", action="store_true")
    parser.add_argument("--portable", action="store_true")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan and not args.portable:
        parser.error("--lan requires --portable")
    env = {"HORIZON_NO_AUDIO": "1"}
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "Toolbox-storage", pack=args.pack, env=env))
        host.commands((
            "/fill 8 99 -12 16 99 -4 minecraft:stone",
            "/fill 8 100 -12 16 102 -4 minecraft:air",
        ))
        actor, player = host, "@s"
        if args.lan:
            player = "ToolboxGuest"
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-toolbox-")))
            actor = stack.enter_context(postbox.mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, scenario="toolbox-portable",
                pack=args.pack, env=env,
            ))
            postbox.mp.until("the Toolbox guest to join", lambda: any(
                entry["name"] == player and entry["placed"] for entry in host.call("lan", "status")["guests"]
            ))
        else:
            placement(host)
        if args.dye:
            host.command("/tp @s 12.5 100 -6.5")
            recolor(host)
        if args.portable:
            portable(host, actor, player)
        else:
            storage(host)


if __name__ == "__main__":
    main()
