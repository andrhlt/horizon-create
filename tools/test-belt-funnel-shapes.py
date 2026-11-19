#!/usr/bin/env python3
"""Replay the original Belt Funnel selection rays in the actual Horizon player view."""
from argparse import ArgumentParser
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
GUEST = "FunnelShapes"
POS = (8, 172, -12)
NORMAL = {
    "north": (0, 0, -1), "south": (0, 0, 1),
    "west": (-1, 0, 0), "east": (1, 0, 0),
}
EYE_HEIGHT = 1.62


def text(pos):
    return " ".join(map(str, pos))


def offset(point, delta):
    return tuple(a + b for a, b in zip(point, delta, strict=True))


def ray(host, actor, name, row, material):
    facing, shape, view, expected_face, *_ = row
    state = f"create:{material}_belt_funnel[facing={facing},shape={shape}]"
    host.command(f"/setblock {text(POS)} {state} strict")
    mp.until("the client receives the Funnel pose", lambda:
             f"shape={shape}" in actor.call("block", *POS)["state"] and
             f"facing={facing}" in actor.call("block", *POS)["state"])
    center = offset(POS, (.5, .75 if view == "front" else .5, .5))
    if view == "front":
        toward = tuple(2 * component for component in NORMAL[facing])
        eye = offset(center, toward)
        aim = offset(center, tuple(-component for component in toward))
    else:
        eye = offset(center, (0, 2.5, 0))
        aim = offset(center, (0, -1.0, 0))
    feet = offset(eye, (0, -EYE_HEIGHT, 0))
    host.command(f"/tp {name} {text(feet)}")
    if actor is not host:
        host.step_to(host.clock() + 1)
    def on_view_ray():
        current = actor.call("state")["player"]["eye"]
        return all(abs(expected - actual) < 1e-5 for expected, actual in zip(eye, current, strict=True))

    mp.until(f"the {name} camera reaches {eye} for {facing}/{shape}/{view}", on_view_ray)
    actor.call("look-at", *aim)
    hit = actor.call("looking-at").get("block")
    if not hit or hit["pos"] != list(POS):
        return ("none",)
    return (hit["face"], *(point - origin for point, origin in zip(hit["point"], POS, strict=True)))


def same(result, row):
    if result[0] != row[3]:
        return False
    return result[0] == "none" or all(abs(act - float(ref)) < 0.0002
                                      for act, ref in zip(result[1:], row[4:], strict=True))


def main():
    parser = ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/belt-funnel-rays-java.csv")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with args.reference.open() as source:
        rows = list(csv.reader(source))[1:]
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "FunnelShapeRays", render=True, pack=args.pack))
        actor, name = host, "@s"
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-fshapes-")))
            actor = stack.enter_context(mp.joined_client(args, scratch, f"127.0.0.1:{port}", GUEST,
                                                       render=True, scenario="funnel-shapes", pack=args.pack))
            name = GUEST
            mp.until("the Funnel shape guest joins", lambda: any(
                p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]
            ))
        host.call("command", f"/gamemode spectator {name}")
        host.command("/fill 4 170 -17 12 177 -7 minecraft:air")
        differences = []
        for material in ("andesite", "brass"):
            for row in rows:
                result = ray(host, actor, name, row, material)
                print(material, ",".join(row), result, flush=True)
                if not same(result, row):
                    differences.append((material, row, result))
    assert not differences, f"{len(differences)} actual rays differ. First: {differences[:6]}"
    print(f"Matched {len(rows) * 2} original Belt Funnel rays in the player view.")


if __name__ == "__main__":
    main()
