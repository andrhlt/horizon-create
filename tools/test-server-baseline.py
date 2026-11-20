#!/usr/bin/env python3
"""Check dedicated server defaults, a config override, op permissions, and rejoin."""

import argparse
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


multiplayer = load("test-multiplayer")
OP = "ConfigOperator"
GUEST = "ConfigGuest"


def verify(args, scratch):
    with multiplayer.dedicated(
        args,
        scratch,
        scenario="server-baseline",
        overrides={"difficulty": "hard", "spawn-protection": None},
        pack=args.pack,
    ) as (address, command):
        server = scratch / "server"
        properties = server / "server.properties"
        multiplayer.until("server.properties defaults", properties.exists)
        values = dict(
            line.split("=", 1)
            for line in properties.read_text(encoding="utf-8").splitlines()
            if "=" in line
        )
        if values.get("spawn-protection") != "16":
            raise RuntimeError(f"Expected the server default spawn-protection=16, got {values.get('spawn-protection')}.")
        if values.get("difficulty") != "hard":
            raise RuntimeError(f"The configured difficulty override was not retained: {values.get('difficulty')}.")

        with multiplayer.joined_client(args, scratch, address, OP, scenario="server-baseline", pack=args.pack) as operator:
            with multiplayer.joined_client(args, scratch, address, GUEST, scenario="server-baseline", pack=args.pack) as guest:
                command(f"op {OP}")
                multiplayer.until(
                    "operator permissions to be saved",
                    lambda: (server / "ops.json").exists()
                    and any(row.get("name") == OP and row.get("level") == 4
                            for row in json.loads((server / "ops.json").read_text(encoding="utf-8"))),
                )

                operator.call("chat", "/give @s minecraft:diamond 1")
                multiplayer.until("the operator command to succeed", lambda:
                                  multiplayer.count(operator, "minecraft:diamond") == 1)
                guest.call("chat", "/give @s minecraft:diamond 1")
                guest.call("wait", 2)
                if multiplayer.count(guest, "minecraft:diamond") != 0:
                    raise RuntimeError("A nonoperator executed the operator-only /give command.")
                command(f"give {GUEST} minecraft:paper 1")
                multiplayer.until("guest inventory to save", lambda:
                                  multiplayer.count(guest, "minecraft:paper") == 1)

                operator.call("chat", "/difficulty")
                multiplayer.until(
                    "the configured hard difficulty to be observable",
                    lambda: any("Hard" in str(line) for line in operator.call("chat-log", 100)["chat"]),
                )

            with multiplayer.joined_client(args, scratch, address, GUEST, scenario="server-baseline", pack=args.pack) as rejoined:
                multiplayer.until("the guest inventory to load after reconnect", lambda:
                                  multiplayer.count(rejoined, "minecraft:paper") == 1)
                if multiplayer.count(rejoined, "minecraft:diamond") != 0:
                    raise RuntimeError("The nonoperator gained items during reconnect.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-server-baseline-") as scratch:
        verify(args, Path(scratch))
    print("Dedicated defaults and difficulty override passed; op-only command access and guest reconnect passed.")


if __name__ == "__main__":
    main()
