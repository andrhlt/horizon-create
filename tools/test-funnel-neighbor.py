#!/usr/bin/env python3
"""Replay Java Funnel support changes against authoritative Horizon states."""
from argparse import ArgumentParser
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
GUEST = "FunnelNeighbors"
ITEM_FILTER = 'minecraft:iron_ingot'
DEPOT = "create:depot"
BELT = "create:belt[part=middle,slope={slope},facing={facing}]"
SAW = "create:mechanical_saw[facing={}]"
SUPPORT = (DEPOT, "create:weighted_ejector", DEPOT,
           BELT.format(slope="horizontal", facing="east"), DEPOT, "create:item_drain",
           SAW.format("up"), BELT.format(slope="vertical", facing="east"))
SUPPORT_CHANGES = {
    3: (BELT.format(slope="horizontal", facing="north"), SUPPORT[3]),
    6: (SAW.format("north"), SUPPORT[6]),
    7: (BELT.format(slope="horizontal", facing="east"), BELT.format(slope="sideways", facing="east")),
}


def state(control, pos, case, action, guest=None):
    # A control snapshot can precede a just-completed world edit by a frame.
    # Query the host command queue first, with the game clock still frozen.
    control.clock()
    visible = control.call("block", *pos)["state"]
    if guest is not None:
        mp.until(f"the guest sees the Funnel support change {case}:{action}", lambda:
                 guest.call("block", *pos)["state"] == visible)
    ident, _, entries = visible.rstrip("]").partition("[")
    props = dict(part.split("=", 1) for part in entries.split(",") if "=" in part)
    flag = "belt" if ident.endswith("_belt_funnel") else "plain" if ident.endswith("_funnel") else ident
    observed_filter = control.command("/data get block {} {} {} Filter".format(*pos))
    return [str(case), str(action), flag, props.get("facing", ""), props.get("shape", props.get("extracting", "")),
            props.get("powered", ""), props.get("waterlogged", ""), str(ITEM_FILTER in observed_filter).lower()]


def run_case(control, case, guest=None):
    x, y, z = pos = (5, 105, -11 + case * 3)
    facing = "up" if case == 2 else "north" if case == 3 else "west"
    active = str(case != 0).lower()
    wet = str(case == 4).lower()
    control.commands((
        f"/setblock {x} {y-1} {z} minecraft:air",
        f"/setblock {x+1} {y} {z} minecraft:barrel",
        f"/setblock {x} {y+1} {z} " + ("minecraft:redstone_block" if case == 4 else "minecraft:air"),
        f"/setblock {x} {y} {z} create:brass_funnel[facing={facing},extracting={active},powered={wet},waterlogged={wet}]",
        f'/data merge block {x} {y} {z} {{Filter:{{id:"{ITEM_FILTER}",count:1}}}}',
    ))
    rows = [state(control, pos, case, 0, guest)]
    control.command(f"/setblock {x} {y-1} {z} {SUPPORT[case]}")
    rows.append(state(control, pos, case, 1, guest))
    for action, support in enumerate(SUPPORT_CHANGES.get(case, ()), 2):
        control.command(f"/setblock {x} {y-1} {z} {support}")
        rows.append(state(control, pos, case, action, guest))
    control.command(f"/setblock {x} {y-1} {z} minecraft:air")
    rows.append(state(control, pos, case, 4, guest))
    return rows


def main():
    parser = ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--lan", action="store_true")
    mode.add_argument("--reopen", action="store_true")
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/funnel-neighbor-java.csv")
    args = parser.parse_args()
    with args.reference.open() as source:
        rows = csv.reader(source)
        next(rows)
        expected = [row[:-1] for row in rows]
    scenario = "FunnelNeighbors" + ("LAN" if args.lan else "Reopen" if args.reopen else "")
    with ExitStack() as stack:
        control = stack.enter_context(fixture_world(args, scenario, pack=args.pack))
        guest = None
        if args.lan:
            port = control.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-fneighbors-")))
            guest = stack.enter_context(mp.joined_client(args, scratch, f"127.0.0.1:{port}", GUEST,
                                                       scenario="funnel-neighbors", pack=args.pack))
            mp.until("the observing guest joins", lambda: any(
                player["name"] == GUEST and player["placed"] for player in control.call("lan", "status")["guests"]
            ))
        tick = control.clock()
        actual = [row for case in range(len(SUPPORT)) for row in run_case(control, case, guest)]
        assert control.clock() == tick, "Funnel conversions should be observed on the support change tick."
        if args.reopen:
            # Leave two Funnels mounted so saving exercises both registered forms.
            for case in (0, 4):
                z = -11 + case * 3
                control.command(f"/setblock 5 104 {z} {SUPPORT[case]}")
            control.restart()
            reopen_cases = tuple((case, 1 if case in (0, 4) else 4) for case in range(len(SUPPORT)))
            reopened = [state(control, (5, 105, -11 + case * 3), case, action)
                        for case, action in reopen_cases]
            wanted = {(int(row[0]), int(row[1])): row for row in expected}
            assert reopened == [wanted[key] for key in reopen_cases], reopened
    for row in actual:
        print(",".join(row))
    mismatches = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
    assert not mismatches, f"{len(mismatches)} of {len(expected)} Java projections differ: {mismatches}"
    print(f"Matched {len(expected)} Java Funnel support changes including the retained filter.")


if __name__ == "__main__":
    main()
