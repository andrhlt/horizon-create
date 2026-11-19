#!/usr/bin/env python3
"""Replay the original Java rider controller with a headless client adapter."""

import argparse
from importlib import import_module
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

prepare = import_module("capture-java-elevator-standing").prepare
HERE = Path(__file__).resolve().parent
CONTROLLER = Path(
    "src/main/java/com/simibubi/create/content/kinetics/chainConveyor/ChainConveyorRidingHandler.java"
)
COUNTS = {
    "straight": 32,
    "rising_reversal": 40,
    "rising_power_pause": 28,
    "junction": 20,
    "disconnect": 5,
    "release_tool": 4,
    "catchup_timeout": 20,
}
HEADER = (
    "scenario,tick,rpm,server_speed,wheel,connection,position,catching_up,reversed,keepalives,stops,"
    "feet_x,feet_y,feet_z,prior_vx,prior_vy,prior_vz,target_x,target_y,target_z,next_vx,next_vy,next_vz"
)


def adapt(source):
    """Replace client I/O with supplied values, retaining the production control flow."""
    imports = (
        "com.simibubi.create.AllTags.AllItemTags",
        "com.simibubi.create.foundation.utility.ServerSpeedProvider",
        "net.createmod.catnip.animation.AnimationTickHolder",
        "net.createmod.catnip.platform.CatnipServices",
        "net.minecraft.client.Minecraft",
        "net.minecraft.client.resources.sounds.SimpleSoundInstance",
        "net.minecraft.network.chat.Component",
        "net.minecraft.sounds.SoundEvents",
    )
    edits = {f"import {name};\n": "" for name in imports}
    a = source.index("\t\tComponent component =")
    b = source.index("\n\t}", a)
    edits[source[a:b]] = ""
    a = source.index("\t\tMinecraft.getInstance()\n\t\t\t.getSoundManager()", source.index("private static void stopRiding"))
    b = source.index("\n\t}", a)
    edits[source[a:b]] = ""
    edits.update({
        "Minecraft mc = Minecraft.getInstance();": "ChainRideProbe.Client mc = ChainRideProbe.Client.getInstance();",
        "updateTargetPosition(Minecraft mc,": "updateTargetPosition(ChainRideProbe.Client mc,",
        "mc.player.isHolding(AllItemTags.CHAIN_RIDEABLE::matches)": "mc.player.holding",
        "ServerSpeedProvider.get()": "mc.serverSpeed",
        "AnimationTickHolder.getTicks()": "mc.tick",
        "CatnipServices.NETWORK.sendToServer(new ServerboundChainConveyorRidingPacket(ridingChainConveyor, false));": "mc.send(false);",
        "CatnipServices.NETWORK.sendToServer(new ServerboundChainConveyorRidingPacket(ridingChainConveyor, true));":
            "ChainRideProbe.Client.getInstance().send(true);",
        "Vec3 diff = targetPosition.subtract(playerPosition);":
            "mc.target = targetPosition;\n\t\tVec3 diff = targetPosition.subtract(playerPosition);",
    })
    for before, after in edits.items():
        occurrences = 2 if before == "Minecraft mc = Minecraft.getInstance();" else 1
        if source.count(before) != occurrences:
            raise ValueError(f"unexpected original controller text: {before!r}")
        source = source.replace(before, after)
    return source


def adapt_authority(source):
    replacements = {
        "import net.createmod.catnip.platform.CatnipServices;\n": "",
        "import net.minecraft.world.entity.player.Player;\n": "",
        "public static int ticks;": "public static int ticks;\n\tpublic static int probeSyncs;",
        "Player player": "UUID player",
        "player.getUUID()": "player",
        "CatnipServices.NETWORK.sendToAllClients(new ClientboundChainConveyorRidingPacket(hangingPlayers.keySet()));":
            "probeSyncs++;",
    }
    for before, after in replacements.items():
        count = 2 if before in ("Player player", "player.getUUID()") else 1
        if source.count(before) != count:
            raise ValueError(f"unexpected original authority text: {before!r}")
        source = source.replace(before, after)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--classpath", type=Path)
    parser.add_argument("--authority-output", type=Path)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    checkout = args.checkout.resolve(strict=True)
    java_home = os.environ.get("JAVA_HOME")

    def java_tool(name):
        return str(Path(java_home) / "bin" / name) if java_home else name

    with TemporaryDirectory(prefix="hc-java-chain-ride-") as directory:
        scratch = Path(directory)
        if args.classpath is None:
            prepare(checkout, scratch, args.offline)
        classpath = (args.classpath or scratch / "client.classpath").read_text()
        controller = scratch / CONTROLLER.name
        controller.write_text(adapt((checkout / CONTROLLER).read_text()))
        authority = scratch / "ServerChainConveyorHandler.java"
        authority_source = (checkout / CONTROLLER).with_name(authority.name)
        authority.write_text(adapt_authority(authority_source.read_text()))
        subprocess.run([
            java_tool("javac"), "-proc:none", "-cp", classpath, "-d", scratch,
            controller, authority, HERE / "ChainRideProbe.java",
        ], check=True)
        trace = subprocess.check_output([
            java_tool("java"), "-cp", os.pathsep.join((str(scratch), classpath)),
            "com.simibubi.create.content.kinetics.chainConveyor.ChainRideProbe",
        ], cwd=scratch, text=True)
    prefix = "CREATE_CHAIN_RIDE "
    rows = [line.removeprefix(prefix) for line in trace.splitlines() if line.startswith(prefix)]
    expected = [(scenario, str(tick)) for scenario, count in COUNTS.items() for tick in range(1, count + 1)]
    if [tuple(row.split(",")[:2]) for row in rows] != expected:
        raise ValueError("incomplete Java chain riding trace")
    if any(len(row.split(",")) != len(HEADER.split(",")) for row in rows):
        raise ValueError("unexpected Java chain riding columns")
    args.output.write_text("\n".join((HEADER, *rows)) + "\n")
    print(f"Captured {len(rows)} Java chain rider ticks in {args.output}.")

    if args.authority_output:
        prefix = "CREATE_CHAIN_RIDE_AUTHORITY "
        samples = [line.removeprefix(prefix) for line in trace.splitlines() if line.startswith(prefix)]
        expected = [(scenario, str(tick)) for scenario, count in (("expiry", 42), ("stop", 15))
                    for tick in range(1, count + 1)]
        if [tuple(row.split(",")[:2]) for row in samples] != expected:
            raise ValueError("incomplete Java ride authority trace")
        header = "scenario,tick,action,ttl,syncs"
        args.authority_output.write_text("\n".join((header, *samples)) + "\n")
        print(f"Captured {len(samples)} Java ride authority ticks in {args.authority_output}.")


if __name__ == "__main__":
    main()
