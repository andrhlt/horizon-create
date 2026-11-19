#!/usr/bin/env python3
"""Compare original Java Package impacts and the actual arrow's next frames."""
import argparse
from collections import defaultdict
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

placement = import_module("test-package-placement")
package = placement.package
fire = import_module("test-package-fire")
AT = (8.5, 104.0, -11.5)
ARROW = "minecraft:arrow"
ARROWS = f"@e[type={ARROW},limit=1]"
PIG = "minecraft:pig"


def entities(peer, kind):
    return peer.call("entities", 16, kind)["entities"]


def seed(host, name, scenario):
    host.call("command", f"/kill {fire.SELECTOR}")
    host.call("command", f"/kill {ARROWS}")
    placement.editor.wait_for(host, "the previous package to leave", lambda: not placement.witness(host))
    host.call("command", f"/tp @e[type={PIG}] 50 100 50")
    host.call("command", "/kill @e[type=minecraft:item]")
    mode = "adventure" if scenario == "adventure" else "survival"
    host.call("command", f"/gamemode {mode} {name}")
    assert int(raw_data(host, name, "playerGameType")) == (2 if mode == "adventure" else 0)
    stack = '{id:"create:cardboard_package_12x12",count:1,components:{' \
            '"create:package_contents":[{slot:0,item:{id:"minecraft:clay_ball",count:3}}]}}'
    invulnerable = int(scenario == "invulnerable")
    options = f"{{Silent:1b,PersistenceRequired:1b,Health:5f,Fire:-1s,Invulnerable:{invulnerable}b,equipment:{{mainhand:{stack}}}}}"
    host.command(f"/summon create:package {placement.editor.xyz(AT)} {options}")
    host.command(f"/summon {PIG} {AT[0]+1} {AT[1]} {AT[2]} {{NoAI:1b,Health:10f}}")
    uuid = raw_data(host, name, "UUID")
    pierce = int(scenario == "piercing")
    burn = 100 if scenario == "burning" else -1
    host.command(f"/summon {ARROW} {AT[0]-1.5} {AT[1]+0.375} {AT[2]} "
                 f"{{Motion:[3d,0d,0d],damage:1d,PierceLevel:{pierce}b,Fire:{burn}s,"
                 f"Owner:{uuid},LeftOwner:1b,HasBeenShot:1b}}")
    assert raw_data(host, ARROWS, "Owner") == uuid
    placement.editor.wait_for(host, "the fresh package to spawn", lambda: len(placement.witness(host)) == 1)
    return placement.witness(host)[0]["id"]


def raw_data(host, entity, field=""):
    return host.command(f"/data get entity {entity} {field}".rstrip()).split("entity data: ", 1)[1]


def vector(host, field):
    response = raw_data(host, ARROWS, field)
    return tuple(float(value.strip().removesuffix("d")) for value in response.strip("[]").split(","))


def state(peer, box_id):
    boxes = [view for view in placement.witness(peer) if view["id"] == box_id]
    return (
        bool(boxes), boxes[0]["health"] if boxes else None,
        fire.cargo_near(peer), tuple(pig["health"] for pig in entities(peer, PIG)),
    )


def run_case(host, actor, name, scenario, rows):
    box_id = seed(host, name, scenario)
    start = host.clock()
    for row in rows:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        alive = row["box_removed"] == "false"
        arrow_alive = row["arrow_removed"] == "false"
        expected = (
            alive, float(row["health"]) if alive else None, int(row["spilled"]),
            (float(row["pig_health"]),),
        )
        for peer in (host,) if actor is host else (host, actor):
            try:
                placement.editor.wait_for(peer, f"the {scenario} arrow outcome at tick {tick}",
                                          lambda: state(peer, box_id) == expected)
            except RuntimeError as error:
                raise AssertionError(scenario, row, state(peer, box_id)) from error
        if arrow_alive:
            pos = tuple(x - y for x, y in zip(vector(host, "Pos"), AT, strict=True))
            motion = vector(host, "Motion")
            for reflected, fields in ((pos, ("x", "y", "z")), (motion, ("vx", "vy", "vz"))):
                expected_values = tuple(float(row[key]) for key in fields)
                assert placement.same(reflected, expected_values, 2e-7), (scenario, row, reflected, fields)
            pierce = int(raw_data(host, ARROWS, "PierceLevel").removesuffix("b"))
            assert pierce == int(row["pierce"]), (scenario, row, pierce)
    print(f"{scenario}: {len(rows)} frames", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--case", action="append")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    grouped = defaultdict(list)
    with (ROOT / "fixtures/package-arrow-java.csv").open(newline="") as data:
        for row in csv.DictReader(data):
            grouped[row["case"]].append(row)
    scenarios = args.case or tuple(grouped)
    assert len(grouped) == 5 and sum(map(len, grouped.values())) == 25
    world = "PackageArrowGuest" if args.lan else "PackageArrowHost"
    with TemporaryDirectory(prefix="hc-package-arrow-") as scratch:
        with fixture_world(args, world, render=True, pack=args.pack) as host:
            host.commands((
                "/fill 4 100 -16 16 100 -4 minecraft:obsidian",
                "/fill 4 101 -16 16 112 -4 minecraft:air",
                "/fill 4 103 -12 15 103 -12 minecraft:obsidian",
            ))
            with package.filters.actor_for(host, args, Path(scratch) if args.lan else None) as (actor, name):
                placement.teleport(host, actor, name, (8.5, 101.0, -14.5))
                for scenario in scenarios:
                    run_case(host, actor, name, scenario, grouped[scenario])
    print(f"Matched {sum(len(grouped[s]) for s in scenarios)} original Java Package arrow frames.", flush=True)


if __name__ == "__main__":
    main()
