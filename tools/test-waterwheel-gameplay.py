#!/usr/bin/env python3
"""Source-aligned wheel survival crafting, LAN materials and idle/active reopen.

Expected recipes and invariants come from Create ac0c444, not Rust output.
Exact flow timing remains covered by test-small-waterwheel and award traces.
"""

import argparse
from importlib import import_module
import json
import math
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

award = import_module("test-waterwheel-advancement")
crafting = import_module("test-survival-crafting")
multiplayer = award.multiplayer
GUEST = "WheelGuest"


def advance(world, ticks):
    for _ in range(ticks):
        world.step_to(world.clock() + 1)


def coords(pos):
    return " ".join(map(str, pos))


def click_face(world, target, point, face, item, *, sneak=False):
    """Make a real ray-cast click after proving its setup matches the case."""
    world.call("look-at", *point)
    world.call("wait", 2)
    if sneak:
        world.call("key", "shift", "down")
        world.call("wait", 1)
    hit = world.call("looking-at")
    block = hit.get("block") or {}
    if hit.get("kind") != "block" or block.get("pos") != list(target) or block.get("face") != face:
        raise RuntimeError(f"Expected ray hit {target} face {face}, got {hit}")
    player = world.call("state")["player"]
    held = (world.call("inventory").get("held") or {}).get("item")
    # Check reach from eye height to the actual ray intersection.
    distance = sum((float(player["eye"][i]) - block["point"][i]) ** 2 for i in range(3)) ** .5
    if distance > 4.5:
        raise RuntimeError(f"Ray target is beyond survival reach ({distance:.2f} blocks): {hit}")
    if held != item:
        raise RuntimeError(f"Expected {item} in main hand before placement, got {held}")
    try:
        if player["sneaking"] != sneak:
            raise RuntimeError(f"Expected sneak={sneak}, actual player state={player}")
        world.call("mouse", "right", "click")
    finally:
        if sneak:
            world.call("key", "shift", "up")
    print(f"placement input: target={target} face={face} reach={distance:.2f} held={held} "
          f"sneak={player['sneaking']} yaw={player['yaw']:.1f} pitch={player['pitch']:.1f}", flush=True)


def numeric(world, pos, field):
    reply = world.command(f"/data get block {coords(pos)} {field}")
    match = re.search(r"block data: (-?\d+(?:\.\d+)?)[fb]?\b", reply)
    if match is None:
        raise RuntimeError(f"Missing {field} at {pos}: {reply}")
    return float(match[1])


def material_name(world, pos):
    material = world.command(f"/data get block {coords(pos)} Material")
    match = re.search(r'Name: "([^"]+)"', material)
    # The port stores its source-default spruce implicitly until first use.
    if match is None and "Found no elements matching Material" in material:
        return "minecraft:spruce_planks"
    if match is None:
        raise RuntimeError(f"Missing wheel Material: {material}")
    return match[1]


def snapshot(world, pos):
    axle = (pos[0], pos[1], pos[2] + 1)
    return {
        "wheel": world.call("block", *pos)["state"],
        "material": material_name(world, pos), "flow": numeric(world, pos, "FlowScore"),
        "speed": numeric(world, pos, "Speed"),
        "axle": world.call("block", *axle)["state"],
        "axle_speed": numeric(world, axle, "Speed"),
    }


def apply_material(world, actor, target, pos, material):
    world.call("command", f"/gamemode survival {target}")
    world.commands((
        f"/tp {target} {pos[0]+.5} {pos[1]+1} {pos[2]+2.5}",
        f"/item replace entity {target} hotbar.2 with {material} 3",
    ))
    multiplayer.until("the material stack to arrive", lambda: (
        actor.call("inventory")["counts"].get(material) == 3
    ))
    actor.call("select", material)
    interaction = actor.call("interact", *pos, "south")
    print(f"{target} applied {material}: {interaction}; server NBT: "
          f"{world.command(f'/data get block {coords(pos)}')}", flush=True)
    multiplayer.until("the authoritative wheel material", lambda: (
        material_name(world, pos) == material
    ))
    # WaterWheelBlockEntity.applyMaterialIfValid never shrinks the stack.
    multiplayer.until("the unchanged survival plank stack", lambda: (
        actor.call("inventory")["counts"].get(material) == 3
    ))


