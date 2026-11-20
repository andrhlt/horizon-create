#!/usr/bin/env python3
"""Exercise the finite Mechanical Pump survival, LAN and restart baseline."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

fluid = import_module("test-fluid-pipe-gameplay")
pipes = fluid.pipes
pressure = import_module("test-pump-startup-pressure")
PUMP = "create:mechanical_pump"
POS = (12, 170, 20)


def observe(host, actor, pos, block_id, **properties):
    try:
        fluid.observe(host, actor, pos, block_id, **properties)
    except RuntimeError as error:
        raise RuntimeError(f"Expected {block_id} {properties}; host={host.call('block', *pos)}, "
                           f"actor={actor.call('block', *pos)}") from error


def interactions(args):
    name = "MechanicalPumpGameplayLAN" if args.lan else "MechanicalPumpGameplay"
    with ExitStack() as stack:
        host = stack.enter_context(fluid.fixture_world(
            args, name, render=not args.lan, pack=args.pack, env=fluid.ENV))
        actor, player = pipes.test_actor(stack, args, host, name)
        host.commands((
            "/fill 8 169 16 24 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            f"/gamemode survival {player}",
        ))
        if not args.lan:
            fluid.move(host, actor, player, 12.5, 170, 26.5)
            with (ROOT / "fixtures/machine-crafting-java.csv").open(newline="") as stream:
                recipe = next(row for row in csv.DictReader(stream) if row["output"] == PUMP)
            fluid.crafting.replay(host, recipe)

        # PumpBlock inherits look-based facing; sneaking reverses the view rule.
        # An adjacent fluid endpoint on another axis overrides ordinary placement.
        with (ROOT / "fixtures/mechanical-pump-placement-java.csv").open(newline="") as stream:
            reference = list(csv.DictReader(stream))
        cases = (("view", False, False), ("sneaking", True, False), ("tank connection", False, True))
        for index, ((case, sneak, neighbor), expected) in enumerate(zip(cases, reference, strict=True)):
            assert expected["case"] == str(index), expected
            facing = expected["facing"]
            host.commands((
                f"/clear {player} {PUMP}",
                f"/setblock {pipes.coords(POS)} minecraft:air",
                "/setblock 11 170 20 " + ("create:fluid_tank" if neighbor else "minecraft:air"),
                f"/item replace entity {player} hotbar.0 with {PUMP}",
                f"/item replace entity {player} hotbar.1 with {fluid.WRENCH}",
            ))
            fluid.move(host, actor, player, 12.5, 170, 22.5)
            actor.call("look", 180, 0)
            fluid.multiplayer.until("the Pump stack to reach the actor",
                                    lambda: pipes.inventory(actor, PUMP) == 1)
            actor.call("select", PUMP)
            if sneak:
                actor.call("key", "shift", "down")
            try:
                actor.call("wait", 4)
                actor.call("interact", 12, 169, 20, "up")
            finally:
                if sneak:
                    actor.call("key", "shift", "up")
            observe(host, actor, POS, PUMP, facing=facing, waterlogged="false")
            fluid.multiplayer.until(f"{case} placement to consume exactly one Pump",
                                    lambda: pipes.inventory(actor, PUMP) == 0)
            opposite = expected["wrenched"]
            pipes.use(actor, POS, fluid.WRENCH)
            observe(host, actor, POS, PUMP, facing=opposite)
            pipes.use(actor, POS, fluid.WRENCH)
            observe(host, actor, POS, PUMP, facing=facing)
            pipes.use(actor, POS, fluid.WRENCH, sneak=True)
            observe(host, actor, POS, "minecraft:air")
            fluid.multiplayer.until("the Wrench to return exactly one Pump",
                                    lambda: pipes.inventory(actor, PUMP) == 1)

        if not args.lan:
            host.command(f"/setblock {pipes.coords(POS)} {PUMP}[facing=west,waterlogged=true]")
            host.restart()
            observe(host, host, POS, PUMP, facing="west", waterlogged="true")
    print(f"{name}: recipe (solo), three placements, facing flips and exact Wrench return passed; "
          + ("host and guest converged." if args.lan else "idle wet Pump reopened."))


def lifecycle(args):
    rows = []
    with fixture_world(args, "MechanicalPumpLifecycle", pack=args.pack, env=fluid.ENV) as host:
        # Reuse the APP-1972 rig, with an unrestricted glass line above the pump.
        fluid.rig(host, 10, fluid.WATER, 7000, fluid.WATER_BUCKET)
        host.command("/setblock 10 173 20 create:glass_fluid_pipe[axis=y]")
        pump, motor = (10, 172, 20), (11, 171, 20)

        def sample(stage, expected_rpm, *, facing="up"):
            data = host.command(f"/data get block {pipes.coords(pump)}")
            rpm = pipes.branched.reading(data, "Speed")
            assert rpm == expected_rpm, (stage, rpm, expected_rpm)
            magnitude = abs(expected_rpm)
            inlet = f"{magnitude:.4f}:0.0000"
            outlet = f"0.0000:{magnitude:.4f}"
            ports = tuple(pressure.port(data, side) for side in ("down", "up"))
            wanted = (inlet, outlet) if facing == "up" else (outlet, inlet)
            assert ports == wanted, (stage, ports, wanted)
            amounts = fluid.balances(host, 10, fluid.WATER, 7000)
            rows.append((stage, rpm, facing, *ports, *amounts))
            return amounts

        def drive(speed):
            host.command(f"/setblock {pipes.coords(motor)} create:creative_motor[facing=up]{{ScrollValue:{speed}}}")

        fluid.advance(host, 24)
        before = sample("forward", -128)
        assert 0 < before[1] < 7000, before
        drive(-128)
        fluid.advance(host, 12)
        reverse_rpm = sample("negative motor", 128)
        # PumpBlockEntity.isPullingOnSide depends on facing, never RPM sign.
        assert reverse_rpm[1] > before[1], (before, reverse_rpm)

        host.command(f"/setblock {pipes.coords(motor)} minecraft:air")
        fluid.advance(host, 4)
        stopped = sample("stopped", 0)
        fluid.advance(host, 16)
        assert sample("still stopped", 0) == stopped
        host.restart()
        assert sample("idle reopen", 0) == stopped

        drive(128)
        fluid.advance(host, 20)
        started = sample("restarted", -128)
        assert started[1] > stopped[1], (stopped, started)
        host.restart()
        reopened = sample("active reopen", -128)
        assert reopened[1] >= started[1], (started, reopened)
        fluid.advance(host, 12)
        assert sample("active resumed", -128)[1] > reopened[1]

        # Facing reversal changes the pumping direction with the same drive.
        host.command(f"/setblock {pipes.coords(pump)} {PUMP}[facing=down]")
        fluid.advance(host, 16)
        reversed_flow = sample("facing reversed", -128, facing="down")
        fluid.advance(host, 12)
        assert sample("reverse transfer", -128, facing="down")[0] > reversed_flow[0]

    output = ROOT / ".local/mechanical-pump-lifecycle-horizon.csv"
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("stage", "rpm", "facing", "down_pressure", "up_pressure", "bottom_mb", "top_mb"))
        writer.writerows(rows)
    print(f"Pump RPM sign, facing reversal, power stop/start and idle/active reopen passed. See {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda value: Path(value).resolve(strict=True))
    scenario = parser.add_mutually_exclusive_group()
    scenario.add_argument("--lan", action="store_true")
    scenario.add_argument("--lifecycle", action="store_true")
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    (lifecycle if args.lifecycle else interactions)(args)


if __name__ == "__main__":
    main()
