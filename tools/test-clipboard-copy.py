#!/usr/bin/env python3
"""Replay Java Clipboard copying and machine settings transfer."""

import argparse
from contextlib import ExitStack
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
clipboard = import_module("test-clipboard-placement")
ITEM = "create:clipboard"
BOARD = (8, 101, -7)
SOURCE = (12, 101, -7)
TARGET = (16, 101, -7)
SUPPLY = (7, 101, -10)
ORIGINAL_BOARD = (
    '{id:"create:clipboard",count:1,components:{"create:clipboard_content":'
    '{type:"written",pages:[[{checked:1b,text:"Sort brass",icon:{},item_amount:0},'
    '{checked:1b,text:"#Warehouse",icon:{id:"minecraft:iron_ingot",count:1},item_amount:7}]],'
    'read_only:0b,previously_opened_page:0}}}'
)


def item_is(host, player, snbt):
    return clipboard.held_clipboard(host, player) == clipboard.menu.clipboard_snbt(snbt)


def diode_at(host, position):
    state = host.call("block", *position)["state"]
    duration = host.command(f"/data get block {clipboard.coords(position)} ScrollValue")
    return {"interval": int(duration.rsplit("block data: ", 1)[1]), "inverted": "inverted=true" in state}


def aim(host, actor, player, position, height, *, face="up"):
    x, y, z = position
    feet = (x + .5, float(y), z - 1.5)
    host.command(f"/tp {player} {clipboard.coords(feet)}")
    multiplayer.until("the player to reach the machine", lambda:
                      actor.call("state")["player"]["position"] == list(feet))
    actor.call("look-at", x + .5, y + height, z + .5)
    def targeted():
        hit = actor.call("looking-at").get("block") or {}
        return hit.get("pos") == list(position) and (face is None or hit.get("face") == face)

    multiplayer.until("the ray to hit the selected block", targeted)
    actor.call("wait", 6)


def run_fixture(host, actor, player, reference):
    board, source, target, supply = map(clipboard.coords, (BOARD, SOURCE, TARGET, SUPPLY))
    cases = reference["interactions"]
    host.commands((
        f"/gamemode survival {player}",
        f"/tp {player} 8.5 101 -9.5",
        f"/setblock {board} {ITEM}[face=floor,facing=north,written=true]",
        f"/data merge block {board} {{ClipboardItem:{ORIGINAL_BOARD}}}",
        f"/setblock {source} create:pulse_extender[inverted=true]",
        f"/data merge block {source} {{ScrollValue:71}}",
        f"/setblock {target} create:pulse_repeater[inverted=false]",
        f"/data merge block {target} {{ScrollValue:9}}",
        f"/setblock {supply} minecraft:barrel",
        f"/data merge block {supply} {{Items:[{{Slot:0b," + cases["board_right"]["before"][1:] + "]}",
    ))
    actor.call("interact", *SUPPLY, "east")
    multiplayer.until("the exact source Clipboard in the barrel", lambda:
                      clipboard.menu.stack_item(actor, 300) == ITEM)
    actor.call("click-slot", 300)
    actor.call("click-slot", 0)
    actor.call("close")
    actor.call("select", ITEM)
    multiplayer.until("the actor's loaded Clipboard to match Java", lambda:
                      item_is(host, player, cases["board_right"]["before"]))
    start = host.clock()

    for label, button in (("board_right", "right"), ("board_left_duplicate", "left")):
        case = cases[label]
        assert case["canceled"] and item_is(host, player, case["before"])
        aim(host, actor, player, BOARD, .03125)
        actor.call("mouse", button, "click")
        actor.call("wait", 5)
        multiplayer.until("the held Clipboard entry merge to match Java", lambda:
                          item_is(host, player, case["after"]))
        assert actor.call("state")["screen"] == "playing"
        assert host.call("block", *BOARD)["block"] == ITEM
        board_data = host.command(f"/data get block {board} ClipboardItem")
        actual = clipboard.menu.clipboard_snbt(board_data.split("block data: ", 1)[1])
        assert actual == clipboard.menu.clipboard_snbt(ORIGINAL_BOARD), actual
        assert host.clock() == start
    print("Clipboard right and left clicks merge Java entries, suppress duplicate text and leave the source board intact.")

    case = cases["diode_right"]
    assert case["canceled"] and item_is(host, player, case["before"])
    aim(host, actor, player, SOURCE, .11)
    actor.call("mouse", "right", "click")
    multiplayer.until("the copied Brass Diode settings to match Java", lambda:
                      item_is(host, player, case["after"]))
    assert diode_at(host, SOURCE) == {"interval": 71, "inverted": True}
    assert actor.call("state")["screen"] == "playing"
    assert host.clock() == start

    assert diode_at(host, TARGET) == reference["diode"]["before"]
    aim(host, actor, player, TARGET, .11)
    actor.call("mouse", "left", "click")
    expected = dict(reference["diode"]["after"])
    assert expected.pop("canceled")
    multiplayer.until("the target diode's Java interval and inversion to apply", lambda:
                      diode_at(host, TARGET) == expected)
    assert item_is(host, player, case["after"])
    assert host.clock() == start
    print("Java 71 ticks copied as row 1, value 3 and pasted as 60 ticks with inversion on the same simulation tick.")


