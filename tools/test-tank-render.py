#!/usr/bin/env python3
"""Verify ordinary and creative tank fluid meshes in an offscreen client."""
import argparse
from pathlib import Path
import time
from tempfile import TemporaryDirectory
from importlib import import_module

from fixture_world import ROOT, fixture_world

TRACE = "CREATE_TANK_RENDER "
mp = import_module("test-multiplayer")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True),
                        default=ROOT / ".local/create.hmod")
    parser.add_argument("--frame", type=Path)
    args = parser.parse_args()

    with fixture_world(args, "TankRenderApp1987", render=True, pack=args.pack,
                       env={"CREATE_TANK_RENDER": "1", "HORIZON_NO_AUDIO": "1"}) as control:
        control.commands((
            "/fill 6 169 18 21 169 23 minecraft:smooth_stone",
            "/fill 6 170 18 21 173 23 minecraft:air",
            "/setblock 8 170 20 create:fluid_tank",
            "/setblock 12 170 20 create:creative_fluid_tank",
            "/fill 16 170 20 17 170 21 create:fluid_tank",
            "/time set noon",
        ))
        for _ in range(6):
            control.step_to(control.clock() + 1)

        def fill(x, z, fluid, clicks, expected):
            control.command(f"/setblock {x} 169 19 minecraft:stone")
            control.command(f"/tp @s {x + 0.5} 170 19.5")
            control.call("look-at", x + 0.5, 170.5, z + 0.5)
            item = f"minecraft:{fluid}_bucket"
            for _ in range(clicks):
                control.command(f"/item replace entity @s hotbar.0 with {item}")
                control.step_to(control.clock() + 1)
                control.call("select", item)
                control.call("mouse", "right", "click")
                control.step_to(control.clock() + 1)
            tag = control.command(f"/data get block {x} 170 {z}")
            if f"id: \"minecraft:{fluid}\"" not in tag or f"amount: {expected}" not in tag:
                raise SystemExit(f"Authoritative tank at {(x, 170, z)} did not fill as expected: {tag}")

        fill(8, 20, "water", 4, 4000)
        fill(12, 20, "lava", 1, 8000)
        fill(16, 20, "water", 16, 16000)
        control.command("/setblock 8 169 19 minecraft:stone")
        control.command("/tp @s 8.5 170 19.5")
        control.call("look-at", 8.5, 170.5, 20.5)
        control.command("/item replace entity @s hotbar.0 with minecraft:bucket")
        control.step_to(control.clock() + 1)
        control.call("select", "minecraft:bucket")
        control.call("mouse", "right", "click")
        control.step_to(control.clock() + 1)
        drained = control.command("/data get block 8 170 20")
        if 'id: "minecraft:water"' not in drained or "amount: 3000" not in drained:
            raise SystemExit(f"Authoritative tank drain mismatch: {drained}")
        control.command("/tp @s 13.5 171.2 26.5")
        control.call("look-at", 13.5, 170.6, 20.5)
        control.call("key", "f1", "tap")
        control.call("wait", 3)
        live_text = (control.socket.parent / "ctl.log").read_text()
        control.command("/tick freeze")

        # A cold reopen must rebuild the client block entities from persisted NBT.
        control.restart()
        for pos, fluid, amount in (
            ((8, 170, 20), "water", 3000),
            ((12, 170, 20), "lava", 8000),
            ((16, 170, 20), "water", 16000),
        ):
            saved = control.command(f"/data get block {pos[0]} {pos[1]} {pos[2]}")
            if f'id: "minecraft:{fluid}"' not in saved or f"amount: {amount}" not in saved:
                raise SystemExit(f"Saved authoritative tank state at {pos} did not reopen: {saved}")
        control.command("/tp @s 13.5 171.2 26.5")
        control.call("look-at", 13.5, 170.6, 20.5)
        control.call("key", "f1", "tap")
        control.call("wait", 3)
        if args.frame:
            args.frame.parent.mkdir(parents=True, exist_ok=True)
            control.call("screenshot", args.frame)
        reopened_text = (control.socket.parent / "ctl.log").read_text()

        # A LAN guest must receive the same update tags when entering the world.
        control.command("/tick unfreeze")
        port = control.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-tank-render-guest-") as guest_tmp, mp.joined_client(
            args, Path(guest_tmp), f"127.0.0.1:{port}", "TankRenderGuest", render=True,
            scenario="tank-render", pack=args.pack,
            env={"CREATE_TANK_RENDER": "1", "HORIZON_NO_AUDIO": "1"},
        ) as guest:
            mp.until("render guest joined", lambda: any(
                item["name"] == "TankRenderGuest" and item["placed"]
                for item in control.call("lan", "status")["guests"]))
            control.command("/tp TankRenderGuest 13.5 171.2 26.5")
            mp.until("render guest positioned", lambda:
                     guest.call("state")["player"]["position"] == [13.5, 171.2, 26.5])
            guest.call("look-at", 13.5, 170.6, 20.5)
            guest.call("key", "f1", "tap")
            guest.call("wait", 3)
            if args.frame:
                guest.call("screenshot", args.frame.with_name(args.frame.stem + "-guest" + args.frame.suffix))
            guest_text = (guest.socket.parent / "ctl.log").read_text()

    expected = {
        (8, 170, 20): (1, 1, "minecraft:water", 3000, 8000, 0.375),
        (12, 170, 20): (1, 1, "minecraft:lava", 8000, 8000, 1.0),
        (16, 170, 20): (2, 1, "minecraft:water", 16000, 32000, 0.5),
    }

    def rendered(text, label, levels=()):
        traces = [line[len(TRACE):].split() for line in text.splitlines()
                  if line.startswith(TRACE)]
        observed = {}
        observed_levels = {}
        for fields in traces:
            if len(fields) != 10:
                continue
            x, y, z, width, height = map(int, fields[:5])
            fluid, amount, capacity = fields[5:8]
            fill, drawn = float(fields[8]), fields[9] == "true"
            pos = (x, y, z)
            observed[pos] = (width, height, fluid, int(amount), int(capacity), fill, drawn)
            observed_levels.setdefault(pos, set()).add(int(amount))
        for pos, wanted in expected.items():
            got = observed.get(pos)
            if got is None or got[:5] != wanted[:5] or abs(got[5] - wanted[5]) > 1e-6 or not got[6]:
                raise SystemExit(f"{label}: expected client-rendered tank {wanted} with geometry at {pos}, got {got}")
        for pos, required in levels:
            if not required.issubset(observed_levels.get(pos, set())):
                raise SystemExit(f"{label}: client did not render level changes at {pos}: {observed_levels.get(pos)}")

    rendered(live_text, "host live view", (((8, 170, 20), {3000, 4000}),))
    rendered(reopened_text, "host after save/reopen")
    rendered(guest_text, "LAN guest view")
    print("Host live, cold-reopened host, and LAN guest rendered ordinary, creative, and 2x2 tank fluids; fill and drain levels replicated.")


if __name__ == "__main__":
    main()
