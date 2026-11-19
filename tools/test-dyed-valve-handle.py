#!/usr/bin/env python3
"""Check original dyed Valve recoloring, paired power retention, and draw motion."""
import argparse
import csv
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
from math import isclose
from pathlib import Path
import time
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world

base_spec = spec_from_file_location("valve_fixture", ROOT / "tools/test-copper-valve-handle.py")
valve = module_from_spec(base_spec)
base_spec.loader.exec_module(valve)
craft_spec = spec_from_file_location("survival_crafting", ROOT / "tools/test-survival-crafting.py")
crafting = module_from_spec(craft_spec)
craft_spec.loader.exec_module(crafting)
PRIMARY = (8, 101, -10)
LINKS = {7: (8, 101, -13), 12: (8, 101, -16), 17: (8, 101, -19)}
ALL = (PRIMARY, *LINKS.values())
TABLE = (8, 101, -6)


def reference(name):
    with (ROOT / f"fixtures/dyed-valve-handle-{name}-java.csv").open() as source:
        _, *rows = csv.reader(source)
        return rows


def shaft(pos):
    return pos[0] - 1, pos[1], pos[2]


def aim(control, pos):
    x, y, z = pos
    control.command(f"/tp @s {x + 3.5} {y}.000 {z + 0.5}")
    control.call("wait", 2)
    valve.point_at(control, pos)


def tap(control):
    control.call("script", script="mouse right down\nwait 2\nmouse right up\nwait 3\n")
    if control.call("state")["screen"] != "playing":
        raise RuntimeError("A short valve tap opened the advanced board.")


def recolor(control, pos, color):
    item = f"minecraft:{color}_dye"
    control.command(f"/item replace entity @s hotbar.0 with {item} 3")
    for _ in range(20):
        if control.call("inventory")["counts"].get(item) == 3:
            break
        control.call("wait", 1)
    else:
        raise RuntimeError(f"The player did not receive the three {item} items.")
    control.call("select", item)
    aim(control, pos)
    tap(control)
    count = control.call("inventory")["counts"].get(f"minecraft:{color}_dye", 0)
    actual = control.call("block", *pos)["state"]
    return actual, count


def data(control, positions):
    commands = [f"/data get block {valve.coord(pos)}" for pos in positions]
    values = control.commands(commands)
    return dict(zip(positions, values, strict=True))


def power_state(by_pos, pos):
    handle = by_pos[pos]
    rear = by_pos.get(shaft(pos), "")
    return (valve.tag(handle, "InUse"), valve.tag(handle, "Speed"), valve.tag(rear, "Speed"),
            valve.tag(handle, "Capacity"), valve.tag(handle, "Stress"))


def assert_frame(control, *, tick, in_use, expected):
    log = control.socket.parent / "ctl.log"
    end = time.monotonic() + 4
    actual = None
    while time.monotonic() < end:
        text = log.read_text()
        for line in text.splitlines():
            if not line.startswith(f"CREATE_VALVE_FRAME {tick},{in_use},"):
                continue
            _, _, partial, zero, angle, vertices = line.split(" ", 1)[1].split(",")
            actual = (float(partial), float(zero), float(angle), int(vertices))
            sample_partial, base, rotation, count = actual
            goal_base, goal_end = expected
            goal_partial = goal_base + (goal_end - goal_base) * sample_partial
            if count > 0 and isclose(base, goal_base, abs_tol=0.00004) and isclose(rotation, goal_partial, abs_tol=0.00006):
                return
        time.sleep(0.04)
    raise RuntimeError(f"Valve angle frame {tick=} {in_use=} expected {expected}, most recent {actual}.")


def verify_assets(pack):
    with ZipFile(pack or ROOT / ".local/create.hmod") as archive:
        for relative, expected in reference("assets"):
            if hashlib.sha256(archive.read(relative)).hexdigest() != expected:
                raise RuntimeError(f"Changed Java asset {relative}.")


def prepare_world(control):
    setup = [
        "/fill 2 100 -24 15 100 -4 minecraft:smooth_stone",
        "/fill 4 101 -23 14 104 -5 minecraft:air",
        "/gamemode survival",
    ]
    for pos in ALL:
        support = "minecraft:stone" if pos == LINKS[12] else "create:shaft[axis=x]"
        setup.extend((
            f"/setblock {valve.coord(shaft(pos))} {support}",
            f"/setblock {valve.coord(pos)} create:copper_valve_handle[facing=east,waterlogged=true]",
        ))
    control.commands(setup)
    control.call("wait", 2)


