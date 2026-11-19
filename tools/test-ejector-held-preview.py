#!/usr/bin/env python3
"""Replay the original placement arc while holding a Weighted Ejector."""
from argparse import ArgumentParser
from contextlib import ExitStack
import csv
import json
from importlib import import_module
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
wrench = import_module("test-ejector-wrench-preview")
click_target = import_module("test-ejector-target-click").click
EJECTOR = "create:weighted_ejector"
GUEST = "EjectHeldGuest"
TARGET = (9, 104, -11)

ARC = "CREATE_EJECTOR_HELD_ARC "
OUTLINE = "CREATE_EJECTOR_HELD_OUTLINE "


def at(log):
    return log.stat().st_size


def point(host, actor, name, at_block):
    x, y, z = at_block
    view = (x - 1.5, 104, z + .5)
    where = " ".join(map(str, view))
    host.command(f"/tp {name} {where}")
    multiplayer.until("player has received the fixture position", lambda:
                      actor.call("state")["player"]["position"] == list(view))
    actor.call("look-at", x + .5, y + 1, z + .5)
    multiplayer.until("player targets the fixture face", lambda:
                      (actor.call("looking-at").get("block") or {}).get("pos") == list(at_block))
    actor.call("wait", 3)


def mark(actor):
    actor.call("key", "shift", "down")
    actor.call("wait", 3)
    try:
        actor.call("interact", *TARGET, "up")
        multiplayer.until("the target mark acknowledgement", lambda:
                          actor.call("messages")["actionbar"] == "Target Selected")
    finally:
        actor.call("key", "shift", "up")


def check_case(text, color, reference):
    expected_outline = OUTLINE + ",".join(reference[key] for key in (
        "target_x", "target_y", "target_z", "min_x", "min_y", "min_z", "max_x", "max_y", "max_z",
        "outline_color", "line_width"))
    assert expected_outline in text, "The selected block had no amber outline"
    if color is None:
        assert ARC not in text, "The invalid placement unexpectedly showed an arc"
        return 0
    passed = 0
    expected = reference | {"dust_color": color}
    for arc in text.split(ARC)[1:]:
        metadata = arc.splitlines()[0].split(",")
        dust = [row.split(",") for row in re.findall(r"CREATE_EJECTOR_HELD_DUST ([^\r\n]+)", arc)]
        if len(metadata) != 11 or len(dust) != int(metadata[7]):
            continue
        wrench.compare_dust(metadata, dust, expected)
        passed += len(dust)
    assert passed >= 16, f"Only {passed} complete dust positions for {color}"
    return passed


def main():
    parser = ArgumentParser()
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/weighted-ejector-held-preview-java.csv")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    os.environ["CREATE_EJECTOR_HELD_PREVIEW"] = "1"
    with (ROOT / "fixtures/weighted-ejector-wrench-java.csv").open() as original:
        reference = next(csv.DictReader(original))
    with args.reference.open() as source:
        cases = list(csv.DictReader(source))
    with ExitStack() as stack:
        suffix = "LAN" if args.lan else "Solo"
        host = stack.enter_context(fixture_world(args, "EjectorHeldPreview" + suffix, render=True, pack=args.pack))
        actor, name = host, "@s"
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-eject-held-")))
            actor = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", GUEST, render=True, scenario="eject-held", pack=args.pack))
            name = GUEST
            multiplayer.until("guest enters the target preview world", lambda:
                              any(p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]))
            host.command(f"/give @s {EJECTOR}")
            host.call("select", EJECTOR)
        setup = (
            "/fill 3 103 -16 13 103 -8 minecraft:smooth_stone",
            "/setblock 9 104 -11 minecraft:smooth_stone",
            f"/gamemode creative {name}",
            f"/give {name} {EJECTOR}",
        )
        host.call("script", script="".join(f"command {json.dumps(command)}\n" for command in setup))
        multiplayer.until("player holds the Ejector stack", lambda: multiplayer.count(actor, EJECTOR) == 1)
        actor.call("select", EJECTOR)
        host.command("/tick unfreeze")
        log = actor.socket.parent / "ctl.log"
        if args.lan:
            point(host, host, "@s", (5, 103, -11))
            host_log = host.socket.parent / "ctl.log"
            host_offset = at(host_log)
        point(host, actor, name, TARGET)
        mark(actor)
        total = 0
        raw = []
        for case in cases:
            x, y, z = (int(case[axis]) for axis in "xyz")
            point(host, actor, name, (x, y - 1, z))
            start = at(log)
            actor.call("wait", 6)
            text = wrench.read_since(log, start)
            raw.append(text)
            color = case["dust_color"] or None
            expected = reference
            if color:
                expected = reference | {axis: case[f"projected_{axis}"] for axis in "xyz"}
                expected["dust_count"] = case["dust_count"]
            total += check_case(text, color, expected)
            print(f"{case['case']}: {color or 'outline only'}", flush=True)
        actor.call("select", 9)
        actor.call("wait", 4)
        actor.call("select", EJECTOR)
        point(host, actor, name, (5, 103, -11))
        start = at(log)
        actor.call("wait", 5)
        assert OUTLINE not in wrench.read_since(log, start), "Hotbar switching kept the marked preview."

        point(host, actor, name, TARGET)
        host.command("/tick freeze")
        click_target(host, actor, TARGET, place=True)
        multiplayer.until("selected target acknowledgement", lambda:
                          actor.call("messages")["actionbar"] == "Target Selected")
        click_target(host, actor, TARGET)
        host.command("/tick unfreeze")
        actor.call("wait", 3)
        start = at(log)
        actor.call("wait", 5)
        assert OUTLINE not in wrench.read_since(log, start), "Deselecting kept the marked preview."
        assert host.call("block", *TARGET)["block"] == "minecraft:smooth_stone"

        point(host, actor, name, TARGET)
        start = at(log)
        host.command("/tick freeze")
        click_target(host, actor, TARGET, place=True)
        host.command("/tick unfreeze")
        multiplayer.until("new target outline after re-marking", lambda: OUTLINE in wrench.read_since(log, start))
        host.command("/tick freeze")
        host.command(f"/tp {name} 5.5 104 -12.5")
        host.step_to(host.clock() + 1)
        multiplayer.until("player reaches the placement pose", lambda:
                          actor.call("state")["player"]["position"] == [5.5, 104, -12.5])
        actor.call("look-at", 5.5, 105.62, -8.5)
        actor.call("interact", 5, 103, -11, "up")
        host.step_to(host.clock() + 1)
        multiplayer.until("the physical Ejector placement", lambda:
                          host.call("block", 5, 104, -11)["block"] == EJECTOR)
        host.command("/tick unfreeze")
        placed = host.call("block", 5, 104, -11)
        distance = host.command("/data get block 5 104 -11 HorizontalDistance")
        assert "facing=east" in placed["state"] and distance.endswith(" 4"), (
            f"Placement did not consume the mark: {placed['state']}, {distance}, {actor.call('messages')['actionbar']}"
        )
        actor.call("wait", 4)
        start = at(log)
        actor.call("wait", 5)
        assert OUTLINE not in wrench.read_since(log, start), "Placement kept the marked preview."
        if args.lan:
            assert OUTLINE not in wrench.read_since(host_log, host_offset), "A guest's selected target appeared to the host."
    if args.trace:
        args.trace.write_text("\n".join(raw))
    print(f"{suffix} matched {total} Java dust positions and the original preview lifecycle.")


if __name__ == "__main__":
    main()