def link_snbt(raw):
    # Java 1.21.1 writes a custom name's text as a quoted JSON string in SNBT.
    quoted = json.dumps("Workshop")
    return clipboard.menu.clipboard_snbt(raw.replace("'" + quoted + "'", json.dumps(quoted)))


def link_frequencies(host, position):
    values = {}
    for key in ("First", "Last"):
        response = host.command(f"/data get block {clipboard.coords(position)} Frequency{key}")
        value = link_snbt(response.split("block data: ", 1)[1])
        value.pop("Slot", None)
        values[key] = value
    return values


def run_link(host, actor, player, reference):
    source, target = map(clipboard.coords, (SOURCE, TARGET))
    assert reference["copy"]["canceled"] and reference["paste"]["canceled"]
    expected = link_snbt(reference["copy"]["snapshots"][0])
    frequencies = expected["components"]["create:clipboard_content"]["copied_values"]["Frequencies"]
    before, after = map(link_snbt, reference["paste"]["snapshots"])
    before_data, after_data = (
        value.replace("First:", "FrequencyFirst:", 1).replace("Last:", "FrequencyLast:", 1)
        for value in reference["paste"]["snapshots"]
    )
    host.commands((
        f"/gamemode survival {player}",
        f"/setblock {source} create:redstone_link[facing=up]",
        f"/data merge block {source} {after_data}",
        f"/setblock {target} create:redstone_link[facing=up]",
        f"/data merge block {target} {before_data}",
        f"/item replace entity {player} hotbar.0 with {ITEM}",
    ))
    multiplayer.until("the blank Clipboard to reach the player's hotbar", lambda:
                      multiplayer.count(actor, ITEM) == 1)
    actor.call("select", ITEM)
    tick = host.clock()
    assert link_frequencies(host, SOURCE) == frequencies
    assert link_frequencies(host, TARGET) == before

    def held():
        response = host.command(f"/data get entity {player} SelectedItem")
        return link_snbt(response.split("entity data: ", 1)[1])

    aim(host, actor, player, SOURCE, .15)
    actor.call("mouse", "right", "click")
    multiplayer.until("the copied Java frequency pair", lambda: held() == expected)
    assert link_frequencies(host, SOURCE) == frequencies
    assert actor.call("state")["screen"] == "playing"
    assert host.clock() == tick

    aim(host, actor, player, TARGET, .15)
    actor.call("mouse", "left", "click")
    multiplayer.until("the Java target frequency pair", lambda: link_frequencies(host, TARGET) == after)
    assert held() == expected
    assert actor.call("block", *TARGET)["state"].startswith("create:redstone_link[")
    assert host.clock() == tick
    print("Clipboard copied the named first frequency and pasted it with an empty second slot on the same simulation tick.")



