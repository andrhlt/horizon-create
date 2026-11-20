#!/usr/bin/env python3
"""Exercise a powered Fluid Valve in a conserved, pumped tank line."""

import argparse
from contextlib import ExitStack
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import fixture_world


def load(name, filename):
    spec = spec_from_file_location(name, Path(__file__).with_name(filename))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


multiplayer = load("multiplayer", "test-multiplayer.py")
motor = load("creative_motor", "test-creative-motor.py")
pipe = load("fluid_pipe_gameplay", "test-fluid-pipe-gameplay.py")

SOURCE = (10, 171, 20)
DESTINATION = (10, 175, 20)
VALVE = (10, 173, 20)
ROTOR = (10, 173, 19)
PUMP = (10, 172, 20)
GLASS = (10, 174, 20)
LINE = (SOURCE, PUMP, VALVE, GLASS, DESTINATION)
TOTAL = 7000
WATER = "minecraft:water"
ENV = {"HORIZON_NO_AUDIO": "1"}


def coords(pos):
    return " ".join(map(str, pos))


def setup(host):
    host.commands((
        "/fill 7 169 16 16 169 25 minecraft:smooth_stone",
        "/fill 7 170 16 16 178 25 minecraft:air",
        f"/setblock {coords(SOURCE)} create:fluid_tank",
        f"/setblock {coords(PUMP)} create:mechanical_pump[facing=up]",
        "/setblock 11 172 20 create:cogwheel[axis=y]",
        "/setblock 11 171 20 create:creative_motor[facing=up]{ScrollValue:128}",
        f"/setblock {coords(VALVE)} create:fluid_valve[facing=east,axis_along_first=false]",
        f"/setblock {coords(ROTOR)} create:creative_motor[facing=south]{{ScrollValue:64}}",
        "/setblock 10 174 20 create:glass_fluid_pipe[axis=y]",
        f"/setblock {coords(DESTINATION)} create:fluid_tank",
    ))
    pipe.fill(host, SOURCE, WATER, TOTAL)


def amount(host, pos):
    return pipe.storage(host, pos)


def balances(host):
    source, destination = amount(host, SOURCE), amount(host, DESTINATION)
    assert source[0] in (None, WATER) and destination[0] in (None, WATER), (source, destination)
    transit = sum(stored_fluid_amount(host, pos) for pos in LINE[1:-1])
    assert source[1] + destination[1] + transit == TOTAL, (source, destination, transit, TOTAL)
    return source[1], destination[1], transit


def compounds(text, name):
    result = []
    for match in re.finditer(rf"\b{name}:\s*\{{", text):
        start = match.end() - 1
        depth = 0
        quoted = escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
                continue
            if char == '"':
                quoted = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    result.append(text[start:index + 1])
                    break
    return result


def stored_fluid_amount(host, pos):
    data = host.command(f"/data get block {coords(pos)}")
    amount = 0
    for field in ("TankContent", "OpenEnd", "RefreshingEnd"):
        for value in compounds(data, field):
            for fluid in compounds(value, "Fluid"):
                match = re.search(r'\bid: "([^"]+)".*?\bamount: (\d+)', fluid)
                if match:
                    assert match[1] == WATER, (pos, match[1])
                    amount += int(match[2])
    return amount


def enabled(host):
    properties = host.call("block", *VALVE)["state"].split("[", 1)[1][:-1]
    return dict(entry.split("=", 1) for entry in properties.split(","))["enabled"] == "true"


def set_rotor(host, rpm):
    host.command(f"/data merge block {coords(ROTOR)} {{ScrollValue:{rpm}}}")
    advance_until(host, f"Fluid Valve rotor to reach {rpm} RPM", lambda:
                  motor.controller.tag(host.command(f"/data get block {coords(ROTOR)}"), "Speed", float) == rpm)


def wait_for_open(host, opened):
    advance_until(host, f"Fluid Valve enabled={str(opened).lower()}", lambda:
                  enabled(host) == opened)


def advance_until(host, description, predicate, max_ticks=120):
    for _ in range(max_ticks):
        if predicate():
            return
        host.step_to(host.clock() + 1)
    states = {pos: host.call("block", *pos)["state"] for pos in (PUMP, VALVE, ROTOR)}
    nbt = {pos: host.command(f"/data get block {coords(pos)}") for pos in (PUMP, VALVE, ROTOR)}
    raise RuntimeError(f"Timed out after {max_ticks} ticks waiting for {description}; states={states}; nbt={nbt}.")


