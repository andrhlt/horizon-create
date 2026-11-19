#!/usr/bin/env python3
"""Compare both clients' elevator indicator traces and sound starts."""

import argparse
import csv
from pathlib import Path
from struct import pack

ORIGIN_Y = 96
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SCROLL = "create:scroll_value"
CLICK = "create:controller_click"
START = "create:contraption_assemble"
CHEST = "create:contraption_assemble_compounded_1"
STOP = "create:contraption_disassemble"
SOUNDS = {
    SCROLL: (7, 0.124, 1.25),
    CLICK: (4, 0.35, 1.5),
    START: (4, 0.375, 0.4),
    CHEST: (4, 0.03375, 0.592),
    STOP: (4, 0.2625, 0.6),
}


def fields(text, cue):
    return (next(csv.reader([line.split(cue, 1)[1]])) for line in text.splitlines() if cue in line)


def single(value):
    return pack(">f", float(value))


def read_fixture(name):
    with (FIXTURES / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def check_client(log, role, start, reference):
    samples = {
        int(tick) - start: (int(current) - ORIGIN_Y, int(target) - ORIGIN_Y,
                            previous, angle, chase, int(frame), button_previous, button,
                            selected, short, long)
        for tick, _, current, target, previous, angle, chase, frame,
        button_previous, button, selected, short, long in fields(log, "CREATE_ELEVATOR_INDICATOR ")
    }
    for row in reference:
        tick = int(row["tick"])
        if tick not in samples:
            raise ValueError(f"{role} missing indicator tick {tick}")
        actual = samples[tick]
        want = (int(row["current_y"]), int(row["target_y"]),
                row["previous_angle"], row["angle"], row["chase_angle"], int(row["frame"]),
                row[f"{role}_previous_button"], row[f"{role}_button"])
        for index, (observed, expected) in enumerate(zip(actual[:8], want, strict=True)):
            if isinstance(expected, str):
                observed, expected = single(observed), single(expected)
            if observed != expected:
                raise ValueError(f"{role} indicator tick {tick}, field {index}: {actual[:8]} versus {want}")
        if tick >= 20:
            short, long, selected_y = ("U", "Upper", 10) if role == "guest" and tick >= 26 else ("G", "Ground", 1)
            want_label = (str(selected_y == want[1]).lower(), short, long)
            if actual[8:] != want_label:
                raise ValueError(f"{role} label on tick {tick}: {actual[8:]} versus {want_label}")

    rendered_frames = {
        int(frame) for _, _, frame, vertices in fields(log, "CREATE_ELEVATOR_RENDER ")
        if int(vertices) > 0
    }
    if len(rendered_frames) < 3:
        raise ValueError(f"{role} rendered only models {sorted(rendered_frames)}")

    played = [
        (sound, int(category), float(volume), float(pitch))
        for sound, category, _, _, _, volume, pitch in fields(log, "CREATE_ELEVATOR_PLAYBACK ")
        if sound in SOUNDS and (sound != SCROLL or int(category) == SOUNDS[SCROLL][0])
    ]
    want_ids = (SCROLL, CLICK, START, CHEST, STOP) if role == "guest" else (CLICK, START, CHEST, STOP)
    if tuple(sound for sound, *_ in played) != want_ids:
        raise ValueError(f"{role} played sound IDs {played} versus {want_ids}")
    for sound, category, volume, pitch in played:
        expected_category, expected_volume, expected_pitch = SOUNDS[sound]
        if category != expected_category or abs(volume - expected_volume) > 1e-7 or abs(pitch - expected_pitch) > 1e-7:
            raise ValueError(f"{role} played {sound} at category {category}, gain {volume}, pitch {pitch}")


def check_server_cues(host, start):
    emitted = [
        # Confirmation is issued after sampling tick 25. The Java fixture
        # collects that event in the following sample. Arrival is a level tick.
        (int(tick) - start + (sound in (CLICK, START, CHEST)), sound)
        for tick, sound, *_ in fields(host, "CREATE_ELEVATOR_SOUND ")
        if sound in SOUNDS and sound != SCROLL
    ]
    want = [
        (int(row["tick"]), sound)
        for row in read_fixture("elevator-service-java.csv")
        for sound in row["server_sounds"].split("|") if sound in SOUNDS
    ]
    if emitted != want:
        raise ValueError(f"Server cues {emitted} versus {want}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host_log", type=Path)
    parser.add_argument("guest_log", type=Path)
    parser.add_argument("start_tick", type=int)
    args = parser.parse_args()
    reference = read_fixture("elevator-indicator-java.csv")
    host = args.host_log.read_text(encoding="utf-8")
    guest = args.guest_log.read_text(encoding="utf-8")
    check_client(host, "host", args.start_tick, reference)
    check_client(guest, "guest", args.start_tick, reference)
    check_server_cues(host, args.start_tick)
    print(f"Both clients matched all {len(reference)} indicator ticks and started the expected Create sound cues.")


if __name__ == "__main__":
    main()
