#!/usr/bin/env python3
"""Check a LAN guest can extend and resize a Steam Whistle with host convergence."""
import argparse
from contextlib import ExitStack
from pathlib import Path
import tempfile

from fixture_world import ROOT
import importlib.util
import math

_spec = importlib.util.spec_from_file_location("multiplayer", ROOT / "tools/test-multiplayer.py")
mp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mp)

WHISTLE = (9, 171, 20)
EXTENSION = (9, 172, 20)
HOST_POS = (12.5, 170.0, 23.5)
GUEST_POS = (9.5, 170.0, 23.5)
TRACE_ENV = {"HORIZON_NO_AUDIO": "1", "HORIZON_CREATE_WHISTLE_TRACE": "1"}


def state(client, pos):
    return client.call("block", *pos)["state"]


def sound_rows(client):
    log = client.socket.parent / "ctl.log"
    if not log.exists():
        return []
    rows = []
    for line in log.read_text(errors="replace").splitlines():
        if "CREATE_WHISTLE_REQUEST " not in line:
            continue
        fields = line.split("CREATE_WHISTLE_REQUEST ", 1)[1].split(",")
        if len(fields) == 8:
            rows.append((fields[0], int(fields[1]), float(fields[5]), float(fields[6]), fields[7] == "true"))
    return rows


def has_sound(client, predicate):
    return any(predicate(row) for row in sound_rows(client))


def last_sound(client, event):
    return next((row for row in reversed(sound_rows(client)) if row[0] == event), None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="hc-app1994-whistle-lan-") as tmp:
        scratch = Path(tmp)
        with ExitStack() as stack:
            address, server = stack.enter_context(mp.dedicated(
                args, scratch, scenario="app1994-whistle-lan", pack=args.pack,
                artifact_dir=ROOT / ".local/app-1994"))
            host = stack.enter_context(mp.joined_client(
                args, scratch, address, "WhistleHost", render=True, env=TRACE_ENV,
                scenario="app1994-whistle-lan", pack=args.pack,
                artifact_dir=ROOT / ".local/app-1994"))
            guest = stack.enter_context(mp.joined_client(
                args, scratch, address, "WhistleGuest", render=True, env=TRACE_ENV,
                scenario="app1994-whistle-lan", pack=args.pack,
                artifact_dir=ROOT / ".local/app-1994"))

            server("fill 4 169 16 15 169 27 minecraft:stone")
            server("fill 4 170 16 15 177 27 minecraft:air")
            server("setblock 9 170 20 create:fluid_tank")
            server("setblock 9 169 20 minecraft:magma_block")
            server("setblock 9 171 20 create:steam_whistle[facing=north,powered=false,size=medium,wall=false]")
            server("setblock 10 171 20 minecraft:redstone_block")
            server("gamemode survival WhistleHost")
            server("gamemode survival WhistleGuest")
            server("item replace entity WhistleGuest hotbar.0 with create:steam_whistle")
            server("item replace entity WhistleGuest hotbar.1 with create:wrench")
            server("tp WhistleHost 12.5 170 23.5")
            server("tp WhistleGuest 9.5 170 23.5")
            mp.until("both clients to see the whistle", lambda:
                     "create:steam_whistle[" in state(host, WHISTLE)
                     and "create:steam_whistle[" in state(guest, WHISTLE))
            mp.until("both players to reach the fixture", lambda:
                     host.call("state")["player"]["position"] == list(HOST_POS)
                     and guest.call("state")["player"]["position"] == list(GUEST_POS))
            mp.until("boiler-driven whistle cue on both clients", lambda:
                     has_sound(host, lambda row: row[0] == "create:whistle" and row[4])
                     and has_sound(guest, lambda row: row[0] == "create:whistle" and row[4]))

            guest.call("select", "create:steam_whistle")
            guest.call("look-at", 9.5, 171.5, 20.5)
            mp.until("guest targets the whistle", lambda:
                     (guest.call("looking-at").get("block") or {}).get("pos") == list(WHISTLE))
            guest.call("mouse", "right", "click")
            mp.until("guest grows the whistle", lambda: "shape=single" in state(host, EXTENSION)
                     and "shape=single" in state(guest, EXTENSION))
            tuned_pitch = 2 ** (-1 / 12)
            mp.until("pitch update reaches both whistle cues", lambda:
                     has_sound(host, lambda row: row[0] == "create:whistle" and not row[4]
                               and math.isclose(row[3], tuned_pitch, rel_tol=1e-5))
                     and has_sound(guest, lambda row: row[0] == "create:whistle" and not row[4]
                                  and math.isclose(row[3], tuned_pitch, rel_tol=1e-5)))

            guest.call("select", "create:wrench")
            guest.call("mouse", "right", "click")
            mp.until("guest changes the octave", lambda:
                     "size=large" in state(host, WHISTLE)
                     and "size=large" in state(guest, WHISTLE)
                     and "size=large" in state(host, EXTENSION)
                     and "size=large" in state(guest, EXTENSION))
            mp.until("large-octave cue on both clients", lambda:
                     has_sound(host, lambda row: row[0] == "create:whistle_low" and row[4])
                     and has_sound(guest, lambda row: row[0] == "create:whistle_low" and row[4]))

            server("setblock 10 171 20 minecraft:air")
            mp.until("redstone-off state on both clients", lambda:
                     "powered=false" in state(host, WHISTLE)
                     and "powered=false" in state(guest, WHISTLE))
            mp.until("both whistle cues fade completely", lambda:
                     has_sound(host, lambda row: row[0] == "create:whistle_low" and not row[4] and row[2] == 0)
                     and has_sound(guest, lambda row: row[0] == "create:whistle_low" and not row[4] and row[2] == 0))

            server("setblock 10 171 20 minecraft:redstone_block")
            mp.until("redstone retrigger reaches both clients", lambda:
                     "powered=true" in state(host, WHISTLE)
                     and "powered=true" in state(guest, WHISTLE)
                     and has_sound(host, lambda row: row[0] == "create:whistle_low" and row[4])
                     and has_sound(guest, lambda row: row[0] == "create:whistle_low" and row[4]))

            server("setblock 9 169 20 minecraft:air")
            mp.until("boiler heat loss fades both whistle cues", lambda:
                     last_sound(host, "create:whistle_low") is not None
                     and last_sound(host, "create:whistle_low")[2] == 0
                     and last_sound(guest, "create:whistle_low") is not None
                     and last_sound(guest, "create:whistle_low")[2] == 0)

            starts_before_heat_restore = [
                sum(row[0] == "create:whistle_low" and row[4] for row in sound_rows(client))
                for client in (host, guest)
            ]
            server("setblock 9 169 20 minecraft:magma_block")
            mp.until("boiler heat restoration restarts both whistle cues", lambda:
                     all(sum(row[0] == "create:whistle_low" and row[4] for row in sound_rows(client)) > before
                         for client, before in zip((host, guest), starts_before_heat_restore)))
    print("Guest extension and octave actions converged on both clients; boiler onset, tuned pitch, redstone fade/retrigger, heat-loss fade and heat-restoration cues passed.")


if __name__ == "__main__":
    main()
