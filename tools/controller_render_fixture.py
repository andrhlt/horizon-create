"""Shared arrangements and frame fields for the controller render comparison."""
import csv
import time

RIGS = {6: ("x", "z", 16), 14: ("z", "x", -16)}
CAMERA = "10.5 105 -3.5 180 22"
STAGES = {
    "empty": ("minecraft:air", None, False),
    "vertical": ("create:large_cogwheel", "y", False),
    "encased": ("create:brass_encased_large_cogwheel", "across", False),
    "bare": ("create:large_cogwheel", "across", True),
    "removed": ("minecraft:air", None, False),
    "reinstalled": ("create:large_cogwheel", "across", True),
}
PART_FIELDS = ("vertices", "block_light", "sky_light", "min_x", "min_y", "min_z", "max_x", "max_y", "max_z")
FIELDS = (
    "x", "axis", "above", "above_axis", "tick", "fraction", "render_time", "rpm", "angle",
    "body_world_block_light", "above_world_block_light",
    *(f"{part}_{field}" for part in ("shaft", "bracket") for field in PART_FIELDS),
)


def setup():
    yield "fill 3 99 -13 17 108 -2 minecraft:stone hollow"
    yield "fill 4 100 -12 16 105 -7 minecraft:air"
    yield "fill 4 100 -12 16 100 -7 minecraft:smooth_stone"
    for x, (axis, _, _) in RIGS.items():
        yield f"setblock {x} 101 -10 create:rotation_speed_controller[axis={axis}]"
        motor = f"{x - 1} 101 -10 create:creative_motor[facing=east]" if axis == "x" else f"{x} 101 -9 create:creative_motor[facing=north]"
        yield f"setblock {motor}"
        yield f"setblock {x + 1} 103 -10 minecraft:glowstone"


def stage_state(stage, x):
    block, axis, bracket = STAGES[stage]
    if stage == "encased" and x == 14:
        block = "create:andesite_encased_large_cogwheel"
    return block, RIGS[x][1] if axis == "across" else (axis or "-"), bracket


def stage_commands(stage):
    for x in RIGS:
        block, axis, _ = stage_state(stage, x)
        state = block if axis == "-" else f"{block}[axis={axis}]"
        yield f"setblock {x} 102 -10 {state}"


def frames(log, marker, offset, stage, count=2, timeout=20, wait_for_bracket=False):
    selected = {x: {} for x in RIGS}
    last = {}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with log.open("rb") as stream:
            stream.seek(offset)
            lines = stream.read().decode(errors="replace").splitlines()
        for line in lines:
            if marker not in line:
                continue
            cells = next(csv.reader([line.split(marker, 1)[1]]))
            if len(cells) != len(FIELDS):
                continue
            row = dict(zip(FIELDS, cells, strict=True))
            x = int(row["x"])
            if x not in RIGS:
                continue
            axis, _, rpm = RIGS[x]
            block, want_axis, bracket = stage_state(stage, x)
            last[x] = tuple(row[key] for key in ("axis", "above", "above_axis", "rpm"))
            if last[x] != (axis, block, want_axis, f"{rpm:.6f}"):
                continue
            if int(row["shaft_vertices"]) == 0:
                continue
            if wait_for_bracket and (int(row["bracket_vertices"]) > 0) != bracket:
                continue
            selected[x][row["render_time"]] = row
        if all(len(rows) >= count for rows in selected.values()):
            return [row for rows in selected.values() for row in list(rows.values())[-count:]]
        time.sleep(0.12)
    raise RuntimeError(f"No rendered {stage} scene in {log}. Latest observations: {last}.")