def run_chute(host, actor, player, reference):
    source, target = map(clipboard.coords, (SOURCE, TARGET))
    host.commands((
        f"/gamemode survival {player}",
        "/setblock 12 100 -7 minecraft:barrel",
        "/setblock 12 102 -7 minecraft:barrel",
        "/setblock 16 100 -7 minecraft:barrel",
        "/setblock 16 102 -7 minecraft:barrel",
        f"/setblock {source} create:smart_chute",
        f"/setblock {target} create:smart_chute",
        f'/data merge block {target} {{Filter:{{id:"minecraft:gold_ingot",count:1}},FilterAmount:3,UpTo:1b}}',
        f"/item replace entity {player} hotbar.0 with {ITEM}",
    ))
    multiplayer.until("the blank Clipboard to reach the player's hotbar", lambda:
                      multiplayer.count(actor, ITEM) == 1)
    actor.call("select", ITEM)
    tick = host.clock()

    def click_machine(position, button):
        aim(host, actor, player, position, .42, face=None)
        actor.call("mouse", button, "click")

    def verify(case):
        expected = clipboard.menu.clipboard_snbt(case["stack"])
        assert case["canceled"]

        def matches():
            raw = host.command(f"/data get block {target} Filter").split("block data: ", 1)[1]
            saved = clipboard.menu.clipboard_snbt(raw)
            saved.pop("Slot", None)
            if saved != expected:
                return False
            count = host.command(f"/data get block {target} FilterAmount").split("block data: ", 1)[1]
            up_to = host.command(f"/data get block {target} UpTo").split("block data: ", 1)[1]
            return (int(count) == case["count"] and up_to == ("1b" if case["up_to"] else "0b")
                    and multiplayer.count(actor, "create:filter") == case["supply"])

        multiplayer.until("the original Smart Chute filter, amount and carried supplies", matches)
        assert actor.call("state")["screen"] == "playing"
        assert host.clock() == tick

    for kind, item, amount, up_to in (("plain", "minecraft:quartz", 7, "0b"), ("filter", "create:filter", 4, "1b")):
        host.command(f'/data merge block {source} {{Filter:{{id:"{item}",count:1}},FilterAmount:{amount},UpTo:{up_to}}}')
        case = reference["copy"][kind]
        assert case["canceled"]
        click_machine(SOURCE, "right")
        multiplayer.until("the Clipboard's exact Java filtering payload", lambda:
                          item_is(host, player, case["stack"]))
        click_machine(TARGET, "left")
        verify(reference["paste"]["plain" if kind == "plain" else "missing"])
    host.command(f"/item replace entity {player} hotbar.1 with create:filter")
    multiplayer.until("one List Filter to reach the player", lambda: multiplayer.count(actor, "create:filter") == 1)
    click_machine(TARGET, "left")
    verify(reference["paste"]["supplied"])
    print("Smart Chute copied seven exact quartz and kept quartz at up-to-four without a spare filter.")
    print("Supplying a List Filter installed it and consumed one item, as in Java.")

    host.commands((
        "/setblock 12 102 -7 minecraft:air",
        f'/data merge block {source} {{Filter:{{id:"minecraft:quartz",count:1}},FilterAmount:7,UpTo:0b}}',
    ))
    click_machine(SOURCE, "right")
    hidden = reference["copy"]["hidden_amount"]
    assert hidden["canceled"]
    multiplayer.until("the hidden amount to be omitted from the copied data", lambda:
                      item_is(host, player, hidden["stack"]))
    assert host.clock() == tick
    print("A chute with its amount hidden copied the filter alone, as in Java.")




