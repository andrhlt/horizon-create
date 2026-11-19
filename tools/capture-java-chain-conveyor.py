#!/usr/bin/env python3
"""Extract the pinned Chain Conveyor GameTest's server trace tables."""
import argparse
import csv
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TICKS = {"rising_reversal": 67, "straight": 80}
ACTIONS = ("insufficient", "connected", "disconnected")
FIELDS = {
    "connection": (
        "scenario", "action", "edge", "chain_cost", "inventory_chains", "a_has_edge",
        "b_has_edge", "tangent_angle", "chain_length", "start_x", "start_y", "start_z",
        "end_x", "end_y", "end_z",
    ),
    "world": (
        "scenario", "tick", "a_rpm", "b_rpm", "a_has_edge", "b_has_edge", "a_reversed",
        "b_reversed", "a_route_for_lab_in", "frogport_animation", "frogport_custody",
    ),
    "package": (
        "scenario", "tick", "wheel", "path", "edge", "payload", "chain_position",
        "anchor_x", "anchor_y", "anchor_z",
    ),
}


def rows_at(log, name, ticks=TICKS):
    pattern = re.compile(rf"CREATE_CHAIN_{name.upper()} ([^\r\n]+)")
    rows = list(csv.reader(pattern.findall(log)))
    if not rows or any(len(row) != len(FIELDS[name]) or row[0] not in ticks for row in rows):
        raise ValueError(f"incomplete or malformed {name} capture")
    if name == "connection":
        rows.sort(key=lambda row: (row[0], ACTIONS.index(row[1])))
        if [(row[0], row[1]) for row in rows] != [
            (case, action) for case in ticks for action in ACTIONS
        ]:
            raise ValueError("each connection case needs a refusal, connection, and removal")
    else:
        rows.sort(key=lambda row: (row[0], int(row[1]), *row[2:6]))
        if name == "world":
            expected = [(case, tick) for case, length in ticks.items() for tick in range(length)]
            if [(row[0], int(row[1])) for row in rows] != expected:
                raise ValueError("the Java world trace has missing or duplicate ticks")
        elif {row[0] for row in rows} != set(ticks):
            raise ValueError("missing package scenario")
    return rows


def player_trace(log, world, packages, output):
    angles = dict(re.findall(r"CREATE_CHAIN_PLAYER_ANGLE (port|package),(\d+)", log))
    if set(angles) != {"port", "package"}:
        raise ValueError("missing Java loop selection observations")
    selected = {
        int(row[1]): row for row in packages if row[0] == "straight" and row[5] == "Lab-In:paper:3"
    }
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("tick", "port_angle", "wheel", "path", "edge", "position", "progress", "custody"))
        for row in world:
            if row[0] != "straight" or (tick := int(row[1])) < 2:
                continue
            motion = selected.get(tick)
            if tick == 2 and int(float(motion[6])) != int(angles["package"]):
                raise ValueError("package did not start at the selected Java loop angle")
            writer.writerow((tick - 2, angles["port"],
                             *((motion[2], motion[3], motion[4], motion[6]) if motion else ("-",) * 4),
                             row[9], row[10]))
            if row[10].startswith("inventory:"):
                break


def wrench_trace(log, output):
    drops = sorted(csv.reader(re.findall(r"CREATE_CHAIN_WRENCH_DROP ([^\r\n]+)", log)))
    hits = sorted(csv.reader(re.findall(r"CREATE_CHAIN_WRENCH_HIT ([^\r\n]+)", log)))
    if [row[0] for row in hits] != list(TICKS) or [(row[0], row[1]) for row in drops] != [
        (name, payload) for name in TICKS for payload in ("Removed-A:paper:3", "Removed-B:string:2")
    ]:
        raise ValueError("missing Java wrench hits or dropped packages")
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("scenario", "payload", "x", "y", "z"))
        writer.writerows(drops)


def span_target_trace(log, output):
    rows = sorted(csv.reader(re.findall(r"CREATE_CHAIN_SPAN_SELECTION ([^\r\n]+)", log)))
    if [row[0] for row in rows] != list(TICKS) or any(len(row) != 4 for row in rows):
        raise ValueError("missing Java span targets")
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("scenario", "wheel", "edge", "position"))
        writer.writerows(rows)


def visual_trace(log, output):
    fields = {
        "SPAN": ("scenario", "wheel", "yaw", "pitch", "length"),
        "PORT": ("scenario", "tick", "yaw", "pitch", "base_head", "base_length",
                 "progress", "head", "tongue", "scale"),
    }
    output.mkdir(parents=True, exist_ok=True)
    for kind, header in fields.items():
        rows = sorted(csv.reader(re.findall(rf"CREATE_CHAIN_VISUAL_{kind} ([^\r\n]+)", log)))
        if len(rows) != (4 if kind == "SPAN" else 9) or any(len(row) != len(header) for row in rows):
            raise ValueError(f"missing Java visual {kind} rows")
        with (output / f"chain-conveyor-visual-{kind.lower()}-java.csv").open("w", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(rows)


def outbound_trace(log, output):
    rows = list(csv.reader(re.findall(r"CREATE_CHAIN_FROGPORT_OUT ([^\r\n]+)", log)))
    if any(len(row) != 6 for row in rows) or [int(row[0]) for row in rows] != list(range(35, 69)):
        raise ValueError("missing Java Frogport outbound ticks")
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("tick", "progress", "depositing", "stored", "animated", "position"))
        writer.writerows(rows)


