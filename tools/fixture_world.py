"""Launch an isolated Horizon GameTest world through horizon-ctl."""

from contextlib import contextmanager
import json
import hashlib
import os
from pathlib import Path
from shutil import copy2
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def install_pack(game, pack=None):
    mods = game / "horizon-mods"
    mods.mkdir(parents=True)
    source = pack or ROOT / ".local/create.hmod"
    target = mods / "create.hmod"
    copy2(source, target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if digest != hashlib.sha256(source.read_bytes()).hexdigest():
        raise RuntimeError(f"Installed Create pack differs from source: {target}")
    print(f"Create pack installed: {target} sha256={digest}")
    (game / "horizon-mods.txt").write_text("mod.create:true\n", encoding="utf-8")


def run_command_harness(args, game, world, operations, env=None):
    script = game / "harness-script.jsonl"
    output = game / "harness-output.jsonl"
    script.write_text("".join(json.dumps(op) + "\n" for op in operations), encoding="utf-8")
    result = subprocess.run(
        (str(args.client), "--headless", "--resources", str(args.resources),
         "--game-dir", str(game), "--home", str(game), "--world", world, "--render-distance", "4"),
        cwd=game, env=os.environ | (env or {}) | {
            "HORIZON_COMMAND_SCRIPT": str(script),
            "HORIZON_COMMAND_OUTPUT": str(output),
            "HORIZON_NO_AUDIO": "1",
            "HORIZON_NO_DISCORD": "1",
            "HORIZON_HARNESS_TIMEOUT": "30",
        }, capture_output=True, text=True, timeout=50)
    if result.returncode:
        raise RuntimeError(f"Headless command harness failed: {result.stderr[-5000:]}")
    return [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]


def last_command_message(record):
    return "".join(span[0] for span in record["messages"][-1])


@contextmanager
def fixture_world(args, world, template=None, *, render=False, env=None, pack=None, terrain_seed=None,
                  artifact_dir=None):
    with tempfile.TemporaryDirectory(prefix="hc-fixture-") as tmp:
        scratch = Path(tmp)
        socket = scratch / "ctl.sock"
        game = scratch / "game"
        install_pack(game, pack)
        if template is not None:
            source = ROOT / ".local/fixtures/data/create/structure" / template
            saved = game / f"saves/{world}/generated/create/structures" / template
            saved.parent.mkdir(parents=True)
            copy2(source, saved)
        control = FixtureWorld(args.ctl, socket, env, launch=(
            "--offscreen" if render else "--headless",
            "--game", args.client, "--resources", args.resources, "--world", world,
            "--creative", "--wait", "--game-dir", game, "--home", game,
            *(("--test-terrain",) if terrain_seed is None else ("--seed", terrain_seed)),
            "--render-distance", 4,
        ))
        try:
            control.open()
            yield control
        finally:
            if socket.exists():
                control.stop()
            log = scratch / "ctl.log"
            if log.exists():
                artifacts = artifact_dir or ROOT / ".local"
                artifacts.mkdir(parents=True, exist_ok=True)
                copy2(log, artifacts / f"horizon-{world.lower()}.log")


class FixtureWorld:
    def __init__(self, ctl, socket, env, *, launch=None):
        self.ctl = ctl
        self.socket = socket
        self.env = os.environ | (env or {})
        self._launch = launch

    def open(self):
        self.call("launch", *self._launch)
        self.command("/tick freeze")

    def stop(self):
        self.call("quit")
        deadline = time.monotonic() + 10
        while self.socket.exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("Horizon did not close its control socket after quit.")
            time.sleep(0.05)

    def restart(self, *, client=None):
        self.stop()
        if client is not None:
            launch = list(self._launch)
            launch[launch.index("--game") + 1] = client
            self._launch = tuple(launch)
        self.open()

    def call(self, *args, script=None):
        result = subprocess.run(
            [str(self.ctl), "--socket", str(self.socket), *map(str, args)],
            input=script, text=True, env=self.env, capture_output=True, timeout=45,
        )
        if result.returncode:
            raise RuntimeError(f"{args} failed: {result.stdout} {result.stderr}")
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        if not replies or any(reply.get("ok") is False for reply in replies):
            raise RuntimeError(f"{args} failed: {replies}")
        return replies if script is not None else replies[-1]

    def command(self, command):
        return self.call("command", command)["chat"][-1]

    def commands(self, commands):
        replies = self.call("script", script="".join(f"command {json.dumps(cmd)}\n" for cmd in commands))
        return [reply["chat"][-1] for reply in replies]

    def clock(self):
        message = self.command("/time query gametime")
        return int(message.split()[-2])

    def step_to(self, tick, *, before=None):
        if before is None:
            self.command("/tick step 1")
        else:
            self.commands((before, "/tick step 1"))
        end = time.monotonic() + 4
        while (now := self.clock()) != tick:
            if now > tick or time.monotonic() >= end:
                raise RuntimeError(f"Expected game tick {tick}, got {now}")
