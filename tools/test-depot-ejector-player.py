#!/usr/bin/env python3
"""Compare a real local player’s Weighted Ejector launch and landing."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
EJECTOR = (5, 104, -11)
LANDING = "8 104 -12 13 106 -10"
GUEST = "LaunchGuest"


def setup(host, flat):
    host.commands((
        "/fill 3 103 -13 14 103 -9 minecraft:smooth_stone",
        "/fill 3 104 -13 14 112 -9 minecraft:air",
        *((f"/fill {LANDING} minecraft:smooth_stone",) if not flat else ()),
        "/setblock 5 104 -11 create:weighted_ejector[facing=east]{HorizontalDistance:4,VerticalDistance:0}",
        "/setblock 5 104 -12 create:creative_motor[facing=south]{ScrollValue:128}",
    ))
    if flat:
        host.command("/gamerule natural_health_regeneration false")
    host.command("/tick unfreeze")
    multiplayer.until("the Weighted Ejector builds up its charge", lambda:
                      "CHARGED" in host.command("/data get block 5 104 -11 State"))


def local_samples(actor, flat):
    hold = "wait 1\nstate\n" * (52 if flat else 42)
    script = 'command "/tp @s 5.5 106.5 -10.5"\n' + hold
    result = actor.call("script", script=script)
    return [(reply["ticks"], reply["player"]) for reply in result if "player" in reply]


def launch_audio(control, offset):
    marker = "CREATE_ELEVATOR_PLAYBACK "
    log = (control.socket.parent / "ctl.log").read_bytes()[offset:].decode(errors="replace")
    cues = []
    for line in log.splitlines():
        if marker not in line:
            continue
        sound, category, x, y, z, volume, pitch = line.split(marker, 1)[1].split(",")
        if sound not in ("minecraft:block.wooden_trapdoor.close", "minecraft:block.chest.open"):
            continue
        if tuple(map(float, (x, y, z))) != tuple(value + .5 for value in EJECTOR):
            raise RuntimeError(f"Wrong player launch sound position: {line}")
        cues.append((sound, int(category), round(float(volume), 6), round(float(pitch), 6)))
    return cues


def sample(tick, state, elytra):
    pos = [a - b for a, b in zip(state["position"], EJECTOR, strict=True)]
    result = (str(tick), *(f"{v:.9f}" for v in (*pos, *state["velocity"])),
              str(state["on_ground"]).lower(), f'{state["health"]:.2f}')
    if elytra:
        result += (str(state["fall_flying"]).lower(), f'{state["yaw"] % 360:.4f}', f'{state["pitch"]:.4f}')
    return result


def match(want, got):
    if len(want) > 9 and (want[9] != got[9] or int(want[0]) >= 0 and want[10:] != got[10:]):
        return False
    return want[:1] == got[:1] and want[7:9] == got[7:9] and all(
        abs(float(a) - float(b)) < 2e-7 for a, b in zip(want[1:7], got[1:7], strict=True)
    )



def capture_window(actor, expected, args, listeners):
    origin = int(expected[0][0])
    for attempt in range(2):
        if attempt:
            actor.command("/effect give @s minecraft:instant_health 1 4 true")
            multiplayer.until("the player recovers from the previous attempt",
                              lambda: actor.call("state")["player"]["health"] == 20)
        offsets = {peer: (peer.socket.parent / "ctl.log").stat().st_size for peer in listeners}
        observed = local_samples(actor, args.flat)
        start = next((i for i, (_, value) in enumerate(observed)
                      if match(tuple(expected[0]), sample(origin, value, args.elytra))), None)
        window = observed if start is None else observed[start:start + len(expected)]
        ticks = [tick for tick, _ in window]
        gaps = [(a, b) for a, b in zip(ticks, ticks[1:]) if b != a + 1]
        if not gaps:
            return [value for _, value in observed], start, offsets
        message = f"The control client skipped a physics observation between ticks {gaps[0]}."
        if attempt:
            raise RuntimeError(message)
        print(f"{message} Retrying the capture.", flush=True)


def run(args):
    if args.flat:
        filename = "depot-ejector-player-flat-java.csv"
    else:
        filename = "depot-ejector-elytra-java.csv" if args.elytra else "depot-ejector-player-java.csv"
    reference = args.reference or ROOT / "fixtures" / filename
    with reference.open() as stream:
        data = csv.reader(stream)
        header, expected = next(data), list(data)
    if args.sound:
        os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    with ExitStack() as stack:
        world = "EjectorElytra" if args.elytra else "EjectorPlayer"
        if args.flat:
            world += "Flat"
        if args.host_player:
            world += "LANHost"
        elif args.multiplayer:
            world += "LAN"
        host = stack.enter_context(fixture_world(args, world, render=True, pack=args.pack))
        setup(host, args.flat)
        guest = None
        if args.multiplayer or args.host_player:
            host.commands(("/gamemode spectator @s", "/tp @s 8.5 109 -8.5"))
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-eject-player-")))
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", GUEST, scenario=world.lower(), pack=args.pack,
                render=True,
            ))
            multiplayer.until("the Ejector guest arrives", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            if args.host_player:
                host.commands((f"/gamemode spectator {GUEST}", f"/tp {GUEST} 8.5 109 -8.5"))
            else:
                host.commands((f"/op {GUEST}", f"/tp {GUEST} 10.5 107 -9.5", f"/gamemode survival {GUEST}"))
            multiplayer.until("the guest sees the throw plate", lambda:
                              guest.call("block", *EJECTOR)["block"] == "create:weighted_ejector")
        actor = guest if args.multiplayer else host
        if actor is host:
            host.commands(("/tp @s 10.5 107 -9.5", "/gamemode survival @s"))
        if args.elytra:
            active = GUEST if args.multiplayer else "@s"
            host.command(f"/item replace entity {active} armor.chest with minecraft:elytra")
            actor.call("wait", 3)
        listeners = ((host,) if guest is None else (host, guest)) if args.sound else ()
        observed, start, offsets = capture_window(actor, expected, args, listeners)
        if args.sound:
            cues = [
                ("minecraft:block.wooden_trapdoor.close", 4, .35, 1.0),
                ("minecraft:block.chest.open", 4, .1, 1.4),
            ]
            for observer in listeners:
                multiplayer.until("the authoritative Ejector's launch sounds", lambda:
                                  len(launch_audio(observer, offsets[observer])) >= len(cues))
                if launch_audio(observer, offsets[observer]) != cues:
                    raise RuntimeError(f"Incorrect Ejector player launch sounds: {launch_audio(observer, offsets[observer])}")
    origin = int(expected[0][0])
    if args.trace:
        with args.trace.open("w") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(sample(i + origin - (start or 0), value, args.elytra) for i, value in enumerate(observed))
    if start is None:
        raise RuntimeError("The player never reached the original Java descent pose.")
    got = [sample(origin + i, value, args.elytra) for i, value in enumerate(observed[start:start + len(expected)])]
    differences = [(a,b) for a,b in zip(expected,got,strict=True) if not match(tuple(a),b)]
    if differences:
        raise RuntimeError(f"The live player differed on {len(differences)} Java ticks: {differences[:8]}")
    if args.elytra:
        print(f"Elytra deployment, view angles and the initial glide matched all {len(got)} Java ticks.")
    else:
        print(f"The live player matched all {len(got)} Java descent, launch, flight, and landing ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--trace", type=Path)
    role = parser.add_mutually_exclusive_group()
    role.add_argument("--multiplayer", action="store_true", help="launch the LAN guest")
    role.add_argument("--host-player", action="store_true", help="launch the LAN host")
    parser.add_argument("--sound", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--elytra", action="store_true")
    mode.add_argument("--flat", action="store_true")
    run(parser.parse_args())
