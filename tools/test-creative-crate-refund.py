#!/usr/bin/env python3
"""Use a real List Filter in a Creative Crate and recover it by replacing the filter."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
ENV = {
    "HORIZON_NO_AUDIO": "1",
    "HORIZON_CREATE_TEST_AUDIO": "1",
    "HORIZON_CREATE_ELEVATOR_TRACE": "1",
}
FILTER_SOUND = "CREATE_ELEVATOR_PLAYBACK minecraft:entity.item_frame.add_item,"
FILTER = "create:filter"


def run(args, scratch):
    with (ROOT / "fixtures/creative_crate_refund-java.csv").open() as file:
        expected = next(row for row in csv.DictReader(file) if row["case"] == args.case)
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, "CreativeCrateRefund",
                                                    render=not args.lan or args.audio, pack=args.pack, env=ENV))
        actor, player = host, "@s"
        if args.lan:
            player = "CrateRefund"
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            actor = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario="creative-crate-refund", pack=args.pack, env=ENV))
            mp.until("the guest to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]))
        if args.lan and args.audio:
            host.command("/tp @s 10.5 171 24.5")
        mode = "survival" if args.case == "survival" else "creative"
        host.call("command", f"/gamemode {mode} {player}")
        host.commands((
            "/fill 5 169 17 15 169 27 minecraft:stone",
            "/fill 5 170 17 15 175 27 minecraft:air",
            "/setblock 9 170 24 minecraft:stone",
            "/setblock 9 171 22 create:creative_crate",
            f"/tp {player} 9.5 171 24.5",
            f"/item replace entity {player} hotbar.0 with {FILTER}[minecraft:custom_data={{marker:17}}]",
            f"/item replace entity {player} hotbar.1 with minecraft:iron_ingot 7",
        ))
        mp.until("the tagged List Filter", lambda: mp.count(actor, FILTER) == 1)
        actor.call("select", FILTER)
        actor.call("look-at", 9.5, 172, 22.5)
        def target():
            hit = actor.call("looking-at").get("block")
            return hit and hit["pos"] == [9, 171, 22] and hit["face"] == "up"
        mp.until("the crate value box", target)
        actor.call("mouse", "right", "click")
        def installed():
            result = host.command("/data get block 9 171 22 Filter")
            return all(part in result for part in ('"create:filter"', 'count: 1', 'marker: 17',
                                                   '"!minecraft:enchantments"', '"!minecraft:attribute_modifiers"'))
        try:
            mp.until("the Java-normalized stored filter", installed)
        except RuntimeError as error:
            raise AssertionError(host.command("/data get block 9 171 22")) from error
        mp.until("the expected List Filter count after insertion",
                 lambda: mp.count(actor, FILTER) == int(expected["held_after_set"]))
        has_copy = args.case in ("creative_has_copy", "creative_exact_copy")
        if args.case == "creative_has_copy":
            host.command(f"/item replace entity {player} hotbar.2 with {FILTER}[minecraft:custom_data={{marker:17}}]")
        if args.case == "creative_exact_copy":
            saved = host.command("/data get block 9 171 22 Filter").split(": ", 1)[1]
            host.commands((
                "/setblock 12 171 22 minecraft:barrel",
                "/data merge block 12 171 22 {Items:[{Slot:0b," + saved[1:] + "]}",
                f"/item replace entity {player} hotbar.2 from block 12 171 22 container.0",
            ))
        if has_copy:
            mp.until("the copied List Filter", lambda: mp.count(actor, FILTER) == 2)
        if args.case != "survival":
            host.command(f"/item replace entity {player} hotbar.0 with minecraft:air")
            mp.until("the original held List Filter to be cleared",
                     lambda: mp.count(actor, FILTER) == int(has_copy))
        actor.call("select", "minecraft:iron_ingot")
        mp.until("the same value box", target)
        actor.call("mouse", "right", "click")
        mp.until("the iron filter", lambda: '"minecraft:iron_ingot"' in host.command("/data get block 9 171 22 Filter"))
        mp.until("the refunded List Filter", lambda: mp.count(actor, FILTER) == int(expected["filters_after_replace"]))
        assert mp.count(actor, "minecraft:iron_ingot") == int(expected["replacement_hand"])
        inventory = actor.call("inventory")
        restored = [slot["components"] for slot in inventory["hotbar"] + inventory["main"]
                    if slot.get("item") == FILTER and "components" in slot]
        assert any("marker:17" in data for data in restored) == (expected["marker_retained"] == "true"), restored
        if args.audio:
            for listener in (host,) if actor is host else (host, actor):
                log = listener.socket.parent / "ctl.log"

                def sounds():
                    return [line.split(FILTER_SOUND, 1)[1].split(",")
                            for line in log.read_text().splitlines() if FILTER_SOUND in line]

                role = "host" if listener is host else "guest"
                try:
                    mp.until(f"both muted Creative Crate filter sounds on the {role}",
                             lambda: len(sounds()) >= 2)
                except RuntimeError as error:
                    raise AssertionError((role, sounds())) from error
                recordings = sounds()
                assert len(recordings) == 2, recordings
                for category, x, y, z, volume, pitch in recordings:
                    assert category == "4" and tuple(map(float, (x, y, z))) == (9.5, 171.5, 22.5), recordings
                    assert abs(float(volume) - 0.25) < 1e-6 and abs(float(pitch) - 0.1) < 1e-6, recordings
        print(f"{args.case}: List Filter handling and refund matched Java with seven iron retained.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--audio", action="store_true")
    parser.add_argument("--case", choices=("survival", "creative_has_copy", "creative_no_copy",
                                             "creative_exact_copy"),
                        default="survival")
    with TemporaryDirectory(prefix="hc-crate-refund-", dir="/private/tmp") as scratch:
        run(parser.parse_args(), Path(scratch))
