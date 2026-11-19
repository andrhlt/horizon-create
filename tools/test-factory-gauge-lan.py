#!/usr/bin/env python3
"""Connect a Factory Panel to a Display Link as a LAN guest and display real stock."""
import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import fixture_world

mp = import_module("test-multiplayer")
placement = import_module("test-clipboard-placement")
GAUGE = "create:factory_gauge"
FREQ = "Freq: [I; 42, 123, -456, 789]"


def target(actor, point, pos):
    actor.call("look-at", *point)
    mp.until(f"the guest to target {pos}", lambda:
             (actor.call("looking-at").get("block") or {}).get("pos") == list(pos))
    actor.call("wait", 4)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "FactoryGaugeLAN", render=True, pack=args.pack,
                                                  env={"HORIZON_NO_AUDIO": "1"}))
        host.commands(("/fill 8 169 20 20 169 28 minecraft:stone",
                       "/setblock 10 170 24 create:stock_link[face=floor]",
                       f"/data merge block 10 170 24 {{{FREQ}}}",
                       "/setblock 14 171 24 minecraft:stone",
                       "/setblock 13 171 24 minecraft:stone",
                       "/setblock 13 171 23 create:display_link[facing=north]",
                       "/setblock 13 172 23 create:nixie_tube",
                       "/data merge block 13 171 23 {TargetOffset:[I;0,1,0],TargetLine:0}",
                       "/setblock 17 170 24 minecraft:barrel",
                       "/setblock 18 170 24 create:packager[facing=east]",
                       "/setblock 18 171 24 create:stock_link[face=floor]",
                       f"/data merge block 18 171 24 {{{FREQ}}}",
                       "/item replace block 17 170 24 container.0 with minecraft:iron_ingot 12"))
        port = host.call("lan", "open", 0, "commands", "force")["port"]
        scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-factory-gauge-lan-")))
        actor = stack.enter_context(mp.joined_client(args, scratch, f"127.0.0.1:{port}", "GaugeGuest",
                                                     render=True, scenario="factory-gauge-lan", pack=args.pack,
                                                     env={"HORIZON_NO_AUDIO": "1"}))
        mp.until("the Gauge guest to join", lambda: any(
            entry["name"] == "GaugeGuest" and entry["placed"] for entry in host.call("lan", "status")["guests"]))
        host.commands(("/gamemode survival GaugeGuest", "/clear GaugeGuest",
                       f"/item replace entity GaugeGuest hotbar.0 with {GAUGE}",
                       "/tp GaugeGuest 10.5 170 22.5"))
        mp.until("the guest to hold a Gauge by the Stock Link", lambda:
                 mp.count(actor, GAUGE) == 1 and actor.call("state")["player"]["position"] == [10.5, 170.0, 22.5])
        actor.call("select", GAUGE)
        target(actor, (10.5, 170.18, 24.5), (10, 170, 24))
        actor.call("mouse", "right", "click")
        mp.until("the guest's Gauge to tune to the network", lambda:
                 FREQ in host.command("/data get entity GaugeGuest SelectedItem"))
        host.command("/tp GaugeGuest 14.5 170 22.5")
        mp.until("the guest to approach the Gauge support", lambda:
                 actor.call("state")["player"]["position"] == [14.5, 170.0, 22.5])
        target(actor, (14.25, 171.25, 24.0), (14, 171, 24))
        actor.call("mouse", "right", "click")
        mp.until("the guest to place the tuned Gauge", lambda:
                 host.call("block", 14, 171, 23)["block"] == GAUGE and mp.count(actor, GAUGE) == 0)
        host.command("/item replace entity GaugeGuest hotbar.0 with minecraft:iron_ingot 5")
        mp.until("the guest to receive the iron filter", lambda: mp.count(actor, "minecraft:iron_ingot") == 5)
        actor.call("select", "minecraft:iron_ingot")
        target(actor, (14.25, 171.25, 23.875), (14, 171, 23))
        actor.call("mouse", "right", "click")
        mp.until("the selected Gauge panel to hold its iron filter", lambda:
                 "minecraft:iron_ingot" in host.command("/data get block 14 171 23 bottom_right"))
        assert mp.count(actor, "minecraft:iron_ingot") == 5
        actor.call("key", "2", "tap")
        target(actor, (14.25, 171.25, 23.875), (14, 171, 23))
        actor.call("mouse", "right", "click")
        mp.until("the guest's panel configuration", lambda:
                 any(b.get("label") == "Add new connection" for b in actor.call("screen").get("buttons", [])))
        actor.call("click-button", "Add new connection")
        mp.until("the panel configuration to close", lambda: actor.call("state")["screen"] == "playing")
        target(actor, (13.5, 171.5, 23.875), (13, 171, 23))
        actor.call("mouse", "right", "click")
        def connected():
            data = host.command("/data get block 13 171 23 LinkedGauges")
            return "bottom_right" in data and "14, 171, 23" in data
        mp.until("the guest's connection to reach the host", connected)
        print("LAN guest connected its filtered lower panel to the Display Link.", flush=True)
        host.step_to(host.clock() + 1)
        target(actor, (13.5, 171.5, 23.875), (13, 171, 23))
        actor.call("mouse", "right", "click")
        mp.until("the guest's Gauge source option", lambda:
                 any(b.get("label") == "Factory gauge status" for b in actor.call("screen").get("buttons", [])))
        actor.call("click-button", "Factory gauge status")
        def displayed():
            data = host.command("/data get block 13 172 23 CustomText")
            return data if "12" in data and "Iron Ingot" in data else None
        result = mp.until("the host Nixie to show twelve network iron", displayed)
        print(f"LAN guest configured Gauge stock output: {result}")


if __name__ == "__main__":
    main()