def check_motion(state, large, *, active):
    flow = state["flow"]
    expected = max(-1, min(1, flow)) * (4 if large else 8)
    if bool(flow) != active or state["speed"] != expected or state["axle_speed"] != expected:
        raise RuntimeError(f"Expected {'active' if active else 'idle'} wheel/axle at {expected} RPM: {state}")


def setup(world, actor, target, structure, large):
    world.command(f"/place template create:{structure.with_suffix('')} 3 96 -12")
    x, y = (7, 98) if large else (6, 97)
    # Player movement continues in a frozen LAN world; give both actors a
    # safe floor while replication waits run, away from the water channels.
    world.command(f"/fill {x-2} {y-1} -8 {x+2} {y-1} -6 minecraft:smooth_stone")
    award.place_wheel(world, actor, target, x, y, large)
    pos = (x, y, -10)
    # The upstream fixture has a front stressometer on this axle; clear it
    # during plank clicks, then attach the checked shaft after recoloring.
    world.command(f"/setblock {x} {y} -9 minecraft:air")
    advance(world, 2)
    return pos


def activate(world, large):
    x, level = (7, 100) if large else (6, 98)
    world.commands((
        f"/fill {x-2} {level} -14 {x+2} {level} -14 minecraft:smooth_stone",
        f"/tp @s {x+.5} {level+1} -13.5",
    ))
    world.call("wait", 3)
    lever = (6, 103, -11) if large else (5, 101, -11)
    world.call("interact", *lever, "north")
    # Close the opposing stream, as in the original upstream GameTest.
    advance(world, 40 if large else 25)
    world.call("interact", *((8, 102, -11) if large else (7, 100, -11)), "north")
    advance(world, 30)


def reopen(args):
    size, structure = award.wheel_fixture(args.large)
    records = []
    with fixture_world(args, f"WheelGameplayReopen-{size}", structure, render=True, pack=args.pack) as world:
        pos = setup(world, world, "@s", structure, args.large)
        apply_material(world, world, "@s", pos, "minecraft:oak_planks")
        world.command(f"/setblock {pos[0]} {pos[1]} -9 create:shaft[axis=z]")
        for active in (False, True):
            if active:
                activate(world, args.large)
                world.command(f"/setblock {pos[0]} {pos[1]} -9 minecraft:air")
                apply_material(world, world, "@s", pos, "minecraft:birch_planks")
                world.command(f"/setblock {pos[0]} {pos[1]} -9 create:shaft[axis=z]")
            advance(world, 3)
            before = snapshot(world, pos)
            check_motion(before, args.large, active=active)
            inventory = world.call("inventory")["counts"]
            world.restart()
            # Large wheel Java source performs lazy flow resampling; allow it
            # to reconstruct connections before comparing stable operation.
            advance(world, 65)
            after = snapshot(world, pos)
            check_motion(after, args.large, active=active)
            if before != after or world.call("inventory")["counts"] != inventory:
                raise RuntimeError(f"{size} {'active' if active else 'idle'} reopen changed state: {before} -> {after}")
            records.append({"active": active, "before": before, "after": after})
    output = ROOT / f".local/waterwheel-gameplay-{size}-reopen.json"
    output.write_text(json.dumps(records, indent=2) + "\n")
    print(f"{size}: idle/active reopen preserved material, flow, RPM, axial connection and inventory. {output}")


