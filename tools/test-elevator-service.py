#!/usr/bin/env python3
"""Compare a two-client standing elevator trip and its floor-controlled doors."""
import argparse
from collections import Counter, defaultdict
import csv
from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

spec = spec_from_file_location("elevator_passengers", Path(__file__).with_name("test-multiplayer-elevator.py"))
trip = module_from_spec(spec)
spec.loader.exec_module(trip)
elevator = trip.elevator
multiplayer = trip.multiplayer
effects = trip.load("check-elevator-effects")
SCENARIO = "elevator-service"
CABIN_DOOR = (3, 2, 3)
LOWER_DOOR = (3, 2, 4)
UPPER_DOOR = (3, 11, 4)
MODE = re.compile(r'\bDoorControl: "([A-Z]+)"')
BLOCK_STATE = re.compile(r"BlockState: \{([^{}]*\{[^{}]*\}[^{}]*)\}")
PROPERTIES_TAG = re.compile(r"Properties: \{([^{}]*)\}")
PROPERTIES = re.compile(r'(?:^|, )(half|open): "?([a-z]+)"?')
RIDERS = ((5.5, 2.5), (4.5, 2.5))
# Fixture windows render at 2560 × 1440 with automatic GUI scale 6.
DOOR_WIDGET = (167, 144)


def above(pos, dy=1):
    x, y, z = pos
    return x, y + dy, z


def build_fixture(host):
    commands = [
        "/gamerule random_tick_speed 0",
        "/gamerule fall_damage false",
        f"/place template create:{elevator.TEMPLATE.with_suffix('')} {elevator.as_argument((0, 0, 0))}",
        f"/setblock {elevator.as_argument(trip.GUEST_SEAT)} minecraft:air",
    ]
    for pos, block in ((CABIN_DOOR, "create:train_door"),
                       (LOWER_DOOR, "minecraft:iron_door"), (UPPER_DOOR, "minecraft:iron_door")):
        if pos != CABIN_DOOR:
            commands.append(f"/setblock {elevator.as_argument(above(pos, -1))} minecraft:iron_block")
        for half, at in (("lower", pos), ("upper", above(pos))):
            commands.append(f"/setblock {elevator.as_argument(at)} {block}"
                            f"[facing=south,half={half},hinge=left,open=false,powered=false]")
    x, y, z = CABIN_DOOR
    commands.append(f"/summon minecraft:marker {elevator.as_argument((x + 0.5, y - 1, z + 0.5))}"
                    " {CreateSuperGlue:1b,From:[-0.5d,0d,-0.5d],To:[0.5d,3d,0.5d]}")
    host.commands(commands)
    if "create:train_door" not in host.call("block", *elevator.at(CABIN_DOOR))["state"]:
        raise RuntimeError("The cabin train door is missing from the pack.")


def floor_editor(host, client, floor, approach, door_scroll, names=None):
    trip.aim_block(host, client, floor, approach)
    client.call("interact", *elevator.at(floor))
    client.call("wait", 3)
    if names:
        for index, name in enumerate(names):
            if index:
                client.call("key", "tab", "tap")
            client.call("type", name)
    client.call("scroll-at", *DOOR_WIDGET, door_scroll)
    client.call("key", "enter", "tap")
    client.call("wait", 2)


def open_state(client, pos):
    state = client.call("block", *elevator.at(pos))["state"]
    match = re.search(r"\bopen=(true|false)", state)
    return match[1] if match else ""


def sample(host, tick):
    primary, cabin, blocks, lower, upper = host.commands((
        f"/data get block {elevator.as_argument(elevator.PRIMARY)}",
        f"/data get entity {elevator.CART} Pos",
        f"/data get entity {elevator.CART} CreateRopeLoad.Blocks",
        f"/data get block {elevator.as_argument(trip.LOWER)}",
        f"/data get block {elevator.as_argument(trip.UPPER)}",
    ))
    target = trip.RETURN.search(primary)
    position = elevator.POSITION.search(cabin)
    states = {}
    for tag in BLOCK_STATE.findall(blocks):
        if 'Name: "create:train_door"' in tag and (props := PROPERTIES_TAG.search(tag)):
            values = dict(PROPERTIES.findall(props[1]))
            if "half" in values and "open" in values:
                states[values["half"]] = values["open"]
    modes = [(match[1] if (match := MODE.search(value)) else "") for value in (lower, upper)]
    return {
        "tick": str(tick),
        "cabin_y": f"{float(position[2]) - elevator.ORIGIN[1]:.9f}" if position else "",
        "target_y": str(int(target[1]) - elevator.ORIGIN[1]) if target else "",
        "bottom_lit": trip.prop(host, elevator.BOTTOM, "lit"),
        "top_lit": trip.prop(host, elevator.TOP, "lit"),
        "lower_mode": modes[0],
        "upper_mode": modes[1],
        "cabin_lower_open": states.get("lower", ""),
        "cabin_upper_open": states.get("upper", ""),
        "lower_lower_open": open_state(host, LOWER_DOOR),
        "lower_upper_open": open_state(host, above(LOWER_DOOR)),
        "upper_lower_open": open_state(host, UPPER_DOOR),
        "upper_upper_open": open_state(host, above(UPPER_DOOR)),
    }


