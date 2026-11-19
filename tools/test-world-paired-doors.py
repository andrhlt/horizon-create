#!/usr/bin/env python3
"""Compare real manual inputs on two freestanding paired Create doors."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from math import cos, isclose, pi, radians, sin
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

nozzle = import_module("test-nozzle")
multiplayer = import_module("test-multiplayer")
GUEST = "WorldDoorGuest"
PROPERTIES = ("open", "visible", "powered")
FOLDING = ("andesite_door", "copper_door")
SLIDING = ("brass_door", "train_door", "framed_glass_door")
ENV = {"HORIZON_NO_AUDIO": "1", "HORIZON_CREATE_TEST_AUDIO": "1",
       "HORIZON_CREATE_ELEVATOR_TRACE": "1"}


def place_pair(world, material, x, y, z):
    world.command(f"/fill {x-1} {y-1} {z-1} {x+2} {y-1} {z+3} minecraft:stone")
    positions = [(x + dx, y + dy, z) for dx in range(2) for dy in range(2)]
    for index, pos in enumerate(positions):
        hinge = "left" if index < 2 else "right"
        half = "lower" if index % 2 == 0 else "upper"
        world.command(f"/setblock {nozzle.xyz(pos)} create:{material}[facing=north,hinge={hinge},half={half}]")
    return positions


def sample(world, positions, material):
    states = [nozzle.state(world, pos) for pos in positions]
    assert all(state.startswith(f"create:{material}[") for state in states), states
    return tuple("".join("1" if f"{key}=true" in state else "0" for state in states)
                 for key in PROPERTIES)


def click(world, actor, pos, closing):
    x, y, z = pos
    feet = (x+.25, y, z+2.5)
    entity = "@s" if actor is world else GUEST
    world.command(f"/tp {entity} {nozzle.xyz(feet)}")
    multiplayer.until("the door player to reach the target", lambda:
                      actor.call("state")["player"]["position"] == list(feet))
    target = (x + (.08 if closing else .5), y + .75, z + .88)
    nozzle.aim(actor, target, pos)
    actor.call("mouse", "right", "click")
    actor.call("wait", 2)


def join(args, world, stack, material, env):
    port = world.call("lan", "open", 0, "commands")["port"]
    scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-world-door-")))
    actor = stack.enter_context(multiplayer.joined_client(
        args, scratch, f"127.0.0.1:{port}", GUEST,
        render=True, scenario=f"world-door-{material}", pack=args.pack,
        env=env))
    multiplayer.until("the door guest to join", lambda: any(
        row["name"] == GUEST and row["placed"] for row in world.call("lan", "status")["guests"]))
    return actor


def cues(actor, marker):
    log = actor.socket.parent / "ctl.log"
    if not log.exists():
        return []
    return [line.partition(marker)[2].split(",") for line in log.read_text().splitlines()
            if marker in line and "minecraft:block.iron_door." in line]


def verify_sounds(world, actor, start, positions, expected):
    def position_of(row):
        return tuple(value + .5 for value in positions[int(row["half"])])

    def compare(actual, authority):
        wanted = {}
        for row in expected:
            key = (row["sound"], position_of(row))
            wanted[key] = int(row["tick"]), float(row["volume"])
        assert len(actual) == len(wanted), (actual, wanted)
        for row in actual:
            if authority:
                tick, sound, *values = row
            else:
                sound, source, *values = row
                assert source == "4", row
            x, y, z, volume, pitch = map(float, values)
            tick_expected, volume_expected = wanted.pop((sound, (x,y,z)))
            if authority:
                assert int(tick) - start == tick_expected, (row, tick_expected, start)
            assert abs(volume - volume_expected) < 1e-6, row
            assert .9 <= pitch <= 1.0 if sound.endswith(".open") else pitch == 1.0, row

    compare(cues(world, "CREATE_ELEVATOR_SOUND "), True)
    for listener in dict.fromkeys((world, actor)):
        marker = "CREATE_ELEVATOR_PLAYBACK "
        multiplayer.until("door cues to reach the listener", lambda:
                          len(cues(listener, marker)) >= len(expected))
        compare(cues(listener, marker), False)


def verify_authority_sample(world, positions, material, expected):
    commands = []
    for index, pos in enumerate(positions):
        properties = ",".join(f"{key}={'true' if bits[index] == '1' else 'false'}"
                              for key, bits in zip(PROPERTIES, expected, strict=True))
        commands.append(f"/execute if block {nozzle.xyz(pos)} create:{material}[{properties}]")
    answers = world.commands(commands)
    assert all("Test passed" in answer for answer in answers), (material, expected, answers)


def verify_outline(world, actor, row):
    x, y, z = 8 + float(row["x"]), 170, 8
    feet = (x, y, z - 1.5)
    who = "@s" if actor is world else GUEST
    world.command(f"/tp {who} {nozzle.xyz(feet)}")
    multiplayer.until("the outline viewer at the ray origin", lambda:
                      actor.call("state")["player"]["position"] == list(feet))
    actor.call("look-at", x, y + 1.62, z + 2.5)
    result = actor.call("looking-at").get("block") or {}
    hit = result.get("pos") == [8, y + 1, z]
    if hit != (row["hit"] == "true"):
        raise AssertionError((row, result))
    if hit:
        assert result["face"] == row["face"], (row, result)
        assert isclose(result["point"][2] - z, float(row["z"]), abs_tol=1e-6), (row, result)


def trace_rows(log, marker, count):
    if not log.exists():
        return
    for line in log.read_text().splitlines(keepends=True):
        if marker not in line or not line.endswith("\n"):
            continue
        fields = line.partition(marker)[2].rstrip().split(",")
        if len(fields) == count:
            yield fields


def drawn_samples(actor, material, start):
    log = actor.socket.parent / "ctl.log"
    marker = f"CREATE_WORLD_DOOR_DRAW create:{material},"
    result = {}
    for fields in trace_rows(log, marker, 6):
        tick, x, y, z, previous, current = fields
        if int(y) == 170 and int(z) == 8 and int(x) in (8,9):
            result[(int(tick) - start, int(x) - 8)] = (float(previous), float(current))
    return result


def java_fold_transform(progress, right, lower):
    # Evaluate the north-facing Java SlidingDoorRenderer matrix at the
    # submitted interpolation fraction. Static JOML samples validate this.
    flip = -1 if right else 1
    base = pi / 2
    first = radians(91 * flip * progress * progress)
    yaw = base + first - (0 if lower else radians(181 * flip * progress * progress))

    def rotate(x, z, angle):
        return x * cos(angle) + z * sin(angle), z * cos(angle) - x * sin(angle)

    center_x, center_z = rotate(.5, .5, base)
    shifts = (rotate(0, int(right), base),
              rotate(0, 0 if lower else flip / 2, base + first),
              rotate(0, -.5 if right else 0, yaw))
    x = .5 - center_x + sum(dx for dx, _ in shifts)
    z = .5 - center_z - min(10 * progress, 1) / 32 + sum(dz for _, dz in shifts)
    return (x, -1 / 512, z), (sin(yaw / 2), cos(yaw / 2))


def java_slide_transform(progress, right, lower):
    direction = 1 if right else -1
    translation = (direction * progress * progress * 13 / 16,
                   0 if lower else 1 - 1 / 512, -min(10 * progress, 1) / 32)
    return translation, (0, 1)


def verify_transform(actual_shift, actual_rotation, expected, label):
    shift, rotation = expected
    assert all(isclose(a, e, abs_tol=2e-6)
               for a, e in zip(actual_shift, shift, strict=True)), (label, actual_shift, shift)
    sign = 1 if sum(a * e for a, e in zip(actual_rotation, rotation, strict=True)) >= 0 else -1
    assert all(isclose(sign * a, e, abs_tol=2e-6)
               for a, e in zip(actual_rotation, rotation, strict=True)), (label, actual_rotation, rotation)


def verify_java_transform_formula():
    with (ROOT / "fixtures/train-folding-door-animation-java.csv").open() as handle:
        for row in csv.DictReader(handle):
            if row["facing"] != "north":
                continue
            right = row["hinge"] == "right"
            lower = row["half"] == "lower"
            expected = java_fold_transform(float(row["progress"]), right, lower)
            verify_transform([float(row[key]) for key in ("x", "y", "z")],
                             [float(row[key]) for key in ("qy", "qw")], expected, row)


def verify_java_slide_formula():
    with (ROOT / "fixtures/train_door_animation-java.csv").open() as handle:
        for row in csv.DictReader(handle):
            (x, _, z), _ = java_slide_transform(float(row["progress"]), True, True)
            assert isclose(x, float(row["slide"]), abs_tol=2e-6), row
            assert isclose(-z, float(row["normal"]), abs_tol=2e-6), row


def verify_panels(actor, material, start, reference, strict_frames):
    log = actor.socket.parent / "ctl.log"
    marker = f"CREATE_WORLD_DOOR_PANEL create:{material},"
    expected = {(int(row["tick"]), int(row["leaf"])):
                (float(row["previous"]), float(row["current"])) for row in reference
                if 3 <= int(row["tick"]) < 20}
    samples = {}
    unsynchronized = set()
    for fields in trace_rows(log, marker, 16):
        tick, x, y, z, open_state, lower, pane, partial, tx, ty, tz, sin_y, cos_y, vertices, before, after = fields
        offset, leaf = int(tick) - start, int(x) - 8
        if int(y) != 170 or int(z) != 8 or (offset, leaf) not in expected:
            continue
        if (open_state == "true") != (offset < 13):
            continue
        lower = lower == "true"
        right = leaf == 1
        if material in FOLDING:
            expected_pane = "left" if lower ^ right else "right"
            transform = java_fold_transform
        else:
            expected_pane = "lower" if lower else "upper"
            transform = java_slide_transform
        assert pane == expected_pane, (offset, leaf, lower, pane)
        assert int(vertices) > 0, (offset, leaf, lower, vertices)
        before, after = map(float, (before, after))
        progress = before + (after - before) * float(partial)
        verify_transform(tuple(map(float, (tx, ty, tz))), tuple(map(float, (sin_y, cos_y))),
                         transform(progress, right, lower), (offset, leaf, lower, partial))
        java_before, java_after = expected[offset, leaf]
        if isclose(before, java_before, abs_tol=1e-6) and isclose(after, java_after, abs_tol=1e-6):
            samples[offset, leaf, lower] = float(partial)
        else:
            unsynchronized.add((offset, leaf))
    missing = {(tick, leaf, lower) for tick, leaf in expected for lower in (False, True)} - samples.keys()
    assert not missing, (material, sorted(missing))
    if strict_frames:
        assert not unsynchronized, (material, sorted(unsynchronized))
    return len(samples), len(unsynchronized)


def verify_render(actor, material, start, reference):
    rendered = drawn_samples(actor, material, start)
    mismatches = []
    for row in reference:
        tick, leaf = int(row["tick"]), int(row["leaf"])
        if not 3 <= tick < 20:
            continue
        expected = (float(row["previous"]), float(row["current"]))
        actual = rendered.get((tick, leaf))
        if actual is None or any(abs(a - e) > 1e-6 for a, e in zip(actual, expected)):
            mismatches.append((tick, leaf, actual, expected))
    assert not mismatches, (material, mismatches)


def run(args):
    with (ROOT / "fixtures/world-paired-doors-java.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    with (ROOT / "fixtures/world-paired-doors-sound-java.csv").open() as handle:
        sounds = list(csv.DictReader(handle))
    env = ENV.copy()
    if args.outline:
        with (ROOT / "fixtures/world-paired-doors-outline-java.csv").open() as handle:
            outlines = list(csv.DictReader(handle))
    if args.render:
        env["HORIZON_CREATE_WORLD_DOOR_TRACE"] = "1"
        if args.sliding:
            verify_java_slide_formula()
        else:
            verify_java_transform_formula()
        with (ROOT / "fixtures/world-paired-doors-progress-java.csv").open() as handle:
            animation = list(csv.DictReader(handle))
    materials = SLIDING if args.sliding else FOLDING
    rows = [row for row in rows if row["material"] in materials]
    sounds = [row for row in sounds if row["material"] in materials]
    if args.outline:
        outlines = [row for row in outlines if row["material"] in materials]
    for material in materials:
        reference = [row for row in rows if row["material"] == material]
        if args.render:
            render_reference = [row for row in animation if row["material"] == material]
            expected_draws = {(int(row["tick"]), int(row["leaf"])):
                              (float(row["previous"]), float(row["current"]))
                              for row in render_reference}
        with ExitStack() as stack:
            scenario = f"WorldPairedDoor{material}{'Lan' if args.lan else 'Solo'}{'Render' if args.render else ''}"
            world = stack.enter_context(fixture_world(args, scenario, render=True, pack=args.pack, env=env))
            positions = place_pair(world, material, 8, 170, 8)
            actor = join(args, world, stack, material, env) if args.lan else world
            if args.lan:
                world.command("/tp @s 10.5 170 10.5")
                world.call("look-at", 9, 171, 8.8)
            if args.outline:
                who = GUEST if args.lan else "@s"
                world.command(f"/attribute {who} minecraft:gravity base set 0")
            start = world.clock()
            for offset, row in enumerate(reference):
                assert int(row["tick"]) == offset
                if offset:
                    world.step_to(start + offset)
                if offset in (3, 13):
                    click(world, actor, positions[0], closing=offset == 13)
                actual = sample(world, positions, material)
                expected = tuple(row[key] for key in PROPERTIES)
                if offset == 3 and args.baseline:
                    print(f"{material},{offset},{','.join(actual)}")
                    assert actual == ("1100", "1111", "0000"), (row, actual)
                    break
                if offset in (3, 13, 21) or actual != expected:
                    verify_authority_sample(world, positions, material, expected)
                    for viewer in dict.fromkeys((world, actor)):
                        multiplayer.until(f"viewer to see the doors at frozen tick {offset}", lambda:
                                          sample(viewer, positions, material) == expected)
                    assert world.clock() == start + offset
                    actual = sample(world, positions, material)
                print(f"{material},{offset},{','.join(actual)}")
                assert actual == expected, (row, actual)
                if args.outline:
                    for ray in outlines:
                        if ray["material"] == material and int(ray["tick"]) == offset:
                            verify_outline(world, actor, ray)
                if args.render and 3 <= offset < 20:
                    for viewer in dict.fromkeys((world, actor)):
                        def sampled_after_click():
                            samples = drawn_samples(viewer, material, start)
                            for leaf in (0, 1):
                                key = offset, leaf
                                if key not in samples:
                                    return False
                                if any(abs(a - e) > 1e-6 for a, e in zip(samples[key], expected_draws[key])):
                                    return False
                            return True

                        multiplayer.until(f"both leaves rendered at frozen tick {offset}", sampled_after_click)
            if not args.baseline:
                verify_sounds(world, actor, start, positions,
                              [row for row in sounds if row["material"] == material])
            if args.render:
                for viewer in dict.fromkeys((world, actor)):
                    verify_render(viewer, material, start, render_reference)
                    count, unsynchronized = verify_panels(
                        viewer, material, start, render_reference, args.strict_frames)
                    print(f"{material}: {count} synchronized panel samples matched Java geometry.")
                    if unsynchronized:
                        print(f"{material}: {unsynchronized} leaf-ticks also had an earlier unsynchronized frame.")
    if args.baseline:
        print("Reproduced one-leaf toggles and missing visibility transition on both baseline pairs.")
    else:
        result = f"All {len(rows)} Java state samples and {len(sounds)} sound cues matched"
        if args.outline:
            result += f", plus {len(outlines)} upper-panel outline rays"
        print(result + ".")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--outline", action="store_true")
    parser.add_argument("--strict-frames", action="store_true",
                        help="also fail on frames drawn before the viewer is synchronized")
    parser.add_argument("--sliding", action="store_true")
    run(parser.parse_args())
