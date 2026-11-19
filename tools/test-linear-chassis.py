#!/usr/bin/env python3
"""Replay the pinned Java Linear Chassis and Secondary Linear Chassis GameTests."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

ANCHOR = (7, 180, 39)
AXES = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
CHASSIS = "create:linear_chassis"
SECONDARY = "create:secondary_linear_chassis"
AIR = "minecraft:air"
FIELDS = ("scenario", "phase", "axis", "sticky_top", "sticky_bottom", "adjacent_sticky_top",
          "range", "payload")


def offset(pos, direction, distance=1):
    return tuple(n + d * distance for n, d in zip(pos, direction, strict=True))


def coordinates(pos):
    return " ".join(map(str, pos))


def chassis(axis, *, top=False, bottom=False, kind=CHASSIS):
    return f"{kind}[axis={axis},sticky_top={str(top).lower()},sticky_bottom={str(bottom).lower()}]"


def setup(scenario):
    direction = AXES[scenario % 3]
    face = AXES[2] if direction == AXES[1] else AXES[1]
    axis = "xyz"[AXES.index(direction)]
    beside = offset(ANCHOR, face)
    across = offset(beside, face)
    bearing = offset(ANCHOR, face, -1)
    motor = offset(bearing, face, -1)
    build = {
        ANCHOR: chassis(axis, top=scenario in (1, 3, 4), bottom=scenario in (2, 3)),
        **{offset(ANCHOR, direction, n): "minecraft:stone"
           for n in range(1, 10) if (scenario, n) != (3, 2)},
        offset(ANCHOR, direction, -1): "minecraft:dirt",
        offset(ANCHOR, direction, -2): "minecraft:smooth_stone",
        beside: chassis(axis, top=scenario == 4),
        offset(beside, direction): "minecraft:oak_planks",
        across: chassis("xyz"[AXES.index(face)]),
        offset(across, direction): "minecraft:bricks",
    }
    return build, beside, bearing, motor, "south" if direction == AXES[1] else "up"


def property_value(state, key):
    return re.search(rf"\b{key}=([a-z]+)", state)[1]


def measure(control, scenario, expected_payload):
    build, beside, bearing, motor, facing = setup(scenario)
    control.commands((
        *(f"/setblock {coordinates(pos)} {state}" for pos, state in build.items()),
        f"/setblock {coordinates(bearing)} create:mechanical_bearing[facing={facing}]",
        f"/setblock {coordinates(motor)} create:creative_motor[facing={facing}]{{ScrollValue:0}}",
    ))
    for _ in range(2):
        control.step_to(control.clock() + 1)
    state = control.call("block", *ANCHOR)["state"]
    secondary = control.call("block", *beside)["state"]
    # Java uses maxChassisRange / 2 by default. The ninth block on the relevant
    # configurations is present in the initial build and checked after capture.
    configuration = [str(scenario), "configuration",
                     *(property_value(state, key) for key in ("axis", "sticky_top", "sticky_bottom")),
                     property_value(secondary, "sticky_top"), "8", "-"]
    control.command(f"/data merge block {coordinates(motor)} {{ScrollValue:16}}")
    for _ in range(3):
        control.step_to(control.clock() + 1)
        if "create:linear_chassis" in control.command(f"/data get block {coordinates(bearing)} MovedBlocks"):
            break
    actual = moved_payload(control, bearing, expected_payload)
    check_removed(control, ANCHOR, scenario, build, expected_payload)
    return configuration, [str(scenario), "capture", "-", "-", "-", "-", "-", actual]


def moved_payload(control, bearing, expected_payload):
    size = len(expected_payload.split("|"))
    fields = control.commands(
        f"/data get block {coordinates(bearing)} MovedBlocks[{index}].{path}"
        for index in range(size + 1)
        for path in ("Pos", "BlockState.Name")
    )
    if "no elements matching" not in fields[-1].lower():
        raise RuntimeError(f"Unexpected additional payload after {size} blocks: {fields[-2:]}")
    actual = []
    for pos, name in zip(fields[0:-2:2], fields[1:-2:2], strict=True):
        relative = re.search(r"\[I;\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\]", pos)
        block = re.search(r'"([a-z_]+:[a-z_]+)"$', name)
        if relative is None or block is None:
            raise RuntimeError(f"Missing assembled block: {pos!r}, {name!r}")
        actual.append(":".join(relative.groups()) + "=" + block[1])
    return "|".join(sorted(actual))


def check_removed(control, anchor, scenario, build, expected_payload):
    expected_removed = {tuple(int(n) for n in key.split("=")[0].split(":"))
                        for key in expected_payload.split("|")}
    for pos, state in build.items():
        relative = tuple(n - root for n, root in zip(pos, anchor, strict=True))
        expected = AIR if relative in expected_removed else state.split("[")[0]
        observed = control.call("block", *pos)["block"]
        if expected != observed:
            raise RuntimeError(f"Scenario {scenario}, at {pos}: Java left {expected}, Horizon left {observed}.")


def run(args):
    with (ROOT / "fixtures/linear-chassis-java.csv").open() as file:
        reader = csv.reader(file)
        if next(reader) != list(FIELDS):
            raise RuntimeError("Unexpected Java trace columns.")
        expected = tuple(reader)
    rows = []
    for before, after in zip(expected[::2], expected[1::2], strict=True):
        scenario = int(before[0])
        with fixture_world(args, f"linear-chassis-{scenario}", pack=args.pack) as control:
            control.command("/tp @s 10.5 180 42.5")
            rows.extend(measure(control, scenario, after[-1]))
    out = ROOT / ".local/linear-chassis-horizon.csv"
    with out.open("w") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows(rows)
    for actual, java in zip(rows, expected, strict=True):
        if actual != java:
            raise RuntimeError(f"Linear Chassis scenario {java[0]} {java[1]} differed. Java {java}, Horizon {actual}.")
    print(f"Linear Chassis axes, sticky properties and captured block positions matched all {len(rows) // 2} Java assemblies.")



def timing(args):
    anchor, cargo, bearing, motor = (8, 190, 24), (9, 190, 24), (8, 189, 24), (8, 188, 24)
    with (ROOT / "fixtures/linear-chassis-timing-java.csv").open() as file:
        source = csv.reader(file)
        header, *expected = source
    actual = []
    with fixture_world(args, "linear-chassis-timing", pack=args.pack) as control:
        control.commands((
            "/tp @s 10.5 190 26.5",
            f"/setblock {coordinates(anchor)} {chassis('x', top=True)}",
            f"/setblock {coordinates(cargo)} minecraft:bricks",
            f"/setblock {coordinates(bearing)} create:mechanical_bearing[facing=up]",
            f"/setblock {coordinates(motor)} create:creative_motor[facing=up]{{ScrollValue:0}}",
        ))
        start = control.clock()
        for row in expected:
            tick = int(row[0])
            if tick:
                control.step_to(start + tick)
            data = control.command(f"/data get block {coordinates(bearing)}")
            running = re.search(r"\bRunning: 1[b,}]", data) is not None
            moved = len(re.findall(r"\bBlockState:", data))
            states = [control.call("block", *pos)["block"] for pos in (anchor, cargo)]
            actual.append([str(tick), str(running).lower(), str(moved),
                           *(str(state == AIR).lower() for state in states)])
            if tick in (3, 12):
                speed = 16 if tick == 3 else 0
                control.command(f"/data merge block {coordinates(motor)} {{ScrollValue:{speed}}}")
    out = ROOT / ".local/linear-chassis-timing-horizon.csv"
    with out.open("w") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    mismatches = [(java, horizon) for java, horizon in zip(expected, actual, strict=True)
                  if java != horizon]
    if mismatches:
        raise RuntimeError(f"Linear Chassis assembly timing differed (Java, Horizon): {mismatches}.")
    print(f"Linear Chassis capture, payload count, and restoration matched all {len(actual)} Java ticks.")


def configure(args):
    with (ROOT / "fixtures/linear-chassis-placement-java.csv").open() as file:
        axes = {row["case"]: row["axis"] for row in csv.DictReader(file)}
    with (ROOT / "fixtures/linear-chassis-adhesive-java.csv").open() as file:
        adhesive = tuple(csv.DictReader(file))
    with fixture_world(args, "linear-chassis-placement", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 5 179 36 14 179 43 minecraft:smooth_stone",
            "/setblock 7 180 39 minecraft:oak_planks",
            "/setblock 8 181 42 minecraft:smooth_stone",
            "/item replace entity @s hotbar.0 with create:linear_chassis 3",
            "/item replace entity @s hotbar.1 with minecraft:slime_ball 2",
            "/gamemode survival",
        ))
        control.call("select", CHASSIS)

        def check(pos, axis, top="false", bottom="false"):
            state = control.call("block", *pos)["state"]
            properties = {"axis": axis, "sticky_top": top, "sticky_bottom": bottom}
            if not state.startswith(CHASSIS + "[") or any(
                property_value(state, key) != value for key, value in properties.items()
            ):
                raise RuntimeError(f"At {pos}, Java had {properties}, Horizon had {state}.")

        main = (8, 180, 39)
        above = (8, 181, 39)
        control.command("/tp @s 10.5 180 39.5 90 20")
        control.call("wait", 2)
        control.call("interact", 7, 180, 39, "east")
        check(main, axes["look"])

        control.command("/tp @s 8.5 182 42.1 180 55")
        control.call("wait", 2)
        control.call("interact", *main, "up")
        check(above, axes["inherit"])
        control.command("/setblock 8 181 39 minecraft:air")
        control.call("wait", 3)
        control.call("key", "shift", "down")
        try:
            control.call("interact", *main, "up")
        finally:
            control.call("key", "shift", "up")
        check(above, axes["sneak"])
        control.command("/setblock 8 181 39 minecraft:air")

        control.call("select", "minecraft:slime_ball")
        control.command("/tp @s 10.5 180 39.5 90 20")
        control.call("wait", 2)
        events = {
            1: "/setblock 7 180 39 " + chassis("x"),
            2: "/setblock 7 180 39 minecraft:air",
            3: "/setblock 7 180 39 " + chassis("x"),
            4: "/setblock 9 180 39 " + chassis("z"),
            5: "/setblock 9 180 39 minecraft:air",
        }
        for row in adhesive:
            step = int(row["step"])
            if step in events:
                control.command(events[step])
            if step <= 2:
                control.call("interact", *main, "east")
            if step == 6:
                control.command("/item replace entity @s hotbar.2 with minecraft:air")
                selection = control.call("select", 3)
                if selection.get("held"):
                    raise RuntimeError(f"Expected an empty acting hand, got {selection}.")
                control.call("key", "shift", "down")
                try:
                    control.call("wait", 4)
                    control.call("look-at", 9, 180.5, 39.5)
                    control.call("mouse", "right", "click")
                    control.call("wait", 3)
                finally:
                    control.call("key", "shift", "up")
            check(main, axes["look"], row["sticky_top"], row["sticky_bottom"])
            counts = control.call("inventory")["counts"]
            if counts.get("minecraft:slime_ball") != int(row["slimeball_count"]):
                raise RuntimeError(f"Slimeball count differed from Java on adhesive step {step}: {counts}.")
        if control.call("inventory")["counts"].get(CHASSIS, 0):
            raise RuntimeError("Survival placement did not consume all three chassis blocks.")
    print(f"Linear Chassis matched {len(axes)} Java placement cases and {len(adhesive)} adhesive steps.")


def secondary_assemblies(args):
    anchor = (8, 184, 40)
    end = offset(anchor, AXES[0])
    bearing = offset(anchor, AXES[1], -1)
    motor = offset(anchor, AXES[1], -2)
    with (ROOT / "fixtures/secondary-linear-chassis-java.csv").open() as file:
        data = csv.reader(file)
        header, *expected = data
    actual = []
    for before, moving, after in zip(expected[::3], expected[1::3], expected[2::3], strict=True):
        scenario = int(before[0])
        seed, mixed = (CHASSIS, SECONDARY) if scenario < 3 else (SECONDARY, CHASSIS)
        forward = seed if scenario % 3 == 1 else mixed
        build = {
            anchor: chassis("x", top=scenario % 3 != 0, kind=seed),
            end: chassis("x", top=True, kind=forward),
            offset(end, AXES[0]): "minecraft:bricks",
            offset(anchor, AXES[2]): chassis("x", kind=mixed),
            offset(end, AXES[2]): chassis("x", kind=forward),
            offset(offset(end, AXES[2]), AXES[0]): "minecraft:oak_planks",
        }
        with fixture_world(args, f"secondary-linear-chassis-{scenario}", pack=args.pack) as control:
            control.commands((
                "/tp @s 11.5 184 43.5",
                *(f"/setblock {coordinates(pos)} {state}" for pos, state in build.items()),
                f"/setblock {coordinates(bearing)} create:mechanical_bearing[facing=up]",
                f"/setblock {coordinates(motor)} create:creative_motor[facing=up]{{ScrollValue:0}}",
            ))
            for _ in range(2):
                control.step_to(control.clock() + 1)
            initial = {pos: control.call("block", *pos)["state"] for pos in build}
            start = control.clock()
            actual.append([str(scenario), "0", *(property_value(initial[pos], "sticky_top")
                                                  for pos in (anchor, end)), "-"])
            control.command(f"/data merge block {coordinates(motor)} {{ScrollValue:16}}")
            control.step_to(start + 1)
            payload = moved_payload(control, bearing, moving[-1])
            check_removed(control, anchor, scenario, build, moving[-1])
            actual.append([str(scenario), "1", "-", "-", payload])
            control.command(f"/data merge block {coordinates(motor)} {{ScrollValue:0}}")
            control.step_to(start + 2)
            replies = control.commands(
                f"/execute if block {coordinates(pos)} {state}" for pos, state in initial.items()
            )
            differences = {pos: (state, reply) for (pos, state), reply in zip(initial.items(), replies, strict=True)
                           if "Test passed" not in reply}
            if differences:
                bearing_data = control.command(f"/data get block {coordinates(bearing)}")
                raise RuntimeError(f"Secondary chassis case {scenario} restoration differed: {differences}. "
                                   f"Bearing state: {bearing_data}")
            actual.append([str(scenario), "2", *(property_value(initial[pos], "sticky_top")
                                                  for pos in (anchor, end)), "-"])
    out = ROOT / ".local/secondary-linear-chassis-horizon.csv"
    with out.open("w") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    for java, horizon in zip(expected, actual, strict=True):
        if java != horizon:
            raise RuntimeError(f"Secondary chassis assembly differed (Java, Horizon): {java}, {horizon}.")
    print(f"Secondary chassis matched {len(actual)} Java ticks across {len(actual) // 3} bearing assemblies.")


def secondary_player(args):
    with (ROOT / "fixtures/secondary-linear-chassis-placement-java.csv").open() as file:
        placements = tuple(csv.DictReader(file))
    with (ROOT / "fixtures/secondary-linear-chassis-adhesive-java.csv").open() as file:
        adhesive = tuple(csv.DictReader(file))
    with fixture_world(args, "secondary-linear-chassis-player", render=True, pack=args.pack) as control:
        main, above, east = (8, 184, 40), (8, 185, 40), (9, 184, 40)
        control.commands((
            "/fill 5 183 37 13 183 44 minecraft:smooth_stone",
            "/setblock 8 185 43 minecraft:smooth_stone",
            "/tp @s 8.5 186 43.1 180 55",
            f"/item replace entity @s hotbar.0 with {CHASSIS}",
            f"/item replace entity @s hotbar.1 with {SECONDARY} 3",
            "/item replace entity @s hotbar.2 with minecraft:slime_ball 2",
            "/gamemode survival",
        ))
        for expected in placements:
            case = int(expected["case"])
            held = CHASSIS if case == 2 else SECONDARY
            support = SECONDARY if case >= 2 else CHASSIS
            control.command(f"/setblock {coordinates(main)} {chassis('x', kind=support)}")
            control.call("select", held)
            control.call("wait", 3)
            if case == 1:
                control.call("key", "shift", "down")
            try:
                control.call("interact", *main, "up")
            finally:
                if case == 1:
                    control.call("key", "shift", "up")
            actual = control.call("block", *above)["state"]
            if not actual.startswith(held + "[") or property_value(actual, "axis") != expected["axis"]:
                raise RuntimeError(f"Secondary chassis placement case {case} differed: {actual}.")
            control.command(f"/setblock {coordinates(above)} minecraft:air")

        counts = control.call("inventory")["counts"]
        if counts.get(CHASSIS) or counts.get(SECONDARY):
            raise RuntimeError(f"Survival chassis placements left unconsumed items: {counts}.")
        control.command(f"/setblock {coordinates(main)} {chassis('x', kind=SECONDARY)}")
        control.command("/tp @s 5.5 184 40.5 -90 20")
        control.call("select", "minecraft:slime_ball")
        control.call("wait", 3)
        neighbors = (AIR, chassis("x", kind=SECONDARY), chassis("x"),
                     chassis("x", kind=SECONDARY), chassis("x"))
        for row in adhesive:
            step = int(row["step"])
            control.command(f"/setblock {coordinates(east)} {neighbors[step]}")
            if step < 3:
                control.call("interact", *main, "west")
            state = control.call("block", *main)["state"]
            counts = control.call("inventory")["counts"]
            if any(property_value(state, key) != row[key] for key in ("sticky_top", "sticky_bottom")):
                raise RuntimeError(f"Secondary chassis adhesive step {step} differed: {state}.")
            if counts.get("minecraft:slime_ball") != int(row["slimeball_count"]):
                raise RuntimeError(f"Secondary chassis adhesive step {step} had differing inventory: {counts}.")
    print(f"Secondary chassis matched {len(placements)} Java placement cases and {len(adhesive)} adhesive steps.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--configure", action="store_true")
    modes.add_argument("--timing", action="store_true")
    modes.add_argument("--secondary", action="store_true")
    modes.add_argument("--secondary-player", action="store_true")
    args = parser.parse_args()
    if args.secondary:
        secondary_assemblies(args)
    elif args.secondary_player:
        secondary_player(args)
    elif args.configure:
        configure(args)
    elif args.timing:
        timing(args)
    else:
        run(args)