def check_rider(host, client, name, x, z, cabin_y):
    wanted = (x, cabin_y + 1 + trip.JAVA_FOOT_CLEARANCE, z)
    actual = None

    def settled():
        nonlocal actual
        state = client.call("state")
        player = state["player"]
        actual = trip.relative(player["position"])
        if state["gamemode"] != "survival" or player["flying"]:
            raise RuntimeError(f"{name} was not standing in survival: {state}")
        if player["health"] <= 0 or not player["on_ground"]:
            return False
        if not all(abs(a - b) < 1e-7 for a, b in zip(actual, wanted, strict=True)):
            return False
        server = trip.relative(trip.pos_reply(host.command(f"/data get entity {name} Pos")))
        return all(abs(a - b) < 1e-7 for a, b in zip(server, wanted, strict=True))

    try:
        multiplayer.until(f"{name} to stand at {wanted}", settled, 3)
    except RuntimeError as error:
        raise RuntimeError(f"{error}. Last local position: {actual}.") from error
    return actual



def observe_landing(guest, row, previous):
    for key, pos in (
        ("lower_lower_open", LOWER_DOOR), ("lower_upper_open", above(LOWER_DOOR)),
        ("upper_lower_open", UPPER_DOOR), ("upper_upper_open", above(UPPER_DOOR)),
    ):
        if previous is not None and row[key] == previous[key] and row["tick"] != "16":
            continue
        multiplayer.until(f"guest to see {key}={row[key]} on tick {row['tick']}",
                          lambda: open_state(guest, pos) == row[key], 3)