def launch_visual_trace(log, output):
    rows = list(csv.reader(re.findall(r"CREATE_CHAIN_VISUAL_SEND ([^\r\n]+)", log)))
    if any(len(row) != 9 for row in rows) or [int(row[0]) for row in rows] != list(range(37, 46)):
        raise ValueError("missing Java Frogport launch poses")
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("tick", "yaw", "pitch", "base_head", "base_length", "progress", "head", "tongue", "scale"))
        writer.writerows(rows)


def retrieval_trace(log, output):
    rows = sorted(csv.reader(re.findall(r"CREATE_CHAIN_RETRIEVAL ([^\r\n]+)", log)))
    if any(len(row) != 6 for row in rows) or [(row[0], row[1]) for row in rows] != [
        (scenario, path) for scenario in TICKS for path in ("loop", "span")
    ]:
        raise ValueError("missing Java package retrieval cases")
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("scenario", "path", "tick", "position", "address", "destination"))
        writer.writerows(rows)


def port_reload_trace(log, output):
    saved = re.findall(r"CREATE_CHAIN_RELOAD_SAVED ([^\r\n]+)", log)
    rows = list(csv.reader(re.findall(r"CREATE_CHAIN_RELOAD_PORT ([^\r\n]+)", log)))
    if saved != ["27,0.400000006,true"] or [int(row[0]) for row in rows] != list(range(27, 40)):
        raise ValueError("missing Java Frogport snapshot and reload observations")
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("tick", "progress", "custody"))
        writer.writerows(rows)


def adjacent_trace(log, output):
    rows = list(csv.reader(re.findall(r"CREATE_CHAIN_ADJACENT ([^\r\n]+)", log)))
    if any(len(row) != 7 for row in rows) or [int(row[0]) for row in rows] != list(range(35, 53)):
        raise ValueError("missing Java Frogport adjacent transfer observations")
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("tick", "received_below", "outbound_below", "port_custody", "progress",
                         "launched", "stick_untouched"))
        writer.writerows(rows)


def blocked_barrel_trace(log, output):
    rows = list(csv.reader(re.findall(r"CREATE_CHAIN_BLOCKED_BARREL ([^\r\n]+)", log)))
    if any(len(row) != 5 for row in rows) or [int(row[0]) for row in rows] != list(range(35, 53)):
        raise ValueError("missing Java Frogport blocked barrel observations")
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("tick", "blocked", "received", "custody", "sticks"))
        writer.writerows(rows)


def branch_trace(log, packages, output, *, shape="branch"):
    length = 230 if shape == "relink" else 70
    rows = list(csv.reader(re.findall(r"CREATE_CHAIN_BRANCH ([^\r\n]+)", log)))
    if any(len(row) != 8 for row in rows) or [int(row[0]) for row in rows] != list(range(length)):
        raise ValueError("missing Java Chain Conveyor branch observations")
    output.mkdir(parents=True, exist_ok=True)
    tables = {
        "world": (("tick", "east_route", "south_route", "side_rpm", "east_progress",
                   "east_custody", "south_progress", "south_custody"), rows),
        "package": (FIELDS["package"], [row for row in packages if row[0] == "straight" and int(row[1]) < length]),
    }
    if shape != "branch":
        intermediate = list(csv.reader(re.findall(r"CREATE_CHAIN_RELAY ([^\r\n]+)", log)))
        if any(len(row) != 2 for row in intermediate) or [int(row[0]) for row in intermediate] != list(range(length)):
            raise ValueError("missing Java Chain Conveyor relay observations")
        fields, samples = tables["world"]
        tables["world"] = ((*fields, "relay_route"), [
            (*row, other[1]) for row, other in zip(samples, intermediate, strict=True)
        ])
    for kind, (fields, samples) in tables.items():
        with (output / f"chain-conveyor-{shape}-{kind}-java.csv").open("w", newline="") as stream:
            csv.writer(stream, lineterminator="\n").writerows([fields, *samples])


def offhand_trace(log, output):
    rows = list(csv.reader(re.findall(r"CREATE_CHAIN_OFFHAND ([^\r\n]+)", log)))
    order = ("insufficient", "connected")
    rows.sort(key=lambda row: (row[0], order.index(row[1])))
    if any(len(row) != 4 for row in rows) or [(row[0], row[1]) for row in rows] != [
        (scenario, action) for scenario in TICKS for action in order
    ]:
        raise ValueError("missing Java offhand-only chain use observations")
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("scenario", "action", "offhand_count", "main_empty"))
        writer.writerows(rows)