def guest_reverses(host, args):
    port = host.call("lan", "open", "0", "commands", "force")["port"]
    with TemporaryDirectory(prefix="hc-fluid-valve-lan-") as scratch:
        with multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", "ValveFlowGuest",
            render=True, scenario="fluid-valve-flow", pack=args.pack, env=ENV,
        ) as guest:
            multiplayer.until("the Valve Flow guest to join", lambda: any(
                player["name"] == "ValveFlowGuest" and player["placed"]
                for player in host.call("lan", "status")["guests"]))
            host.command("/gamemode survival ValveFlowGuest")
            x, y, z = ROTOR
            guest_pos = [x - 1.5, 170, z + 0.5]
            host.command(f"/tp ValveFlowGuest {guest_pos[0]} {guest_pos[1]} {guest_pos[2]}")
            host.step_to(host.clock() + 1)
            multiplayer.until("the guest to reach the Valve rotor", lambda:
                              guest.call("state")["player"]["position"] == guest_pos)
            motor.configure(guest, ROTOR, 0, 64, teleport=False, facing="south")
            advance_until(host, "guest reversal to close the Fluid Valve", lambda: not enabled(host))
            closed = balances(host)
            pipe.advance(host, 15)
            assert balances(host) == closed, ("closed valve passed fluid", closed, balances(host))
            motor.configure(guest, ROTOR, 1, 64, teleport=False, facing="south")
            advance_until(host, "guest to reopen and transfer through the line", lambda:
                          enabled(host) and balances(host)[1] > closed[1])
            return balances(host)


def run(args):
    if args.recipe:
        check_recipe(args)
        return
    name = "FluidValveFlowLAN" if args.lan else "FluidValveFlow"
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, name, pack=args.pack, render=args.lan, env=ENV))
        setup(host)
        pipe.advance(host, 12)
        wait_for_open(host, True)
        advance_until(host, "open Fluid Valve to transfer water", lambda: balances(host)[1] > 0)
        opened = balances(host)
        assert 0 < opened[1] < TOTAL, opened

        set_rotor(host, -64)
        wait_for_open(host, False)
        closed = balances(host)
        pipe.advance(host, 15)
        stopped = balances(host)
        assert stopped[1] == closed[1], ("closed valve passed fluid", closed, stopped)

        set_rotor(host, 64)
        wait_for_open(host, True)
        advance_until(host, "reopened valve to resume transfer", lambda: balances(host)[1] > closed[1])
        if args.lan:
            guest_active = guest_reverses(host, args)
            assert balances(host) == guest_active

        # Persist a live line, then require both its setting and conserved fluid
        # to survive the real world restart and resume moving.
        before_save = balances(host)
        host.restart()
        host.call("wait", 4)
        pipe.advance(host, 2)
        assert motor.controller.tag(host.command(f"/data get block {coords(ROTOR)}"), "ScrollValue", int) == 64
        after_reopen = balances(host)
        assert after_reopen[0] + after_reopen[1] == TOTAL, (before_save, after_reopen)
        advance_until(host, "active flow to continue after reopen", lambda:
                      enabled(host) and balances(host)[1] > after_reopen[1])
        flowing_reopen = balances(host)

        # Save an idle, closed valve and confirm no delayed flow resumes.
        set_rotor(host, -64)
        wait_for_open(host, False)
        set_rotor(host, 0)
        idle = balances(host)
        host.restart()
        host.call("wait", 4)
        assert not enabled(host)
        assert balances(host)[1] == idle[1]
        pipe.advance(host, 20)
        assert balances(host)[1] == idle[1]
    print(f"Fluid Valve flow: closed rejection, powered open/reverse/reopen, conserved water, active/idle save-reopen passed ({opened} open, {closed} closed, {flowing_reopen} after active reopen)." +
          (" LAN guest reversed and reopened the line." if args.lan else ""))


def check_recipe(args):
    recipe_script = Path(__file__).with_name("test-machine-crafting.py")
    recipe_spec = spec_from_file_location("machine_crafting", recipe_script)
    machine_crafting = module_from_spec(recipe_spec)
    recipe_spec.loader.exec_module(machine_crafting)
    recipe = {
        "recipe": "crafting/kinetics/fluid_valve",
        "width": "3",
        "slots": "create:fluid_pipe,create:iron_sheet",
        "output": "create:fluid_valve",
        "count": "1",
        "remainder": "",
    }
    with fixture_world(args, "FluidValveSurvivalRecipe", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 8 169 22 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
            "/gamemode survival",
        ))
        machine_crafting.replay(host, recipe)
    print("Survival Fluid Valve recipe consumed one pipe and one iron sheet and produced one valve.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--recipe", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