def lan(args):
    size, structure = award.wheel_fixture(args.large)
    with fixture_world(args, f"WheelGameplayLAN-{size}", structure, render=True, pack=args.pack) as world:
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-wheel-gameplay-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
            scenario=f"wheel-gameplay-{size}", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to join", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in world.call("lan", "status")["guests"]
            ))
            pos = setup(world, guest, GUEST, structure, args.large)
            apply_material(world, world, "@s", pos, "minecraft:oak_planks")
            world.command(f"/tp @s {pos[0]-1.5} {pos[1]} {pos[2]+3.5}")
            apply_material(world, guest, GUEST, pos, "minecraft:birch_planks")
            world.command(f"/setblock {pos[0]} {pos[1]} -9 create:shaft[axis=z]")
            activate(world, args.large)
            state = snapshot(world, pos)
            check_motion(state, args.large, active=True)
            # `block` reads the guest's local state. /data commands query the
            # server, so they cannot prove guest block-entity material/RPM.
            multiplayer.until("guest wheel and axle block convergence", lambda: (
                guest.call("block", *pos)["state"] == state["wheel"]
                and guest.call("block", pos[0], pos[1], pos[2]+1)["state"] == state["axle"]
            ))
    print(f"{size}: guest survival placement, host/guest nonconsuming plank use and server generation with guest block convergence passed.")


def axes(args):
    errors = []
    with fixture_world(args, "WheelGameplayAxes", render=True, pack=args.pack) as world:
        for label, support, face, camera, facing, shaft, sneak in (
            ("x", (13, 110, -10), "west", (9.5, 110, -9.5), "west", False, False),
            ("y", (12, 109, -10), "up", (14.5, 112, -9.5), "up", False, False),
            ("shaft-preference", (12, 110, -11), "south", (12.5, 110, -7.5), "west", True, False),
            ("sneak-direction", (12, 110, -11), "south", (12.5, 110, -7.5), "north", False, True),
        ):
            world.commands((
                "/fill 9 108 -13 15 114 -7 minecraft:air",
                f"/setblock {math.floor(camera[0])} {int(camera[1])-1} {math.floor(camera[2])} minecraft:stone",
                f"/setblock {coords(support)} minecraft:stone",
                f"/tp @s {coords(camera)}", "/clear @s",
                "/give @s create:water_wheel 1",
            ))
            if sneak:
                world.call("command", "/tp @s 12.5 110 -7.5 -180 0")
            if shaft:
                world.command("/setblock 13 110 -10 create:shaft[axis=x]")
            world.call("command", "/gamemode survival")
            world.call("select", "create:water_wheel")
            face_point = {
                "west": (13.001, 110.5, -9.5),
                "up": (12.9, 109.999, -9.5),
                "south": (12.5, 110.5, -11.001),
            }[face]
            click_face(world, support, face_point, face, "create:water_wheel", sneak=sneak)
            world.call("wait", 8)
            state = world.call("block", 12, 110, -10)["state"]
            print(f"{label} placement state: {state}", flush=True)
            actual_facing = state.partition("facing=")[2].partition(",")[0]
            actual_axis = {"east": "x", "west": "x", "up": "y", "down": "y", "north": "z", "south": "z"}.get(actual_facing)
            expected_axis = "x" if facing in ("east", "west") else ("y" if facing in ("up", "down") else "z")
            if actual_axis != expected_axis:
                errors.append((label, facing, state))
    if errors:
        raise RuntimeError(f"Java directional placement mismatches: {errors}")
    print("Small wheel X/Y placement, shaft preference and sneak override matched Java source.")