def suspended_trace(log, output, *, rising=False):
    marker = "CREATE_CHAIN_SUSPENDED_RISING" if rising else "CREATE_CHAIN_SUSPENDED"
    end = 67 if rising else 24
    rows = list(csv.reader(re.findall(rf"{marker} ([^\r\n]+)", log)))
    if any(len(row) != 12 for row in rows) or [int(row[0]) for row in rows] != list(range(2, end)):
        raise ValueError("missing Java suspended package poses")
    if len({row[2] for row in rows}) != 1:
        raise ValueError("Java replaced the package identity during transfer")
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("tick", "wheel", "id", "target_x", "target_y", "target_z",
                         "physical_x", "physical_y", "physical_z", "yaw", "roll", "pitch"))
        writer.writerows(rows)


def suspended_light_trace(log, output):
    rows = list(csv.reader(re.findall(r"CREATE_CHAIN_SUSPENDED_LIGHT ([^\r\n]+)", log)))
    if any(len(row) != 8 for row in rows) or [int(row[0]) for row in rows] != list(range(2, 24)):
        raise ValueError("missing Java suspended package light samples")
    if not any(row[4] != row[6] for row in rows):
        raise ValueError("Java package and wheel lighting never differ")
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("tick", "cell_x", "cell_y", "cell_z", "block", "sky", "wheel_block", "wheel_sky"))
        writer.writerows(rows)


def wheel_sky_trace(log, output):
    rows = list(csv.reader(re.findall(r"CREATE_CHAIN_WHEEL_SKY ([^\r\n]+)", log)))
    if len(rows) != 2 or any(len(row) != 7 for row in rows) or [row[0] for row in rows] != ["A", "B"]:
        raise ValueError("missing Java wheel skylight samples")
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("wheel", "dampening", "passes_sky", "occludes", "above", "inside", "below"))
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "fixtures")
    parser.add_argument("--player-output", type=Path)
    parser.add_argument("--wrench-output", type=Path)
    parser.add_argument("--span-target-output", type=Path)
    parser.add_argument("--visual-output", type=Path)
    parser.add_argument("--outbound-output", type=Path)
    parser.add_argument("--launch-visual-output", type=Path)
    parser.add_argument("--retrieval-output", type=Path)
    parser.add_argument("--port-reload-output", type=Path)
    parser.add_argument("--adjacent-output", type=Path)
    parser.add_argument("--blocked-barrel-output", type=Path)
    parser.add_argument("--branch-output", type=Path)
    parser.add_argument("--relay-output", type=Path)
    parser.add_argument("--relink-output", type=Path)
    parser.add_argument("--offhand-output", type=Path)
    parser.add_argument("--suspended-output", type=Path)
    parser.add_argument("--suspended-rising-output", type=Path)
    parser.add_argument("--suspended-light-output", type=Path)
    parser.add_argument("--wheel-sky-output", type=Path)
    args = parser.parse_args()
    log = args.log.read_text()
    if "All 2 required tests passed" not in log or "BUILD SUCCESSFUL" not in log:
        parser.error("both original Java tests must pass before extracting traces")
    ticks = {**TICKS, "straight": 250} if args.relink_output else TICKS
    tables = {name: rows_at(log, name, ticks) for name in FIELDS}
    if args.player_output:
        player_trace(log, tables["world"], tables["package"], args.player_output)
    if args.wrench_output:
        wrench_trace(log, args.wrench_output)
    if args.span_target_output:
        span_target_trace(log, args.span_target_output)
    if args.visual_output:
        visual_trace(log, args.visual_output)
    if args.outbound_output:
        outbound_trace(log, args.outbound_output)
    if args.launch_visual_output:
        launch_visual_trace(log, args.launch_visual_output)
    if args.retrieval_output:
        retrieval_trace(log, args.retrieval_output)
    if args.port_reload_output:
        port_reload_trace(log, args.port_reload_output)
    if args.adjacent_output:
        adjacent_trace(log, args.adjacent_output)
    if args.blocked_barrel_output:
        blocked_barrel_trace(log, args.blocked_barrel_output)
    if args.branch_output:
        branch_trace(log, tables["package"], args.branch_output)
    if args.relay_output:
        branch_trace(log, tables["package"], args.relay_output, shape="relay")
    if args.relink_output:
        branch_trace(log, tables["package"], args.relink_output, shape="relink")
    if args.offhand_output:
        offhand_trace(log, args.offhand_output)
    if args.suspended_output:
        suspended_trace(log, args.suspended_output)
    if args.suspended_rising_output:
        suspended_trace(log, args.suspended_rising_output, rising=True)
    if args.suspended_light_output:
        suspended_light_trace(log, args.suspended_light_output)
    if args.wheel_sky_output:
        wheel_sky_trace(log, args.wheel_sky_output)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        target = args.output / f"chain-conveyor-{name}-java.csv"
        with target.open("w", newline="") as stream:
            csv.writer(stream, lineterminator="\n").writerows([FIELDS[name], *rows])
        print(f"{target} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
