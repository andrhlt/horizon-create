#!/usr/bin/env python3
"""Check a Weighted Ejector mark does not carry across a guest reconnect."""
from argparse import ArgumentParser
import csv
from importlib import import_module
import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

eject = import_module("test-ejector-held-preview")
mp = import_module("test-multiplayer")
guest_name = "EjectRejoinGuest"


def joined(args, parent, port):
    return mp.joined_client(args, Path(parent), f"127.0.0.1:{port}", guest_name,
                            render=True, scenario="ejector-target-rejoin", pack=args.pack)


def listed(host):
    return [p for p in host.call("lan", "status")["guests"] if p["name"] == guest_name and p["placed"]]


def main():
    parser = ArgumentParser()
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/weighted-ejector-target-rejoin-java.csv")
    args = parser.parse_args()
    with args.reference.open() as source:
        reference = next(csv.DictReader(source))
    os.environ["CREATE_EJECTOR_HELD_PREVIEW"] = "1"
    os.environ["CREATE_EJECTOR_WRENCH_PREVIEW"] = "1"
    with fixture_world(args, "EjectorTargetRejoin", render=True, pack=args.pack) as host:
        port = host.call("lan", "open", 0, "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-ejr-a-") as first_home:
            with joined(args, first_home, port) as first:
                mp.until("first guest joined", lambda: listed(host))
                setup = (
                    "/fill 3 103 -16 13 103 -8 minecraft:smooth_stone",
                    "/setblock 9 104 -11 minecraft:smooth_stone",
                    f"/gamemode creative {guest_name}",
                    f"/give {guest_name} {eject.EJECTOR}",
                )
                host.call("script", script="".join(f"command {json.dumps(command)}\n" for command in setup))
                mp.until("the guest receives the Ejector", lambda: mp.count(first, eject.EJECTOR) == 1)
                first.call("select", eject.EJECTOR)
                host.command("/tick unfreeze")
                eject.point(host, first, guest_name, eject.TARGET)
                log = first.socket.parent / "ctl.log"
                start = eject.at(log)
                eject.mark(first)
                mp.until("guest sees the initial amber mark", lambda:
                         eject.OUTLINE in eject.wrench.read_since(log, start))
        mp.until("the first guest left LAN", lambda: not listed(host))
        with TemporaryDirectory(prefix="hc-ejr-b-") as second_home:
            with joined(args, second_home, port) as second:
                mp.until("same player reconnects", lambda: listed(host))
                mp.until("the original inventory was kept", lambda: mp.count(second, eject.EJECTOR) == 1)
                second.call("select", eject.EJECTOR)
                host.command("/tick freeze")
                host.command(f"/tp {guest_name} 5.5 104 -12.5")
                host.step_to(host.clock() + 1)
                mp.until("player reaches the placement pose", lambda:
                         second.call("state")["player"]["position"] == [5.5, 104, -12.5])
                second.call("look-at", 5.5, 105.62, -8.5)
                second.call("interact", 5, 103, -11, "up")
                host.step_to(host.clock() + 1)
                mp.until("the physical Ejector placement", lambda:
                         host.call("block", 5, 104, -11)["block"] == eject.EJECTOR)
                host.command("/tick unfreeze")
                mp.until("unmarked placement feedback", lambda:
                         "No Target was Selected" in (second.call("messages")["actionbar"] or ""))
                host.command(f"/give {guest_name} {eject.wrench.WRENCH}")
                mp.until("guest receives the Wrench", lambda: mp.count(second, eject.wrench.WRENCH) == 1)
                second.call("select", eject.wrench.WRENCH)
                log = second.socket.parent / "ctl.log"
                start = eject.at(log)
                host.command(f"/tp {guest_name} 3.5 104 -10.5")
                mp.until("guest reaches the Wrench observation point", lambda:
                         second.call("state")["player"]["position"] == [3.5, 104, -10.5])
                second.call("look-at", 5.5, 104.55, -10.5)
                mp.until("guest looks at the new Ejector", lambda:
                         (second.call("looking-at").get("block") or {}).get("pos") == [5, 104, -11])
                patterns = re.compile(r"CREATE_EJECTOR_WRENCH_ARC 5,104,-11,-?\d+,-?\d+,(\d+),")
                observed = mp.until("Wrench trajectory for the unmarked Ejector", lambda:
                                    patterns.search(eject.wrench.read_since(log, start)))
                assert observed[1] == reference["placement_distance"], (
                    f"Reconnected player used distance {observed[1]}, Java {reference['placement_distance']}."
                )
    print("Rejoining the same host cleared the old Ejector target.")


if __name__ == "__main__":
    main()
