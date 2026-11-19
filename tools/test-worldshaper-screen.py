#!/usr/bin/env python3
"""Configure the real Worldshaper screen and verify the held components."""
import argparse
from contextlib import ExitStack
import csv
from math import isclose
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
selection = import_module("test-worldshaper-selection")
ITEM = "create:handheld_worldshaper"
GUEST = "ShaperEditor"
ENV = {"HORIZON_NO_AUDIO": "1"}


def widget(actor, prefix):
    buttons = actor.call("screen")["buttons"]
    matches = [button for button in buttons if button["label"].startswith(prefix)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {prefix} control: {buttons}")
    button = matches[0]
    return button["x"] + button["w"] / 2, button["y"] + button["h"] / 2


def open_editor(actor):
    actor.call("look-at", 10.5, 170.3, 22.5)
    actor.call("key", "shift", "down")
    actor.call("wait", 4)
    try:
        actor.call("mouse", "right", "click")
        mp.until("the Worldshaper settings screen", lambda: actor.call("state")["screen"] == "mod")
    finally:
        actor.call("key", "shift", "up")
    mp.until("the Worldshaper controls", lambda: any(
        button["label"].startswith("Width: ") for button in actor.call("screen")["buttons"]))


def check_fill(host, actor, player, expected):
    base = (10, 171, 22)
    face = expected["hit_face"]
    expected_cells = {
        tuple(map(int, offset.split(":")))
        for offset in expected["changed_relative_cells"].split("|")
    }
    dz = 3.5 if face == "south" else -4.85
    feet = (10.5, 170.0, 22 + dz + 0.5)
    host.commands((
        "/fill 9 170 17 12 173 26 minecraft:air",
        "/setblock 10 171 22 minecraft:stone",
        f"/tp {player} {' '.join(map(str, feet))}",
    ))
    mp.until("the actor to reach the target", lambda: all(
        isclose(actual, coord, abs_tol=1e-4) for actual, coord in zip(
            actor.call("state")["player"]["position"], feet, strict=True)))
    actor.call("look-at", 10.5, 171.5, 22.5)
    def aimed_at_face():
        hit = actor.call("looking-at").get("block")
        return hit and hit["pos"] == list(base) and hit["face"] == face
    mp.until(f"the {face} side of the Fill target", aimed_at_face)
    actor.call("mouse", "right", "click")
    first = min(expected_cells)
    mp.until("the first original Cuboid cell to fill", lambda:
             host.call("block", *(coord + offset for coord, offset in zip(base, first)))["block"]
             == "minecraft:gold_block")
    offsets = [(x, y, z) for z in range(-5, 5) for y in range(-1, 3) for x in range(-1, 3)]
    replies = host.call("script", script="".join(
        f"block {base[0] + x} {base[1] + y} {base[2] + z}\n" for x, y, z in offsets))
    actual = {offset for offset, block in zip(offsets, replies, strict=True)
              if block["block"] == "minecraft:gold_block"}
    assert actual == expected_cells, (sorted(expected_cells - actual), sorted(actual - expected_cells))
    assert host.call("block", *base)["block"] == "minecraft:stone"
    mp.until("the actor to retain the Worldshaper", lambda:
             mp.count(actor, ITEM) == int(expected["item_count"]))
    host.commands((
        "/fill 9 170 17 12 173 26 minecraft:air",
        "/setblock 10 170 22 minecraft:gold_block",
        f"/tp {player} 10.5 170 25.5",
    ))
    actor.call("wait", 4)
    print(f'{expected["placement"]} {face} matched all {len(actual)} original changed Cuboid cells.')


def check_tools(host, actor, player, cases, stone):
    base = (10, 171, 22)
    for case in cases:
        name = case["tool"]
        gold = "minecraft:gold_block"
        host.commands((
            f"/tp {player} 10.5 170 25.5",
            "/fill 9 170 21 12 172 24 minecraft:air",
            f"/setblock 10 170 22 {gold}",
            f"/item replace entity {player} hotbar.0 with {ITEM}",
        ))
        mp.until("the actor to reach the original work area", lambda:
                 actor.call("state")["player"]["position"] == [10.5, 170.0, 25.5])
        actor.call("select", ITEM)
        if case["has_selected"] == "true":
            host.command(f"/item replace entity {player} hotbar.0 with {ITEM}[minecraft:custom_data={{marker:17}}]")
            mp.until("the new Worldshaper to reach the actor", lambda:
                     "marker" in str(actor.call("inventory")["hotbar"][0]))
            selection.select(host, actor, player, (10, 170, 22), {**stone, "name": gold}, 0.3)
        open_editor(actor)
        for label in ("Width: ", "Length: "):
            actor.call("scroll-at", *widget(actor, label), 1)
        actor.call("click-at", *widget(actor, name))
        actor.call("click-at", *widget(actor, "Confirm"))
        mp.until("the Worldshaper screen to close", lambda: actor.call("state")["screen"] == "playing")
        def configured():
            data = host.command(f"/data get entity {player} SelectedItem")
            return (f'"create:shaper_tool": "{name.lower()}"' in data
                    and '"create:shaper_brush_params": [I; 2, 1, 2]' in data
                    and ('"create:shaper_block_used"' in data) == (case["has_selected"] == "true"))
        mp.until(f"the {name} settings to reach the server", configured)
        host.commands((
            "/setblock 10 171 22 minecraft:stone",
            f"/setblock 11 171 22 {gold}",
            "/setblock 11 171 23 minecraft:cobblestone",
        ))
        actor.call("look-at", 10.5, 171.5, 22.5)
        def same_hit():
            hit = actor.call("looking-at").get("block")
            return hit and hit["pos"] == list(base) and hit["face"] == case["hit_face"]
        mp.until("the original Cuboid tool hit", same_hit)
        actor.call("mouse", "right", "click")
        def state_grid(encoded):
            result = {}
            for cell in encoded.split("|"):
                offset, state = cell.split("=", 1)
                pos = tuple(origin + int(delta) for origin, delta in zip(base, offset.split(":"), strict=True))
                result[pos] = state
            return result
        expected = state_grid(case["after"])
        compare_at = next(iter(state_grid(case["changes"])))
        mp.until(f"the first original {name} change", lambda:
                 host.call("block", *compare_at)["block"] == expected[compare_at])
        actual = {pos: host.call("block", *pos)["block"] for pos in expected}
        assert actual == expected, (name, actual, expected)
        mp.until("the Worldshaper to remain in hand", lambda:
                 mp.count(actor, ITEM) == int(case["item_count"]))
        actor.call("wait", 4)
        print(f'{name} matched all {case["changed_count"]} original changed cells and the complete eight-cell grid.')


def check_rounded(host, actor, player, cases, stone):
    base = (10, 171, 22)
    gold = "minecraft:gold_block"
    for index, case in enumerate(cases, start=1):
        brush = case["brush"].capitalize()
        params = [int(case[f"param{i}"]) for i in range(3)]
        host.commands((
            "/fill 5 170 15 15 177 29 minecraft:air",
            "/fill 5 169 15 15 169 29 minecraft:stone",
            f"/tp {player} 10.5 170 25.5",
            f"/setblock 10 170 22 {gold}",
            f"/item replace entity {player} hotbar.0 with {ITEM}[minecraft:custom_data={{marker:17}}]",
        ))
        mp.until("the actor to return to the selection block", lambda:
                 actor.call("state")["player"]["position"] == [10.5, 170.0, 25.5])
        def fresh():
            held = str(actor.call("inventory")["hotbar"][0])
            return "marker" in held and "shaper_brush" not in held
        mp.until("an unconfigured Worldshaper", fresh)
        selection.select(host, actor, player, (10, 170, 22), {**stone, "name": gold}, 0.3)
        open_editor(actor)
        for _ in range(index):
            actor.call("scroll-at", *widget(actor, "Brush: "), 1)
        mp.until(f"the {brush} editor", lambda: any(
            button["label"] == f"Brush: {brush}" for button in actor.call("screen")["buttons"]))
        for label, steps in (("Radius: ", params[0] - 1), ("Height: ", params[1] - 1)):
            if steps:
                x, y = widget(actor, label)
                actor.call("script", script=f"scroll-at {x} {y} 1\n" * steps)
        actor.call("click-at", *widget(actor, "Attached"))
        actor.call("click-at", *widget(actor, "Confirm"))
        mp.until("the Worldshaper screen to close", lambda: actor.call("state")["screen"] == "playing")
        def configured():
            data = host.command(f"/data get entity {player} SelectedItem")
            return (f'"create:shaper_brush": "{brush.lower()}"' in data
                    and f'"create:shaper_brush_params": [I; {", ".join(map(str, params))}]' in data
                    and '"create:shaper_placement_options": "attached"' in data)
        mp.until(f"the {brush} components to match Java", configured)
        host.commands((
            f"/setblock 10 170 22 minecraft:air",
            "/setblock 10 171 22 minecraft:stone",
        ))
        if case["hit_face"] == "up":
            host.command("/setblock 13 172 22 minecraft:stone")
            feet = (13.5, 173.0, 22.5)
            aim = (10.5, 171.8, 22.5)
        else:
            host.command("/fill 5 169 16 15 169 27 minecraft:air")
            feet = (10.5, 170.0, 28.5)
            aim = (10.5, 171.5, 22.5)
        host.command(f"/tp {player} {' '.join(map(str, feet))}")
        mp.until("the actor to reach the original side", lambda:
                 actor.call("state")["player"]["position"] == list(feet))
        actor.call("look-at", *aim)
        if case["hit_face"] == "up":
            def directly_above():
                hit = actor.call("looking-at").get("block")
                return hit and hit["pos"] == list(base) and hit["face"] == "up"
            mp.until("the Cylinder target's upper face", directly_above)
        actor.call("mouse", "right", "click")
        offsets = [tuple(map(int, cell.split(":")))
                   for cell in case["changed_relative_cells"].split("|")]
        expected = [tuple(coord + delta for coord, delta in zip(base, offset, strict=True))
                    for offset in offsets]
        mp.until(f"the first original {brush} cell to fill", lambda:
                 host.call("block", *expected[0])["block"] == gold)
        actual = host.call("script", script="".join(
            f"block {x} {y} {z}\n" for x, y, z in expected))
        missing = [block["pos"] for block in actual if block["block"] != gold]
        assert not missing, (brush, missing)
        assert host.call("block", *base)["block"] == "minecraft:stone"
        mp.until("the Worldshaper to remain in hand", lambda:
                 mp.count(actor, ITEM) == int(case["item_count"]))
        count = host.command(f"/fill 5 169 15 15 177 29 minecraft:air replace {gold}")
        assert f"Successfully filled {case['changed_count']} block(s)" in count, count
        print(f'{brush} matched all {len(expected)} original cells and no extra cells in the test volume.')


def check_patterns(host, actor, player, cases, stone):
    gold = "minecraft:gold_block"
    labels = {
        "Solid": "Solid", "Checkered": "Checkerboard", "InverseCheckered": "Inverted Checkerboard",
        "Chance25": "25% Roll", "Chance50": "50% Roll", "Chance75": "75% Roll",
    }
    cases = [{**case, "target_xyz": tuple(map(int, case.get("target_absolute", case.get("target")).split(":")))}
             for case in cases]
    min_x = min(case["target_xyz"][0] for case in cases) - 5
    max_x = max(case["target_xyz"][0] for case in cases) + 5
    clear = f"/fill {min_x} 111 -14 {max_x} 119 -1 minecraft:air"
    host.commands((
        f"/fill {min_x} 110 -14 {max_x} 110 -1 minecraft:stone",
        clear,
        f"/setblock 10 170 22 {gold}",
        f"/item replace entity {player} hotbar.0 with {ITEM}[minecraft:custom_data={{marker:17}}]",
    ))
    mp.until("the fresh Worldshaper to arrive", lambda:
             "marker" in str(actor.call("inventory")["hotbar"][0]))
    selection.select(host, actor, player, (10, 170, 22), {**stone, "name": gold}, 0.3)
    for index, name in enumerate(dict.fromkeys(case["pattern"] for case in cases)):
        label = labels[name]
        host.command(f"/tp {player} 10.5 170 25.5")
        mp.until("the actor to return to the editor area", lambda:
                 actor.call("state")["player"]["position"] == [10.5, 170.0, 25.5])
        open_editor(actor)
        if index == 0:
            for parameter, steps in (("Width: ", 1), ("Height: ", 2), ("Length: ", 3)):
                x, y = widget(actor, parameter)
                actor.call("script", script=f"scroll-at {x} {y} 1\n" * steps)
        actor.call("click-at", *widget(actor, label))
        actor.call("click-at", *widget(actor, "Attached"))
        actor.call("click-at", *widget(actor, "Confirm"))
        mp.until("the Worldshaper screen to close", lambda: actor.call("state")["screen"] == "playing")
        def exact_components():
            data = host.command(f"/data get entity {player} SelectedItem")
            expected = (
                f'"create:placement_pattern": "{name.lower()}"',
                '"create:shaper_brush_params": [I; 2, 3, 4]',
                '"create:shaper_placement_options": "attached"',
                '"create:shaper_brush": "cuboid"',
                '"create:shaper_tool": "fill"',
                'Name: "minecraft:gold_block"',
            )
            return all(part in data for part in expected)
        mp.until(f"the {label} configuration to match Java", exact_components)
        for case in (entry for entry in cases if entry["pattern"] == name):
            bx, by, bz = base = case["target_xyz"]
            feet = [bx + 0.5, by - 1.0, bz + 5.5]
            host.commands((
                clear,
                f"/setblock {bx} {by} {bz} minecraft:stone",
                f"/tp {player} {' '.join(map(str, feet))}",
            ))
            mp.until("the actor to reach the Java target", lambda:
                     actor.call("state")["player"]["position"] == feet)
            actor.call("look-at", bx + 0.5, by + 0.5, bz + 0.5)
            actor.call("mouse", "right", "click")
            offsets = [tuple(map(int, cell.split(":")))
                       for cell in case["changed_relative_cells"].split("|")]
            expected = [tuple(coord + delta for coord, delta in zip(base, offset, strict=True))
                        for offset in offsets]
            mp.until(f"the first {label} cell to fill", lambda:
                     host.call("block", *expected[0])["block"] == gold)
            actual = host.call("script", script="".join(
                f"block {x} {y} {z}\n" for x, y, z in expected))
            missing = [block["pos"] for block in actual if block["block"] != gold]
            assert not missing, (name, missing)
            assert host.call("block", *base)["block"] == "minecraft:stone"
            mp.until("the Worldshaper to stay in hand", lambda:
                     mp.count(actor, ITEM) == int(case["item_count"]))
            count = host.command(f"{clear} replace {gold}")
            assert f"Successfully filled {case['changed_count']} block(s)" in count, count
            actor.call("wait", 4)
            print(f"{label} at {base} matched all {len(expected)} cells and no extra cells.")


def run(args, scratch):
    pattern_cases = []
    env = ENV
    if args.patterns or args.chance_patterns:
        name = "worldshaper_chance_stream-java.csv" if args.chance_patterns else "worldshaper_pattern_fill-java.csv"
        with (ROOT / "fixtures" / name).open() as source:
            pattern_cases = list(csv.DictReader(source))
        if args.chance_patterns:
            env = ENV | {"CREATE_WORLDSHAPER_PATTERN_TRACE_SEED": pattern_cases[0]["seed"]}
    brush_cases = []
    if args.rounded_fill:
        with (ROOT / "fixtures/worldshaper_rounded_fill-java.csv").open() as source:
            brush_cases = list(csv.DictReader(source))
    tool_cases = []
    if args.cuboid_tools:
        with (ROOT / "fixtures/worldshaper_cuboid_tools-java.csv").open() as source:
            tool_cases = list(csv.DictReader(source))
    cases = {}
    if args.cuboid_fill:
        with (ROOT / "fixtures/worldshaper_cuboid_fill-java.csv").open() as source:
            cases = {row["placement"]: row for row in csv.DictReader(source)}
    with (ROOT / "fixtures/worldshaper_selection-java.csv").open() as source:
        stone = next(row for row in csv.DictReader(source) if row["case"] == "stone")
    source_block = "minecraft:gold_block" if cases else "minecraft:stone"
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, "WorldshaperScreen", render=not args.lan,
                                                    pack=args.pack, env=env))
        actor, player = host, "@s"
        if args.lan:
            player = GUEST
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            actor = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario="worldshaper-screen", pack=args.pack, env=env))
            mp.until("the guest to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]))
        host.command(f"/gamemode survival {player}")
        host.commands((
            "/fill 6 169 16 14 169 28 minecraft:stone",
            "/fill 6 170 20 14 175 28 minecraft:air",
            f"/tp {player} 10.5 170 25.5",
            f"/setblock 10 170 22 {source_block}",
            f"/item replace entity {player} hotbar.0 with {ITEM}[minecraft:custom_data={{marker:17}}]",
        ))
        mp.until("the Worldshaper to reach the player", lambda: mp.count(actor, ITEM) == 1)
        actor.call("select", ITEM)
        if pattern_cases:
            check_patterns(host, actor, player, pattern_cases, stone)
            if args.chance_patterns:
                expected = f'Worldshaper pattern RNG fingerprint: {pattern_cases[-1]["final_next_long"]}'
                log = host.socket.parent / "ctl.log"
                mp.until("the exact Java random-stream fingerprint", lambda:
                         log.exists() and expected in log.read_text(errors="replace"))
                print(expected)
            return
        if brush_cases:
            check_rounded(host, actor, player, brush_cases, stone)
            return
        if tool_cases:
            check_tools(host, actor, player, tool_cases, stone)
            return
        selection.select(host, actor, player, (10, 170, 22), {**stone, "name": source_block}, 0.3)
        for index, name in enumerate(("Merged", "Attached", "Inserted")):
            open_editor(actor)
            if index == 0:
                for label, steps in (("Width: ", 1), ("Height: ", 2), ("Length: ", 3)):
                    x, y = widget(actor, label)
                    actor.call("script", script=f"scroll-at {x} {y} 1\n" * steps)
                mp.until("the three brush dimensions", lambda: all(
                    any(button["label"] == expected for button in actor.call("screen")["buttons"])
                    for expected in ("Width: 2", "Height: 3", "Length: 4")))
                if args.visual:
                    actor.call("screenshot", ROOT / ".local/worldshaper-settings.png")
            else:
                labels = [button["label"] for button in actor.call("screen")["buttons"]]
                for expected in ("Width: 2", "Height: 3", "Length: 4"):
                    if expected not in labels:
                        raise RuntimeError(f"Reopened screen lost dimensions: {labels}")
            actor.call("click-at", *widget(actor, name))
            actor.call("click-at", *widget(actor, "Confirm"))
            mp.until("the Worldshaper screen to close", lambda: actor.call("state")["screen"] == "playing")
            def configured():
                data = host.command(f"/data get entity {player} SelectedItem")
                required = ('"create:placement_pattern": "solid"', '"create:shaper_brush": "cuboid"',
                            '"create:shaper_brush_params": [I; 2, 3, 4]', '"create:shaper_tool": "fill"',
                            f'"create:shaper_placement_options": "{name.lower()}"',
                            '"create:shaper_block_used"', f'Name: "{source_block}"', 'marker: 17')
                return data if all(text in data for text in required) else None
            try:
                mp.until(f"the server to save {name} settings", configured)
            except RuntimeError as error:
                raise AssertionError(host.command(f"/data get entity {player} SelectedItem")) from error
            if name in cases:
                check_fill(host, actor, player, cases[name])
    print("Worldshaper UI saved Cuboid 2×3×4, Solid Fill, and all three placement modes while preserving the selected block.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--visual", action="store_true")
    scenario = parser.add_mutually_exclusive_group()
    scenario.add_argument("--cuboid-fill", action="store_true")
    scenario.add_argument("--cuboid-tools", action="store_true")
    scenario.add_argument("--rounded-fill", action="store_true")
    scenario.add_argument("--patterns", action="store_true")
    scenario.add_argument("--chance-patterns", action="store_true")
    with TemporaryDirectory(prefix="hc-wse-", dir="/private/tmp") as scratch:
        run(parser.parse_args(), Path(scratch))