def run_funnel(host, actor, player, rows):
    host.command(f"/gamemode survival {player}")
    tick = host.clock()

    def setup(position, mode, java_state):
        x, y, z = position
        point = clipboard.coords(position)
        state = java_state.replace("Block{", "").replace("}", "")
        commands = [
            f"/setblock {x} {y} {z+1} minecraft:barrel",
        ]
        if mode.startswith("belt"):
            for bx, part in ((x-1, "start"), (x, "middle"), (x+1, "end")):
                commands.append(f"/setblock {bx} {y-1} {z} create:belt[facing=east,part={part},slope=horizontal]")
        else:
            support = "create:depot" if mode.startswith("depot") else "minecraft:smooth_stone"
            commands.append(f"/setblock {x} {y-1} {z} {support}")
        commands.append(f"/setblock {point} {state}")
        for command in commands:
            host.call("command", command)
        multiplayer.until(f"the {mode} Funnel at {position} to match {state}", lambda:
                          host.call("block", *position)["state"] == state)
        return state

    def click_funnel(position, button):
        x, y, z = position
        feet = (x + .5, float(y), z - 1.5)
        host.command(f"/tp {player} {clipboard.coords(feet)}")
        multiplayer.until("the player to reach the Brass Funnel", lambda:
                          actor.call("state")["player"]["position"] == list(feet))
        actor.call("look-at", x + .5, y + .59, z + .65)
        multiplayer.until("the ray to hit the mounted or plain Funnel", lambda:
                          (actor.call("looking-at").get("block") or {}).get("pos") == list(position))
        actor.call("wait", 6)
        actor.call("mouse", button, "click")

    for i, row in enumerate(rows):
        source_pos = (12, 101, -7 - 4 * i)
        target_pos = (16, 101, -7 - 4 * i)
        expected_source = setup(source_pos, row["source"], row["source_state"])
        expected_target = setup(target_pos, row["target"], row["target_state"])
        source, target = map(clipboard.coords, (source_pos, target_pos))
        host.commands((
            f'/data merge block {source} {{Filter:{{id:"minecraft:quartz",count:1}},FilterAmount:7,UpTo:0b}}',
            f'/data merge block {target} {{Filter:{{id:"minecraft:gold_ingot",count:1}},FilterAmount:3,UpTo:1b}}',
            f"/item replace entity {player} hotbar.0 with {ITEM}",
        ))
        multiplayer.until("the blank Clipboard in the selected hotbar slot", lambda:
                          item_is(host, player, '{id:"create:clipboard",count:1}'))
        actor.call("select", ITEM)
        assert row["copy_canceled"] and row["paste_canceled"]
        click_funnel(source_pos, "right")
        multiplayer.until("the Java Brass Funnel payload to reach the Clipboard", lambda:
                          item_is(host, player, row["clipboard"]))
        click_funnel(target_pos, "left")

        def matches():
            saved = host.command(f"/data get block {target} Filter").split("block data: ", 1)[1]
            item = clipboard.menu.clipboard_snbt(saved)
            item.pop("Slot", None)
            if item != clipboard.menu.clipboard_snbt(row["filter"]):
                return False
            count = host.command(f"/data get block {target} FilterAmount").split("block data: ", 1)[1]
            up_to = host.command(f"/data get block {target} UpTo").split("block data: ", 1)[1]
            return int(count) == row["count"] and up_to == ("1b" if row["up_to"] else "0b")

        multiplayer.until("the Java Brass Funnel filter and amount mode", matches)
        assert host.call("block", *source_pos)["state"] == expected_source
        assert host.call("block", *target_pos)["state"] == expected_target
        assert actor.call("state")["screen"] == "playing"
        assert host.clock() == tick
        print(f'{row["source"]} to {row["target"]}: Java filter, amount {row["count"]}, up-to {row["up_to"]}.')



def run(args):
    scope = "funnel" if args.funnel else "chute" if args.chute else "link" if args.link else "copy"
    reference = json.loads((ROOT / f"fixtures/clipboard-{scope}-java.json").read_text())
    mode = "Lan" if args.lan else "Solo"
    env = {"HORIZON_NO_AUDIO": "1"}
    with ExitStack() as resources:
        host = resources.enter_context(fixture_world(args, "Clipboard" + scope.title() + mode, pack=args.pack,
                                                    render=not args.lan, env=env))
        floor_min_z = -32 if args.funnel else -14
        host.command(f"/fill 5 100 {floor_min_z} 18 100 -4 minecraft:smooth_stone")
        actor, player = host, "@s"
        if args.lan:
            scratch = Path(resources.enter_context(TemporaryDirectory(prefix="hc-cc-")))
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            player = "ClipboardGuest"
            actor = resources.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, pack=args.pack, render=True,
                scenario="clipboard-copy", env=env,
            ))
            multiplayer.until("the Clipboard copy guest to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]
            ))
            host.command("/tp @s 5.5 101 -9.5")
        if args.funnel:
            run_funnel(host, actor, player, reference)
        elif args.chute:
            run_chute(host, actor, player, reference)
        elif args.link:
            run_link(host, actor, player, reference)
        else:
            run_fixture(host, actor, player, reference)
    print(f"{mode} matched the original {scope} snapshots.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--lan", action="store_true")
    machine = parser.add_mutually_exclusive_group()
    machine.add_argument("--link", action="store_true")
    machine.add_argument("--chute", action="store_true")
    machine.add_argument("--funnel", action="store_true")
    run(parser.parse_args())
