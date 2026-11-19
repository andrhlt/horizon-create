#!/usr/bin/env python3
"""Compare the Flywheel's Java trace and the rendered rotor on a Horizon LAN."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import importlib.util
from pathlib import Path
from shutil import which
import subprocess
from tempfile import TemporaryDirectory
import time

from fixture_world import ROOT, fixture_world

GUEST = "FlywheelGuest"
CAMERA = (9.5, 106.0, -10.5)
AIM = (5.5, 106.5, -10.5)
VIEW_TICKS = (1, 4, 15, 26, 27, 39, 51, 52, 64, 76, 77, 95)


def load(name):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


flywheel = load("test-flywheel")
multiplayer = load("test-multiplayer")


def setup(host):
    host.commands((
        "/time set noon",
        "/weather clear",
        "/fill 1 98 -27 1 115 7 minecraft:blue_concrete",
        "/setblock 3 105 -10 minecraft:smooth_stone",
        f"/setblock {flywheel.WHEEL} create:flywheel[axis=x]",
        f"/setblock {flywheel.SHAFT} create:shaft[axis=x]",
        f"/setblock {flywheel.COG} create:cogwheel[axis=x]",
        "/gamemode spectator",
        "/tp @s 9.5 106 -10.5",
    ))


def position_guest(host, guest):
    host.commands((f"/gamemode spectator {GUEST}", f"/tp {GUEST} 9.5 106 -10.5"))
    multiplayer.until("the guest to reach the common camera", lambda: (
        guest.call("state")["player"]["position"] == list(CAMERA)
    ))
    guest.call("look-at", *AIM)


def remove_motor(host, guest):
    host.commands((f"/gamemode creative {GUEST}", f"/tp {GUEST} 3.5 106 -9.5"))
    multiplayer.until("the guest to reach the motor", lambda: (
        guest.call("state")["player"]["position"] == [3.5, 106, -9.5]
    ))
    coords = tuple(map(int, flywheel.MOTOR.split()))
    guest.call("break", *coords)
    multiplayer.until("the guest to remove the motor in the shared world", lambda: (
        host.call("block", *coords)["state"] == "minecraft:air"
    ))
    position_guest(host, guest)


def rotor_pixels(path, ffmpeg):
    # The navy backdrop excludes warm world colors. Inspect only the wheel's
    # region and mask the brass rim and hubs so ambient shading can vary.
    data = subprocess.check_output([
        ffmpeg, "-v", "error", "-threads", "1", "-filter_threads", "1", "-i", str(path),
        "-vf", "scale=640:360,crop=240:220:200:70", "-frames:v", "1",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
    ])
    return {
        pixel for pixel, (red, green, blue) in enumerate(zip(data[::3], data[1::3], data[2::3]))
        if red > 65 and green > 42 and red > green + 8 and green > blue + 12
    }


def overlap(first, second):
    return len(first & second) / len(first | second)


def take_frame(control, label, tick, started, png_dir, ffmpeg):
    path = png_dir / f"{label}-{tick:02d}.png"
    control.call("screenshot", path)
    completed = (time.monotonic() - started) * 1000
    return rotor_pixels(path, ffmpeg), completed


def verify(args, scratch):
    output = ROOT / ".local/flywheel-lan"
    output.mkdir(exist_ok=True)
    with (ROOT / "fixtures/flywheel-java.csv").open() as source:
        expected = list(csv.DictReader(source))
    masks = {}
    captures = []
    net_columns = ("tick", "wheel_rpm", "shaft_rpm", "cog_rpm", "network_stress", "network_capacity")
    serve_env = {"CREATE_FLYWHEEL_TRACE_POS": flywheel.WHEEL.replace(" ", ",")}
    pack = args.pack or ROOT / ".local/create.hmod"
    if args.java_source:
        flywheel.check_assets(pack, args.java_source)

    with fixture_world(args, "FlywheelLAN", render=True, env=serve_env, pack=pack) as host:
        setup(host)
        online = host.call("lan", "open", "0", "commands", "force")
        with multiplayer.joined_client(
            args, scratch, f"127.0.0.1:{online['port']}", GUEST, render=True,
            scenario="flywheel-lan", pack=pack,
        ) as guest, ThreadPoolExecutor(max_workers=2) as camera:
            multiplayer.until("the guest to enter the LAN world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            position_guest(host, guest)
            multiplayer.until("the guest to see the Flywheel", lambda: (
                guest.call("block", *map(int, flywheel.WHEEL.split()))["state"] == "create:flywheel[axis=x]"
            ))
            for control in (host, guest):
                control.call("key", "f1", "tap")
                control.call("look-at", *AIM)
                control.call("wait", 5)
            start = host.clock()
            for tick, row in enumerate(expected):
                if tick:
                    host.step_to(start + tick)
                started = time.monotonic()
                actual = flywheel.sample(host, tick)
                wanted = [float(row[key]) for key in net_columns]
                if actual != wanted:
                    raise RuntimeError(f"On LAN tick {tick}, Java measured {wanted}. Horizon measured {actual}.")
                if tick in VIEW_TICKS:
                    pending = [
                        camera.submit(take_frame, control, label, tick, started, output, args.ffmpeg)
                        for control, label in ((host, "host"), (guest, "guest"))
                    ]
                    (host_mask, host_ms), (guest_mask, guest_ms) = [frame.result() for frame in pending]
                    if host.clock() != start + tick:
                        raise RuntimeError(f"The LAN server advanced during the tick {tick} screenshot.")
                    if min(len(host_mask), len(guest_mask)) < 500:
                        raise RuntimeError(f"The original brass Flywheel did not render in both views at tick {tick}.")
                    ratio = overlap(host_mask, guest_mask)
                    captures.append((tick, len(host_mask), len(guest_mask), ratio, host_ms, guest_ms))
                    masks[tick] = (host_mask, guest_mask)
                if tick == 3:
                    flywheel.power(host, 64, place=True)
                elif tick == 26:
                    flywheel.power(host, -64)
                elif tick == 51:
                    remove_motor(host, guest)
                elif tick == 76:
                    flywheel.power(host, 32, place=True)

    observed_motion = flywheel.read_motion(ROOT / ".local/horizon-flywheellan.log", start)
    motion_fields = ("previous_rotor_rpm", "rotor_rpm", "angle")
    for tick, row in enumerate(expected):
        wanted = [float(row[field]) for field in motion_fields]
        actual = observed_motion.get(tick, [0.0] * 3 if tick == 0 else [])
        if actual != wanted:
            raise RuntimeError(f"On LAN tick {tick}, Java rotor measured {wanted}. Horizon measured {actual}.")

    table = output / "rendered-checkpoints.csv"
    with table.open("w", newline="") as handle:
        print("fixture_tick,host_brass_pixels,guest_brass_pixels,overlap,host_capture_ms,guest_capture_ms", file=handle)
        csv.writer(handle, lineterminator="\n").writerows(captures)
    for tick, _, _, ratio, *_ in captures:
        if ratio < 0.98:
            raise RuntimeError(f"At tick {tick}, host and guest rotor masks overlap by {ratio:.1%}. See {table}")
    for earlier, later in ((1, 15), (39, 51), (52, 64), (77, 95)):
        for before, after in zip(masks[earlier], masks[later], strict=True):
            if overlap(before, after) > 0.94:
                raise RuntimeError(f"The rendered rotor stopped changing between ticks {earlier} and {later}.")
    return captures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--java-source", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    if not which(args.ffmpeg):
        parser.error("the LAN screenshot comparison requires ffmpeg")
    with TemporaryDirectory(prefix="hc-flywheel-lan-") as scratch:
        captures = verify(args, Path(scratch))
    print(f"Flywheel LAN matched the Java network and rotor on all 96 ticks. "
          f"The guest removed the motor on tick 51. The minimum brass mask overlap was "
          f"{min(row[3] for row in captures):.2%} across {len(captures)} frozen ticks. "
          f"Guest capture replies took {min(row[5] for row in captures):.0f} to "
          f"{max(row[5] for row in captures):.0f} ms from the host tick observation.")


if __name__ == "__main__":
    main()
