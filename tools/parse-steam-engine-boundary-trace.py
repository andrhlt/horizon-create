#!/usr/bin/env python3
"""Extract Java CREATE_STEAM_BOUNDARY rows into the replay CSV format."""

import argparse
import csv
from pathlib import Path
import re

HEADER = (
    "tick", "supply", "pump_a_speed", "pump_b_speed", "engines", "active_heat", "passive_heat",
    "shaft_a_speed", "shaft_a_power", "shaft_b_speed", "shaft_b_power",
    "speedometer_rpm", "stress_capacity",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = []
    pattern = re.compile(r"CREATE_STEAM_BOUNDARY\s+(.+)")
    for line in args.log.read_text(errors="replace").splitlines():
        match = pattern.search(line)
        if not match:
            continue
        fields = match[1].split()
        if len(fields) != len(HEADER):
            raise SystemExit(f"Malformed Java steam row ({len(fields)} fields): {line}")
        rows.append(fields)
    if len(rows) != 221 or [int(row[0]) for row in rows] != list(range(221)):
        raise SystemExit(f"Expected Java ticks 0..220 (221 rows); found {len(rows)} rows")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(rows)
    print(f"Wrote {len(rows)} pinned-Java steam samples to {args.output}")


if __name__ == "__main__":
    main()
