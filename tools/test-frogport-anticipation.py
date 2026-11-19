#!/usr/bin/env python3
"""Compare the Frogport pre-catch signals and head pose on a loop or rising span."""

import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

effects = import_module("test-frogport-package-effects")
chain, player, multiplayer = effects.chain, effects.player, effects.multiplayer
A, B, LOOP_PORT = effects.A, effects.B, effects.PORT
SPAN_PORT = (12, 101, -8)
RISING = (6, 2, 3)
ENV = effects.ENV | {"CREATE_FROGPORT_ANTICIPATION": "1"}


def log(actor):
    return (actor.socket.parent / "ctl.log").read_text()


def configure(host, span):
    if span:
        other = tuple(origin + delta for origin, delta in zip(A, RISING, strict=True))
        chain.setup(host, A, other, (8, 101, -10), SPAN_PORT, RISING, True, warm=7)
        host.commands(("/setblock 12 101 -8 create:package_frogport", "/fill 10 100 -6 15 100 -3 minecraft:stone"))
        chain.merge(host, SPAN_PORT, '{AddressFilter:"Lab-In",Target:{RelativePos:[I;-4,1,-2],ChainPosition:2.4f,Connection:[I;6,2,3]}}')
        chain.merge(host, A, "{PackagePorts:[{Port:[I;4,-1,2],ChainPosition:2.4f,Connection:[I;6,2,3]}]}")
        return SPAN_PORT, (13.5, 101.0, -4.5)
    chain.setup(host, A, B, (8, 101, -10), LOOP_PORT, (7, 0, 0), False, warm=7)
    host.command("/fill 14 99 -8 20 99 -3 minecraft:stone")
    chain.merge(host, LOOP_PORT, '{AddressFilter:"Lab-In",Target:{RelativePos:[I;-2,2,0],ChainPosition:150f}}')
    chain.merge(host, B, "{PackagePorts:[{Port:[I;2,-2,0],ChainPosition:150f}]}")
    return LOOP_PORT, (17.5, 100.0, -5.5)


def custody(host, port):
    box = player.get(host, port, "ReceivingPackage")
    if box and "create:package_address" in box:
        return "animation:" + chain.payload(box)
    items = player.get(host, port, "Items")
    if items and "create:package_address" in items:
        return "inventory:" + chain.payload(items)
    return "-"


def check(host_log, client_log, at, start, requests):
    pos = re.escape(str(list(at)))
    actual = [int(tick) - start for tick in re.findall(rf"CREATE_FROGPORT_ANTICIPATE_REQUEST {pos},(\d+)", host_log)]
    assert actual == requests, (actual, requests)
    seen = list(dict.fromkeys(int(tick) - start for tick in re.findall(
        rf"CREATE_FROGPORT_ANTICIPATE_TICK {pos},\d+,(\d+),", client_log)))
    assert seen == requests, (seen, requests)
    catch = re.search(rf"CREATE_FROGPORT_PACKAGE_START {pos},\d+,(\d+),false", client_log)
    assert catch, "client did not see the catch"
    assert int(catch[1]) - start == requests[-1] + 1
    frames = re.findall(rf"CREATE_FROGPORT_ANTICIPATE_MODEL {pos},\d+,([\d.]+),([\d.]+),([\d.]+)",
                        client_log[:catch.start()])
    assert frames, "no rendered anticipatory head movement before the catch"
    for phase, head, base in frames:
        phase, head, base = map(float, (phase, head, base))
        assert abs(head - base * max(0, 1 - (phase * 1.25 * 2 - 1)**4)) < 4e-5
    print(f"Requests at Java ticks {requests}, catch at {requests[-1] + 1}, {len(frames)} pre-catch render frames")


def run(args):
    scenario = "rising_span" if args.span else "straight_loop"
    mode = ("Span" if args.span else "Loop") + ("Lan" if args.lan else "Solo")
    requests = [int(row["tick"]) for row in effects.read_fixture("frogport-anticipation-java.csv")
                if row["scenario"] == scenario]
    if args.span:
        reference = {int(row["tick"]): row["custody"]
                     for row in effects.read_fixture("frogport-anticipation-span-custody-java.csv")}
    else:
        reference = {int(row["tick"]): row["frogport_custody"]
                     for row in effects.read_fixture("chain-conveyor-world-java.csv")
                     if row["scenario"] == "straight" and 18 <= int(row["tick"]) <= 33}
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "FrogportAnticipate" + mode, pack=args.pack,
                                                 render=not args.lan, env=ENV))
        port, feet = configure(host, args.span)
        actor, name = host, "@s"
        if args.lan:
            lan = host.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-anticipation-")))
            name = "FrogportWatcher"
            actor = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{lan}", name, pack=args.pack,
                render=True, env=ENV, scenario="frogport-anticipation-" + mode,
            ))
            multiplayer.until("an observer to join", lambda:
                              any(g["name"] == name and g["placed"] for g in host.call("lan", "status")["guests"]))
        host.command(f"/tp {name} {chain.coords(feet)}")
        multiplayer.until("the observer to reach the Frogport", lambda:
                          actor.call("state")["player"]["position"] == list(feet))
        actor.call("look-at", port[0] + 0.5, port[1] + 0.65, port[2] + 0.5)
        actor.call("wait", 4)
        host_offset, actor_offset = len(log(host)), len(log(actor))
        start = host.clock()
        cargo = chain.stack("Lab-In", "paper", 3)
        if args.span:
            chain.merge(host, A, f"{{Packages:[{{Item:{cargo},Position:0f,Connection:[I;6,2,3]}}]}}")
        for tick in range(max(reference) + 2):
            if tick:
                host.step_to(start + tick)
            if tick == 2 and not args.span:
                chain.merge(host, A, f"{{Packages:[{{Item:{cargo},Position:40f}}]}}")
            if tick in reference:
                seen = custody(host, port)
                assert seen == reference[tick], (tick, seen, reference[tick])
            if requests[0] <= tick <= requests[-1] + 2:
                actor.call("wait", 2)
        check(log(host)[host_offset:], log(actor)[actor_offset:], port, start, requests)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--span", action="store_true")
    run(parser.parse_args())
