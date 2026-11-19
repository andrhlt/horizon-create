#!/usr/bin/env python3
"""Use original valve recoloring inputs from an independent survival guest."""
import argparse
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

spec = spec_from_file_location("multiplayer_fixture", ROOT / "tools/test-multiplayer.py")
multiplayer = module_from_spec(spec)
spec.loader.exec_module(multiplayer)
spec = spec_from_file_location("dyed_fixture", ROOT / "tools/test-dyed-valve-handle.py")
dyed = module_from_spec(spec)
spec.loader.exec_module(dyed)
valve = dyed.valve
PRIMARY = dyed.PRIMARY
GUEST = "DyeValveGuest"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-dl-") as tmp:
        verify(args, Path(tmp))
    print("A survival guest recolored the wet valve without consuming dye, then generated the same signed power as Java.")


def verify(args, scratch):
    with fixture_world(args, "DyedValveLAN", render=True, pack=args.pack) as host:
        valve.setup(host)
        host.commands((
            f"/setblock {valve.coord(PRIMARY)} create:copper_valve_handle[facing=east,waterlogged=true]",
            f"/data merge block {valve.coord(PRIMARY)} {{ScrollValue:-137}}",
            "/tp @s 12.5 101.0 -7.5",
        ))
        host.step_to(host.clock() + 1)
        address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
        with multiplayer.joined_client(
            args, scratch, address, GUEST, render=True, scenario="valve-dye-lan", pack=args.pack,
        ) as guest:
            multiplayer.until("the valve guest to enter", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/tp {GUEST} 11.500 101.000 -9.500",
                f"/item replace entity {GUEST} hotbar.0 with minecraft:red_dye 3",
            ))
            multiplayer.until("the guest to reach the valve with dye", lambda: (
                guest.call("state")["player"]["position"] == [11.5, 101.0, -9.5]
                and guest.call("inventory")["counts"].get("minecraft:red_dye") == 3
                and guest.call("block", *PRIMARY)["state"] == "create:copper_valve_handle[facing=east,waterlogged=true]"
            ))
            guest.call("select", "minecraft:red_dye")
            valve.point_at(guest, PRIMARY)
            dyed.tap(guest)
            wanted = "create:red_valve_handle[facing=east,waterlogged=true]"
            multiplayer.until("both players to see the red wet valve", lambda: all(
                peer.call("block", *PRIMARY)["state"] == wanted for peer in (host, guest)
            ))
            prior = dyed.data(host, [PRIMARY])[PRIMARY]
            if guest.call("inventory")["counts"].get("minecraft:red_dye") != 3 or (
                valve.tag(prior, "ScrollValue"), valve.tag(prior, "InUse")
            ) != (-137, 0):
                raise RuntimeError(f"Guest dye changed the count or active angle: {prior}.")

            valve.point_at(guest, PRIMARY)
            dyed.tap(guest)
            multiplayer.until("the same dye to use the already-red valve", lambda: (
                valve.tag(dyed.data(host, [PRIMARY])[PRIMARY], "InUse") == 17
            ))
            host.step_to(host.clock() + 1)
            rate = dyed.power_state(dyed.data(host, [PRIMARY, dyed.shaft(PRIMARY)]), PRIMARY)
            if rate != (16, -32.0, -32.0, 256.0, 0.0):
                raise RuntimeError(f"Unexpected mapped red valve power after guest tap: {rate}.")


if __name__ == "__main__":
    main()
