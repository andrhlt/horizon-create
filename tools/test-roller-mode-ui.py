#!/usr/bin/env python3
"""Craft and place a Mechanical Roller, then verify its host and LAN modes."""
import argparse
from pathlib import Path
from runpy import run_path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

POS = (8, 201, 42)
LABELS = ["Tunnel Pave", "Straight Fill", "Wide Fill"]


def mode(control):
    result = control.command(f"/data get block {' '.join(map(str, POS))} ScrollValue")
    tail = result.rsplit(" ", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def value_box(control):
    facing = control.call("block", *POS)["state"].split("facing=", 1)[1].split(",", 1)[0].split("]", 1)[0]
    offset = {
        "north": (5 / 16, 11 / 16),
        "south": (11 / 16, 5 / 16),
        "west": (15.5 / 16, 5 / 16),
        "east": (0.5 / 16, 11 / 16),
    }[facing]
    return (POS[0] + offset[0], POS[1] + 15.5 / 16, POS[2] + offset[1])

def filter_box(control):
    facing = control.call("block", *POS)["state"].split("facing=", 1)[1].split(",", 1)[0].split("]", 1)[0]
    offset = {
        "north": (11 / 16, 11 / 16),
        "south": (5 / 16, 5 / 16),
        "west": (15.5 / 16, 11 / 16),
        "east": (0.5 / 16, 5 / 16),
    }[facing]
    return (POS[0] + offset[0], POS[1] + 15.5 / 16, POS[2] + offset[1])


def choose(control, value):
    control.call("look-at", *value_box(control))
    control.call("wait", 2)
    control.call("mouse", "right", "down")
    control.call("wait", 7)
    screen = control.call("screen")
    if control.call("state")["screen"] != "mod":
        raise RuntimeError(f"Mechanical Roller mode board did not open: {screen}")
    buttons = screen["buttons"]
    labels = [button["label"] for button in buttons]
    if labels != LABELS:
        raise RuntimeError(f"Expected Roller modes {LABELS}, got {labels}")
    button = buttons[value]
    control.call("click-at", button["x"] + button["w"] / 2,
                 button["y"] + button["h"] / 2, "right")
    control.call("wait", 3)
    if control.call("state")["screen"] != "playing":
        raise RuntimeError("Confirming a Roller mode did not close the board")


def craft_and_place(control):
    control.commands((
        "/item replace entity @s hotbar.0 with create:electron_tube",
        "/item replace entity @s hotbar.1 with create:andesite_casing",
        "/item replace entity @s hotbar.2 with create:crushing_wheel",
    ))
    control.call("interact", 6, 200, 42, "up")
    for source, target in ((0, 100), (1, 103), (2, 106)):
        control.call("click-slot", source)
        control.call("click-slot", target, "right")
    menu = control.call("menu")
    result = next((slot["stack"] for slot in menu["slots"] if slot["slot"] == 200), None)
    if not result or result.get("item") != "create:mechanical_roller":
        raise RuntimeError(f"Survival recipe did not produce a Mechanical Roller: {result}")
    control.call("click-slot", 200, "shift")
    if control.call("inventory")["counts"].get("create:mechanical_roller") != 1:
        raise RuntimeError("Crafting did not place one Mechanical Roller in the survival inventory")
    control.call("close")
    control.call("select", "create:mechanical_roller")
    control.call("look-at", 8.5, 201, 42.5)
    control.call("wait", 2)
    control.call("mouse", "right", "down")
    control.call("wait", 2)
    control.call("mouse", "right", "up")
    place_result = control.call("wait", 2)
    state = control.call("block", *POS)["state"]
    if not state.startswith("create:mechanical_roller"):
        around = [control.call("block", 8, y, 42)["state"] for y in (199, 200, 201, 202)]
        raise RuntimeError(f"Survival placement on a full floor failed: result={place_result}, blocks={around}")
    if control.call("inventory")["counts"].get("create:mechanical_roller", 0):
        raise RuntimeError("Roller placement did not consume its crafted item")
    # Normalize the heading so the rendered control target is deterministic.
    control.command(f"/setblock {' '.join(map(str, POS))} create:mechanical_roller[facing=north]")

def reject_invalid_filter(control):
    control.command("/item replace entity @s hotbar.0 with minecraft:chest")
    control.call("select", 1)
    before = control.call("inventory")
    control.call("look-at", *filter_box(control))
    control.call("wait", 2)
    target = control.call("looking-at")
    hit = target.get("block", target)
    if before["hotbar"][0].get("item") != "minecraft:chest" or before["hotbar"][0].get("count") != 1:
        raise RuntimeError(f"Invalid-filter setup did not hold one chest: {before}")
    if hit.get("pos") != list(POS) or hit.get("block") != "create:mechanical_roller":
        raise RuntimeError(f"Invalid-filter click is not aimed at Roller {POS}: {target}")
    control.call("mouse", "right", "down")
    control.call("wait", 2)
    control.call("mouse", "right", "up")
    control.call("wait", 2)
    after = control.call("inventory")
    filt = control.command(f"/data get block {' '.join(map(str, POS))} Filter")
    blocks = control.call("blocks", POS[0] - 1, POS[1] - 1, POS[2] - 1, POS[0] + 1, POS[1] + 2, POS[2] + 1)["blocks"]
    placed = [block for block in blocks if block[3].split("[", 1)[0] == "minecraft:chest"]
    if after["hotbar"][0].get("item") != "minecraft:chest" or after["hotbar"][0].get("count") != 1:
        raise RuntimeError(f"Invalid Roller filter consumed chest: target={target}; before={before}; after={after}; Filter={filt}; placed={placed}")
    if placed or "minecraft:chest" in filt:
        raise RuntimeError(f"Invalid Roller filter changed world/filter: Filter={filt}, blocks={placed}")

    control.command("/item replace entity @s hotbar.0 with minecraft:stone")
    control.call("select", 1)
    control.call("look-at", *filter_box(control))
    control.call("wait", 2)
    supported_target = control.call("looking-at")
    control.call("mouse", "right", "down")
    control.call("wait", 2)
    control.call("mouse", "right", "up")
    control.call("wait", 2)
    supported_after = control.call("inventory")
    supported_filter = control.command(f"/data get block {' '.join(map(str, POS))} Filter")
    if supported_target.get("block", supported_target).get("pos") != list(POS):
        raise RuntimeError(f"Supported filter target missed Roller: {supported_target}")
    if supported_after["hotbar"][0].get("item") != "minecraft:stone" or supported_after["hotbar"][0].get("count") != 1:
        raise RuntimeError(f"Supported plain-block filter consumed stone: {supported_after}; Filter={supported_filter}")
    if "minecraft:stone" not in supported_filter:
        raise RuntimeError(f"Supported plain-block filter was not stored: {supported_filter}")


def check_guest_filter(host, guest, until):
    expected_filter = host.command(f"/data get block {' '.join(map(str, POS))} Filter")
    for item in ("minecraft:chest", "minecraft:stone"):
        host.command(f"/item replace entity RollerGuest hotbar.0 with {item}")
        until(f"guest to receive one {item}", lambda:
              (guest.call("inventory")["hotbar"][0].get("item") == item
               and guest.call("inventory")["hotbar"][0].get("count") == 1))
        guest.call("select", 1)
        guest.call("look-at", *filter_box(guest))
        guest.call("wait", 2)
        target = guest.call("looking-at")
        if target.get("block", target).get("pos") != list(POS):
            raise RuntimeError(f"LAN {item} filter click missed the Roller: {target}")
        guest.call("mouse", "right", "down")
        guest.call("wait", 2)
        guest.call("mouse", "right", "up")

        def authoritative_inventory():
            return host.command(
                "/data get entity RollerGuest Inventory[{Slot:0b}]"
            )

        inventory = None
        for _ in range(40):
            guest.call("wait", 1)
            inventory = authoritative_inventory()
            if item in inventory:
                break
        guest_inventory = guest.call("inventory")
        filt = host.command(f"/data get block {' '.join(map(str, POS))} Filter")
        if item not in inventory or "count: 1" not in inventory:
            raise RuntimeError(
                f"LAN Roller filter changed authoritative {item} count: "
                f"server={inventory}; guest={guest_inventory}; Filter={filt}"
            )
        if guest_inventory["hotbar"][0].get("item") != item or guest_inventory["hotbar"][0].get("count") != 1:
            raise RuntimeError(
                f"LAN Roller filter changed guest {item} count: "
                f"guest={guest_inventory}; server={inventory}; Filter={filt}"
            )
        if item == "minecraft:chest":
            blocks = host.call("blocks", POS[0] - 1, POS[1] - 1, POS[2] - 1,
                               POS[0] + 1, POS[1] + 2, POS[2] + 1)["blocks"]
            placed = [block for block in blocks if block[3].split("[", 1)[0] == item]
            if placed or item in filt or filt != expected_filter:
                raise RuntimeError(
                    f"LAN unsupported filter changed world/filter: "
                    f"before={expected_filter}; after={filt}; blocks={placed}"
                )
        elif item not in filt:
            raise RuntimeError(f"LAN supported stone filter was not stored: {filt}")
        print(f"LAN {item}: guest count 1, server count 1, Roller Filter={filt}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    multiplayer = run_path(str(ROOT / "tools/test-multiplayer.py"))
    until = multiplayer["until"]

    with fixture_world(args, "RollerModeUI", render=True,
                       env={"HORIZON_NO_AUDIO": "1"}) as host:
        host.commands((
            "/fill 6 200 40 11 200 47 minecraft:smooth_stone",
            "/setblock 6 200 42 minecraft:crafting_table",
            "/tp @s 8.3125 201 45.5 180 24",
            "/gamemode survival",
        ))
        host.step_to(host.clock() + 1)
        craft_and_place(host)
        reject_invalid_filter(host)
        for selected in (1, 2, 0):
            choose(host, selected)
            if mode(host) != selected:
                raise RuntimeError(f"Host selected mode {selected}, server stored {mode(host)}")

        host.command("/tp @s 6.5 201 45.5")
        network = host.call("lan", "open", "0", "commands", "force")
        with TemporaryDirectory(prefix="roller-mode-ui-") as temp, multiplayer["joined_client"](
            args, Path(temp), f"127.0.0.1:{network['port']}", "RollerGuest",
            render=True, scenario="roller-mode-ui",
        ) as guest:
            until("guest to join", lambda: any(
                player["name"] == "RollerGuest" and player["placed"]
                for player in host.call("lan", "status")["guests"]))
            host.commands((
                "/gamemode survival RollerGuest",
                "/tp RollerGuest 8.3125 201 45.5",
            ))
            host.step_to(host.clock() + 1)
            until("guest to see Roller", lambda:
                  guest.call("block", *POS)["block"] == "create:mechanical_roller")
            choose(guest, 2)
            until("guest mode to reach server", lambda: mode(host) == 2)
            check_guest_filter(host, guest, until)

        host.command("/save-all flush")
        host.restart()
        if mode(host) != 2:
            raise RuntimeError(f"Roller mode did not persist across reopen: {mode(host)}")
        reopened_filter = host.command(f"/data get block {' '.join(map(str, POS))} Filter")
        reopened_inventory = host.call("inventory")
        if "minecraft:stone" not in reopened_filter:
            raise RuntimeError(f"Roller filter did not persist across reopen: {reopened_filter}")
        if reopened_inventory["hotbar"][0].get("item") != "minecraft:stone" or reopened_inventory["hotbar"][0].get("count") != 1:
            raise RuntimeError(f"Plain-block filter inventory changed across reopen: {reopened_inventory}")

    print("Host selected all three Roller modes; LAN guest selected Wide Fill; mode persisted across reopen.")


if __name__ == "__main__":
    main()
