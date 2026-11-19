"""Compare original Sword PvP impact with real Horizon host and guest attacks."""
import argparse
import csv
import json
from importlib import import_module
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world
sword = import_module("test-cardboard-sword")

def status(control):
    player = control.call("status")["player"]
    return {name: player[name] for name in ("health", "position", "velocity", "on_ground")}

watch = sword.placement.editor.wait_for

CASES = ("plain", "base_knockback", "pvp_disabled", "knockback_sprint",
         "mounted", "creative_victim", "wood")
ORIGIN = (8.5, 101.0, 3.5)
TOLERANCE = 2e-7


def impacts(host):
    prefix = "CREATE_SWORD_PVP "
    with (host.socket.parent / "ctl.log").open() as log:
        return [line.strip().split(prefix, 1)[1].split(",") for line in log if prefix in line]


def run(host, guest, name, args, case, rows):
    row = rows[case]
    attacker, victim = (host, guest) if args.host_attacks else (guest, host)
    attacker_name, victim_name = ("@s", name) if args.host_attacks else (name, "@s")
    pvp = row["pvp"] == "true"
    sprint = case == "knockback_sprint"
    cardboard = case != "wood"
    weapon = sword.SWORD if cardboard else "minecraft:wooden_sword"
    modifiers = '[minecraft:enchantments={"minecraft:knockback":2}]' if sprint else ""
    for command in (
        f"/gamemode survival {attacker_name}",
        f"/gamemode {'creative' if case == 'creative_victim' else 'survival'} {victim_name}",
        f"/gamerule pvp {str(pvp).lower()}",
        f"/item replace entity {attacker_name} weapon.mainhand with {weapon}{modifiers}",
        f"/clear {victim_name}",
    ):
        host.call("command", command)
    if case == "base_knockback":
        reply = host.command(f"/attribute {attacker_name} minecraft:attack_knockback base set 2")
        assert "2" in reply, reply
    x, y, z = ORIGIN
    sword.placement.teleport(host, attacker, attacker_name, (x, y, z - (2.9 if sprint else 2)))
    sword.placement.teleport(host, victim, victim_name, ORIGIN)
    if case == "mounted":
        host.command(f"/summon minecraft:oak_boat {x} {y} {z} {{Tags:[sword_pvp_boat]}}")
        reply = host.command(f"/ride {victim_name} mount @e[tag=sword_pvp_boat,limit=1]")
        watch(victim, "the victim seated in the boat", lambda:
                       victim.call("status")["riding"] is not None)
        assert "riding" in reply.lower(), reply
    watch(attacker, "the original weapon in the player’s hand", lambda:
                   (attacker.call("inventory")["held"] or {}).get("item") == weapon)
    watch(victim, "the victim's expected standing state", lambda:
                   case == "mounted" or status(victim)["on_ground"])
    health_before = status(victim)["health"]
    assert health_before == float(row["health_before"]), health_before
    position = status(victim)["position"]
    attacker.call("look-at", position[0], position[1] + 1.0, position[2])
    def aimed():
        pick = attacker.call("looking-at")
        return pick.get("kind") == "entity" and pick.get("entity", {}).get("type") == "minecraft:player"
    watch(attacker, "the other real player under the crosshair", aimed)
    attacker.call("wait", 14)
    if case == "mounted":
        position = status(victim)["position"]
        attacker.call("look-at", position[0], position[1] + 1.0, position[2])
        watch(attacker, "the seated player under the crosshair", aimed)
    offsets = {
        peer: (sword.bonks_heard(peer), len(sword.playback_trace(peer)))
        for peer in (attacker, victim)
    }
    old_impacts = len(impacts(host))
    if sprint:
        attacker.call("key", "ctrl", "down")
        attacker.call("key", "w", "down")
        watch(attacker, "the attacker to sprint", lambda:
                       attacker.call("state")["player"]["sprinting"])
        attacker.call("key", "ctrl", "up")
    try:
        attacker.call("mouse", "left", "click")
        if sprint:
            watch(attacker, "the sword to stop attacker sprinting", lambda:
                           not attacker.call("state")["player"]["sprinting"])
    finally:
        if sprint:
            attacker.call("key", "ctrl", "up")
            attacker.call("key", "w", "up")
    health_after = float(row["health_after"])
    if not cardboard:
        watch(victim, "normal wooden sword damage", lambda:
                       status(victim)["health"] == health_after)
        assert len(impacts(host)) == old_impacts, impacts(host)
        assert all(sword.bonks_heard(peer) == heard
                   for peer, (heard, _) in offsets.items()), offsets
        print(f"{case}: ordinary sword dealt {health_before - health_after} damage.", flush=True)
        return

    watch(host, "the authority's original knockback impact",
                   lambda: len(impacts(host)[old_impacts:]) == 1)
    impact = impacts(host)[old_impacts]
    _, _, health, vx, vy, vz, riding, grounded = impact
    if case == "mounted" and grounded == "true":
        row = rows["mounted_grounded"]
    expected = tuple(float(row[key]) for key in ("health_after", "vx", "vy", "vz"))
    actual = tuple(map(float, (health, vx, vy, vz)))
    assert riding == row["riding"], (case, row, impact)
    assert all(math.isclose(a, e, abs_tol=TOLERANCE)
               for a, e in zip(actual, expected, strict=True)), (case, expected, actual)
    # The client still integrates its motion after the server-side impact.
    # Observe it physically leaving its prior Z position through the wire.
    watch(victim, "the actual recipient client to move after the bonk", lambda:
                   status(victim)["position"][2] > position[2] + 0.1)
    assert status(victim)["health"] == health_after
    assert "minecraft:slowness" not in (sword.entity_data(host, victim_name, "active_effects") or "")
    if case == "mounted":
        watch(victim, "the actual victim client to leave its boat", lambda:
                       victim.call("status")["riding"] is None)
    for peer, (heard, trace_offset) in offsets.items():
        watch(peer, "the original bonk event at the listener", lambda:
                      sword.bonks_heard(peer) == heard + 1)
        sword.check_bonk_playback(peer, trace_offset, 0.75, 1.85,
                                          "Host" if peer is host else "Guest")
    print(json.dumps({"case": case, "java_case": row["case"], "java_impact": expected, "horizon_impact": actual,
                      "mounted_after_impact": riding == "true", "grounded_at_impact": grounded == "true",
                      "client_victim": status(victim)}), flush=True)


def main():
    os.environ["HORIZON_CREATE_SWORD_PVP_TRACE"] = "1"
    os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--host-attacks", action="store_true")
    parser.add_argument("--case", action="append", choices=CASES)
    args = parser.parse_args()
    with (ROOT / "fixtures/cardboard-sword-pvp-java.csv").open(newline="") as source:
        rows = {row["case"]: row for row in csv.DictReader(source)}
    for case in args.case or CASES:
        direction = "Host" if args.host_attacks else "Guest"
        scenario = f"CardboardSwordPvp{direction}{case}"
        with TemporaryDirectory(prefix="hc-sword-pvp-") as scratch:
            with fixture_world(args, scenario, render=True, pack=args.pack) as host:
                host.commands((
                    "/fill 0 100 -4 20 100 19 minecraft:smooth_stone",
                    "/fill 0 101 -4 20 106 19 minecraft:air",
                ))
                with sword.package.filters.actor_for(host, args, Path(scratch)) as (guest, name):
                    run(host, guest, name, args, case, rows)


if __name__ == "__main__":
    main()