def verify(args):
    color_rows = reference("dye")
    state_rows = reference("state")
    motion_rows = reference("visual")
    link_rows = reference("link")
    repeats = reference("repeat")
    assert (len(color_rows), len(motion_rows), len(link_rows), len(repeats)) == (16, 17, 255, 1)
    verify_assets(args.pack)
    colors = {int(row[0]): row[1:] for row in color_rows}
    states = {int(row[0]): row[1:] for row in state_rows}
    motion = {int(row[0]): row[1:] for row in motion_rows}
    links = {}
    for tick, z, remaining, rotor, output, _generated, _first, _second, capacity, stress in link_rows:
        links.setdefault(int(tick), {})[LINKS[int(z)]] = tuple(map(float, (remaining, rotor, output, capacity, stress)))
    env = {"CREATE_VALVE_TRACE": ",".join(map(str, PRIMARY))}
    if args.frames:
        args.frames.mkdir(parents=True, exist_ok=True)
    with fixture_world(args, "DyedValve", render=True, pack=args.pack, env=env) as control:
        prepare_world(control)
        control.step_to(control.clock() + 1)
        start = control.clock() - 1
        control.commands(f"/data merge block {valve.coord(pos)} {{ScrollValue:-137}}" for pos in ALL)
        control.step_to(start + 2)
        for pos in ALL:
            aim(control, pos)
            tap(control)
        aim(control, PRIMARY)
        _, at_start, _, at_end, remaining = motion[2]
        assert_frame(control, tick=start + 2, in_use=int(remaining),
                     expected=(float(at_start), float(at_end)))
        positions = [*ALL, *(shaft(pos) for pos in ALL if pos != LINKS[12])]
        diffs = []
        for tick in range(3, 87):
            control.step_to(start + tick)
            if tick == 5:
                for pos in (LINKS[7], LINKS[12]):
                    actual, count = recolor(control, pos, "white")
                    if actual != "create:white_valve_handle[facing=east,waterlogged=true]" or count != 3:
                        raise RuntimeError(f"Single-dye case failed: {actual} with {count} dyes left.")

            before = data(control, positions)
            for pos, wanted in links[tick].items():
                got = power_state(before, pos)
                if got != wanted:
                    diffs.append((tick, pos, wanted, got))
            if tick in states:
                remaining, speed, output, _, cooldown = map(float, states[tick])
                nbt = before[PRIMARY]
                got = (*power_state(before, PRIMARY)[:3], valve.tag(nbt, "Cooldown"))
                if got != (remaining, speed, output, cooldown):
                    diffs.append((tick, "primary", (remaining, speed, output, cooldown), got))

            if tick in colors:
                color, name, facing, wet, qty, _same_entity, angle, remaining, target, speed, output, _base_capacity = colors[tick]
                actual, count = recolor(control, PRIMARY, color)
                wanted = f"{name}[facing={facing},waterlogged={wet}]"
                after = data(control, [PRIMARY, shaft(PRIMARY)])
                state = after[PRIMARY]
                got = (
                    actual, count,
                    valve.tag(state, "ScrollValue"),
                    valve.tag(state, "InUse"), valve.tag(state, "TargetAngle"),
                    valve.tag(state, "Speed"), valve.tag(after[shaft(PRIMARY)], "Speed"),
                )
                expected = (wanted, int(qty), *map(float, (angle, remaining, target, speed, output)))
                if got != expected:
                    diffs.append((tick, color, expected, got))
                _, at_start, _, at_end, remaining = motion[tick]
                assert_frame(control, tick=start + tick, in_use=int(remaining),
                             expected=(float(at_start), float(at_end)))
                if args.frames and tick in (3, 10, 17):
                    control.call("screenshot", str(args.frames / f"valve-{color}.png"))

            if tick == 25:
                actual, count = recolor(control, PRIMARY, "black")
                state = data(control, [PRIMARY])[PRIMARY]
                got = count, valve.tag(state, "InUse"), valve.tag(state, "ScrollValue"), valve.tag(state, "Speed")
                expected = tuple(map(float, repeats[0][1:]))
                if got != expected:
                    diffs.append((tick, "repeat black", expected, got))
        if diffs:
            raise RuntimeError(f"{len(diffs)} Java differences, first 12: {diffs[:12]}")
    print("All 16 dye interactions and 252 paired, stone-supported and unchanged link samples matched Java.")
    print("The original render angle and sub-tick interpolation matched for all 17 active samples.")


def verify_crafting(args):
    colors = [row[1] for row in reference("dye")]
    cases = [
        ("create:copper_valve_handle", "create:black_valve_handle", None),
        *( (f"create:{color}_valve_handle", "create:copper_valve_handle", f"minecraft:{color}_dye")
           for color in colors),
    ]
    with fixture_world(args, "DyedValveCraft", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 5 100 -10 12 100 -4 minecraft:smooth_stone",
            f"/setblock {valve.coord(TABLE)} minecraft:crafting_table",
            "/tp @s 6.2 101 -5.5",
            "/gamemode survival",
        ))
        control.call("wait", 3)
        for wanted, handle, dye in cases:
            control.call("command", "/clear @s")
            control.command(f"/item replace entity @s hotbar.0 with {handle}")
            if dye:
                control.command(f"/item replace entity @s hotbar.1 with {dye}")
            control.call("wait", 2)
            control.call("interact", *TABLE, "west")
            control.call("wait", 3)
            crafting.distribute(control, 0, (100,))
            if dye:
                crafting.distribute(control, 1, (101,))
            crafting.craft(control, wanted, 1)
            control.call("wait", 2)
            control.call("close")
    print(f"All {len(cases)} Java valve recoloring and copper conversion recipes worked in survival.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--frames", type=Path)
    parser.add_argument("--craft", action="store_true")
    args = parser.parse_args()
    (verify_crafting if args.craft else verify)(args)


if __name__ == "__main__":
    main()