def placement(args):
    errors = []
    with fixture_world(args, "WheelGameplayPlacement", render=True, pack=args.pack) as world:
        world.commands((
            "/fill 9 104 -14 16 108 -6 minecraft:air",
            "/fill 9 104 -14 16 104 -6 minecraft:stone",
            "/setblock 12 105 -11 minecraft:stone",
            "/setblock 13 105 -11 minecraft:stone",
            "/gamemode survival", "/tp @s 12.5 105 -7.5", "/clear @s",
            "/give @s create:water_wheel 3",
        ))
        world.call("select", "create:water_wheel")
        click_face(world, (12, 105, -11), (12.5, 105.5, -10.999), "south", "create:water_wheel")
        world.call("wait", 8)
        print(f"first wheel: {world.call('block', 12, 105, -10)}", flush=True)
        candidates = ((12.5, 105.5, -9.999), (12.5, 105.95, -9.999),
                      (12.5, 105.05, -9.999), (12.05, 105.5, -9.999),
                      (12.95, 105.5, -9.999))
        hits = []
        for point in candidates:
            world.call("look-at", *point)
            hit = world.call("looking-at")
            hits.append(hit)
            if (hit.get("block") or {}).get("pos") == [12, 105, -10]:
                click_face(world, (12, 105, -10), point, hit["block"]["face"], "create:water_wheel")
                world.call("wait", 8)
                break
        else:
            raise RuntimeError(f"No ray point on the first wheel; candidate hits={hits}")
        for z in (-10, -9):
            state = world.call("block", 12, 105, z)["state"]
            if not state.startswith("create:water_wheel[facing=") or state.split("facing=", 1)[1][0] != "s":
                raise RuntimeError(f"Aligned axle wheel failed at z={z}: {state}")
        click_face(world, (13, 105, -11), (13.5, 105.5, -10.999), "south", "create:water_wheel")
        world.call("wait", 8)
        state = world.call("block", 13, 105, -10)["state"]
        count = world.call("inventory")["counts"].get("create:water_wheel", 0)
        if state != "minecraft:air" or count != 1:
            errors.append(f"Java rejects side-by-side wheels without consumption; got {state}, remaining={count}")
        world.commands((
            "/fill 10 105 -12 15 107 -8 minecraft:air",
            "/setblock 12 105 -8 minecraft:stone",
            "/setblock 12 106 -11 minecraft:stone",
            "/setblock 13 106 -10 minecraft:stone",
            "/tp @s 12.5 106 -7.5", "/clear @s",
            "/give @s create:large_water_wheel 1",
        ))
        world.call("select", "create:large_water_wheel")
        click_face(world, (12, 106, -11), (12.5, 106.5, -10.999), "south", "create:large_water_wheel")
        world.call("wait", 8)
        state = world.call("block", 12, 106, -10)["state"]
        count = world.call("inventory")["counts"].get("create:large_water_wheel", 0)
        if state != "minecraft:air" or count != 1:
            errors.append(f"Occupied large-wheel rim must reject without consumption: {state}, remaining={count}")
    if errors:
        raise RuntimeError("; ".join(errors))
    print("Aligned small wheels placed; side-by-side small wheels and occupied large rim rejected without consumption.")


def craft(args):
    # crafting/kinetics/{water_wheel,large_water_wheel}.json: eight
    # minecraft:planks surrounding a shaft / small wheel, output one.
    with fixture_world(args, "WheelGameplayCraft", render=True, pack=args.pack) as world:
        world.commands((
            "/fill 8 169 22 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5", "/gamemode survival", "/clear @s",
            "/item replace entity @s hotbar.0 with minecraft:oak_planks 16",
            "/item replace entity @s hotbar.1 with create:shaft 1",
        ))
        for ingredient, output in (("create:shaft", "create:water_wheel"),
                                   ("create:water_wheel", "create:large_water_wheel")):
            world.call("interact", 12, 170, 24, "up")
            source = crafting.inventory_slot(world, "minecraft:oak_planks")
            crafting.distribute(world, source, (100, 101, 102, 103, 105, 106, 107, 108))
            # Return the unspent eight planks to their original slot.
            world.call("click-slot", source)
            crafting.distribute(world, crafting.inventory_slot(world, ingredient), (104,))
            crafting.craft(world, output, 1)
            world.call("close")
            expected = {output: 1}
            if output == "create:water_wheel":
                expected["minecraft:oak_planks"] = 8
            actual = world.call("inventory")["counts"]
            if actual != expected:
                raise RuntimeError(f"Wheel crafting inventory: expected {expected}, got {actual}")
    print("Survival table crafted small then large wheel, consuming exactly 16 planks and one shaft.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--large", action="store_true")
    parser.add_argument("--mode", choices=("craft", "lan", "reopen", "placement", "axes"), default="reopen")
    args = parser.parse_args()
    {"craft": craft, "lan": lan, "reopen": reopen, "placement": placement, "axes": axes}[args.mode](args)
