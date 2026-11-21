#!/usr/bin/env python3
"""Save and reopen an idle dyed valve and an active copper handle stroke."""
import argparse
from pathlib import Path

from fixture_world import fixture_world
from importlib.util import module_from_spec, spec_from_file_location

spec = spec_from_file_location("valve_fixture", Path(__file__).with_name("test-copper-valve-handle.py"))
valve = module_from_spec(spec)
spec.loader.exec_module(valve)

HANDLE = valve.HANDLE
SHAFT = valve.SHAFT
def data(control, pos):
    return control.command(f"/data get block {valve.coord(pos)}")


def verify(args):
    with fixture_world(args, "ValveHandlePersistence", render=True, pack=args.pack) as control:
        valve.setup(control)
        control.command(f"/setblock {valve.coord(HANDLE)} create:red_valve_handle[facing=east,waterlogged=true]")
        control.command(f"/data merge block {valve.coord(HANDLE)} {{ScrollValue:-137}}")
        control.call("save")
        control.restart()

        state = control.call("block", *HANDLE)["state"]
        handle = data(control, HANDLE)
        if state != "create:red_valve_handle[facing=east,waterlogged=true]" or (
            valve.tag(handle, "ScrollValue"), valve.tag(handle, "InUse"),
            control.call("block", *SHAFT)["block"],
        ) != (-137, 0, "create:shaft"):
            raise RuntimeError(f"Idle dyed valve lost state across reopen: {state}; {handle}")

        control.command(f"/setblock {valve.coord(HANDLE)} create:copper_valve_handle[facing=east,waterlogged=false]")
        control.command(f"/data merge block {valve.coord(HANDLE)} {{ScrollValue:-137}}")
        valve.point_at(control, HANDLE)
        valve.activate(control)
        before = data(control, HANDLE)
        active = (valve.tag(before, "ScrollValue"), valve.tag(before, "InUse"),
                  valve.tag(before, "TotalUseTicks"), valve.tag(before, "TargetAngle"),
                  valve.tag(before, "Backwards"))
        if active != (-137, 17, 17, -180, 0):
            raise RuntimeError(f"Unexpected active stroke before save: {active}; {before}")
        control.call("save")
        control.restart()

        after = data(control, HANDLE)
        resumed = (valve.tag(after, "ScrollValue"), valve.tag(after, "InUse"),
                   valve.tag(after, "TotalUseTicks"), valve.tag(after, "TargetAngle"),
                   valve.tag(after, "Backwards"))
        if resumed[0] != active[0] or resumed[2:] != active[2:] or not 0 <= resumed[1] <= active[1]:
            raise RuntimeError(f"Active valve stroke changed across reopen: {active} -> {resumed}")
        if resumed[1] == 0 or valve.tag(data(control, SHAFT), "Speed") != -32.0:
            raise RuntimeError(f"Reopened valve did not resume its signed shaft pulse: {resumed}")
        control.step_to(control.clock() + 1)
        for _ in range(18):
            current = data(control, HANDLE)
            if valve.tag(current, "InUse") == 0:
                break
            control.step_to(control.clock() + 1)
        if valve.tag(data(control, HANDLE), "InUse") != 0 or valve.tag(data(control, SHAFT), "Speed") != 0.0:
            raise RuntimeError("Reopened valve stroke did not stop cleanly after its saved timer.")
    print("Idle dyed-valve state and active copper stroke survived save/reopen; the signed pulse resumed and stopped.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
