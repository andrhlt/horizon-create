#!/usr/bin/env python3
"""Exercise Create item interactions between two clients on a local dedicated server."""

import argparse
from contextlib import ExitStack, contextmanager
from pathlib import Path
from shutil import copy2
import socket
import subprocess
import tempfile
import time

from fixture_world import ROOT, FixtureWorld


def until(description, test, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if result := test():
            return result
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for {description}")


def install_pack(home, pack=None):
    (home / "horizon-mods").mkdir(parents=True, exist_ok=True)
    copy2(pack or ROOT / ".local/create.hmod", home / "horizon-mods/create.hmod")
    (home / "horizon-mods.txt").write_text("mod.create:true\n", encoding="utf-8")


@contextmanager
def dedicated(args, scratch, *, scenario="multiplayer", overrides=None, pack=None):
    home = scratch / "server"
    install_pack(home, pack)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    properties = {
        "server-ip": "127.0.0.1",
        "server-port": port,
        "online-mode": "false",
        "enforce-secure-profile": "false",
        "white-list": "false",
        "level-name": "Parity",
        "level-type": "minecraft:flat",
        "view-distance": 4,
        "simulation-distance": 4,
        "spawn-protection": 0,
    }
    properties.update(overrides or {})
    (home / "server.properties").write_text(
        "".join(f"{k}={v}\n" for k, v in properties.items() if v is not None)
    )
    (home / "eula.txt").write_text("eula=true\n")
    logfile = ROOT / f".local/{scenario}-server.log"
    with logfile.open("w") as log:
        server = subprocess.Popen(
            [args.client, "--resources", args.resources, "--dedicated", "--nogui"],
            cwd=home, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, text=True,
        )

        def command(text):
            if server.poll() is not None:
                raise RuntimeError(f"Dedicated server exited. See {logfile}")
            server.stdin.write(text + "\n")
            server.stdin.flush()

        try:
            until("the local dedicated server",
                  lambda: server.poll() is not None or "Done (" in logfile.read_text(), 30)
            if server.poll() is not None:
                raise RuntimeError(f"Dedicated server failed to start. See {logfile}")
            yield f"127.0.0.1:{port}", command
        finally:
            if server.poll() is None:
                command("stop")
                try:
                    server.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    server.terminate()
                    server.wait(timeout=10)


@contextmanager
def joined_client(args, scratch, address, name, *, render=False, scenario="multiplayer", pack=None, env=None):
    home = scratch / name
    install_pack(home, pack)
    ctl = FixtureWorld(args.ctl, home / "ctl.sock", env)
    try:
        ctl.call("launch", "--offscreen" if render else "--headless", "--game", args.client, "--resources", args.resources,
                 "--server", address, "--name", name, "--game-dir", home, "--home", home,
                 "--render-distance", 4, "--wait")
        yield ctl
    finally:
        if ctl.socket.exists():
            ctl.call("quit")
            until(f"{name} to quit", lambda: not ctl.socket.exists(), 10)
        log = home / "ctl.log"
        if log.exists():
            copy2(log, ROOT / f".local/{scenario}-{name.lower()}.log")


def count(client, item):
    return client.call("inventory")["counts"].get(item, 0)


def run(args, scratch):
    with ExitStack() as stack:
        address, command = stack.enter_context(dedicated(args, scratch))
        alice = stack.enter_context(joined_client(args, scratch, address, "CreateAlice"))
        bob = stack.enter_context(joined_client(args, scratch, address, "CreateBob"))
        command("tp CreateAlice 7.5 96 -9.5")
        command("tp CreateBob 7.5 96 -8.5")
        until("the clients' experiment chunk", lambda: bob.call("block", 9, 95, -9).get("loaded"))
        command("fill 5 94 -12 13 94 -4 minecraft:smooth_stone")
        command("setblock 9 95 -9 minecraft:stripped_oak_log")
        command("setblock 9 95 -8 create:depot")
        command("give CreateAlice create:andesite_alloy 1")
        until("Alice’s alloy", lambda: count(alice, "create:andesite_alloy") == 1)
        until("Bob’s stripped log", lambda: bob.call("block", 9, 95, -9)["state"].startswith("minecraft:stripped_oak_log"))
        alice.call("select", "create:andesite_alloy")
        alice.call("interact", 9, 95, -9, "west")
        until("Bob to see the casing", lambda: bob.call("block", 9, 95, -9)["state"] == "create:andesite_casing")
        until("the server to consume Alice’s alloy", lambda: count(alice, "create:andesite_alloy") == 0)
        command("give CreateAlice minecraft:ender_pearl 8")
        until("Alice’s pearls", lambda: count(alice, "minecraft:ender_pearl") == 8)
        alice.call("select", "minecraft:ender_pearl")
        alice.call("interact", 9, 95, -8, "up")
        until("Alice to deposit eight pearls", lambda: count(alice, "minecraft:ender_pearl") == 0)
        bob.call("interact", 9, 95, -8, "up")
        until("Bob to receive eight pearls", lambda: count(bob, "minecraft:ender_pearl") == 8)
    print("Two clients shared a dedicated Horizon world. Both saw the casing, and Alice’s eight pearls reached Bob through the depot.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="hc-mp-") as tmp:
        run(args, Path(tmp))


if __name__ == "__main__":
    main()