def replay(args, reference, scratch):
    with fixture_world(args, SCENARIO, elevator.TEMPLATE, render=True, pack=args.pack) as host:
        network = host.call("lan", "open", "0", "commands", "force")
        name = host.call("lan", "status")["host"]
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(args, scratch, address, trip.GUEST, render=True, scenario=SCENARIO, pack=args.pack) as guest:
            multiplayer.until("the independent guest to join", lambda: any(
                player["name"] == trip.GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.command("/tick unfreeze")
            for client in (host, guest):
                client.call("script", script="key space down\nwait 1\nkey space up\nwait 1\nkey space down\nwait 1\nkey space up\n")
                multiplayer.until("creative flight for fixture setup", lambda: client.call("state")["player"]["flying"])
            host.command("/tick freeze")
            while host.clock() % 20 != 2:
                host.step_to(host.clock() + 1)
            build_fixture(host)
            start = host.clock()
            print(f"Fixture starts at world tick {start}.", flush=True)
            actual = []
            positions = []
            for expected in reference:
                tick = int(expected["tick"])
                if tick:
                    host.step_to(start + tick)
                result = sample(host, tick)
                actual.append(result)
                if tick >= 16 and not args.record_only:
                    observe_landing(guest, result, actual[-2] if tick else None)
                if 23 <= tick <= 88 and not args.record_only:
                    riders = zip((host, guest), (name, trip.GUEST), RIDERS, strict=True)
                    positions.append([
                        tick,
                        *[coordinate for client, player, (x, z) in riders
                          for coordinate in check_rider(host, client, player, x, z, float(result["cabin_y"]))],
                    ])
                if tick == 15:
                    trip.aim_block(host, host, elevator.PRIMARY, (7.5, 11.0, 4.5))
                    host.call("interact", *elevator.at(elevator.PRIMARY))
                elif tick == 18:
                    floor_editor(host, host, trip.LOWER, (0.5, 1.0, 2.5), -3, ("G", "Ground"))
                    floor_editor(host, guest, trip.UPPER, (2.5, 10.0, 4.0), -5, ("U", "Upper"))
                elif tick == 22:
                    for client, player, (x, z) in zip((host, guest), (name, trip.GUEST), RIDERS, strict=True):
                        trip.place_standing_rider(host, client, player, (x, 2.0, z))
                elif tick == 25:
                    x, y, z = trip.find_hitbox(host, trip.CONTROLS)
                    guest.call("look-at", x, y + 0.5, z)
                    guest.call("script", script="scroll-at 10 10 1\nuse-item\n")
                    trip.wait_for_selected_floor(host, trip.UPPER)
                elif tick == 88:
                    host.command(f"/setblock {elevator.as_argument((2, 9, 4))} minecraft:stone")
                    floor_editor(host, guest, trip.UPPER, (2.5, 10.0, 4.0), 2)
                if host.clock() != start + tick:
                    raise RuntimeError(f"World advanced while applying inputs on tick {tick}.")
            return start, actual, positions



def append_sounds(start, actual, reference, host_log):
    sampled_ids = {sound for row in reference for sound in row["server_sounds"].split("|") if sound}
    sounds = defaultdict(list)
    for tick, sound, *_ in effects.fields(host_log, "CREATE_ELEVATOR_SOUND "):
        if sound not in sampled_ids:
            continue
        # The confirmation happens after the tick-25 observation on both
        # platforms. The GameTest collects it in its next sample.
        after_sample = sound in (effects.CLICK, effects.START, effects.CHEST)
        sounds[int(tick) - start + after_sample].append(sound)
    for row in actual:
        row["server_sounds"] = "|".join(sounds[int(row["tick"])])


def check_door_audio(log, role):
    opening = "minecraft:block.iron_door.open"
    closing = "minecraft:block.iron_door.close"
    wanted = Counter({(opening, 1.0): 2, (opening, 0.125): 2,
                      (closing, 1.0): 1, (closing, 0.125): 1})
    played = Counter()
    for sound, category, _, _, _, gain, pitch in effects.fields(log, "CREATE_ELEVATOR_PLAYBACK "):
        if sound not in (opening, closing):
            continue
        gain, pitch = float(gain), float(pitch)
        valid_pitch = pitch == 1.0 if gain == 0.125 else 0.9 <= pitch <= 1.0
        if category != "4" or not valid_pitch:
            raise ValueError(f"{role} door cue {sound} used category {category}, gain {gain}, pitch {pitch}.")
        played[sound, gain] += 1
    if played != wanted:
        raise ValueError(f"{role} door cues {played} versus {wanted}.")

def run(args):
    os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    with (ROOT / "fixtures/elevator-service-java.csv").open() as source:
        reference = list(csv.DictReader(source))
    with TemporaryDirectory(prefix="hc-elevator-service-") as scratch:
        start, actual, positions = replay(args, reference, Path(scratch))
    host_log = (ROOT / f".local/horizon-{SCENARIO}.log").read_text()
    guest_log = (ROOT / f".local/{SCENARIO}-{trip.GUEST.lower()}.log").read_text()
    append_sounds(start, actual, reference, host_log)
    output = ROOT / ".local/elevator-service-horizon.csv"
    with output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, list(actual[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(actual)
    if args.record_only:
        print(f"Recorded {len(actual)} ticks in {output}.")
        return
    with (ROOT / ".local/elevator-standing-horizon.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("tick", "host_x", "host_y", "host_z", "guest_x", "guest_y", "guest_z"))
        writer.writerows(positions)
    errors = [(row["tick"], {key: (expected[key], row[key]) for key in row if row[key] != expected[key]})
              for expected, row in zip(reference, actual, strict=True)
              if any(row[key] != expected[key] for key in row)]
    if errors:
        raise SystemExit(f"{len(errors)} differences. First 12: {errors[:12]}. See {output}.")
    indicator = effects.read_fixture("elevator-indicator-java.csv")
    effects.check_client(host_log, "host", start, indicator)
    effects.check_client(guest_log, "guest", start, indicator)
    check_door_audio(host_log, "host")
    check_door_audio(guest_log, "guest")
    print(f"Matched Java door, cabin and sound events on all {len(actual)} ticks. "
          f"Both clients matched all {len(indicator)} indicator samples. "
          f"Both Horizon players remained standing at the cabin floor on {len(positions)} ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for path in ("ctl", "client", "resources"):
        parser.add_argument(path, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--record-only", action="store_true")
    run(parser.parse_args())
