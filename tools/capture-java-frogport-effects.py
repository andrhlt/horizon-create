#!/usr/bin/env python3
"""Run the original Java Frogport start cues and catch particles without a render window."""

import argparse
from pathlib import Path
import os
import subprocess
from tempfile import TemporaryDirectory

SOURCE = Path("src/main/java/com/simibubi/create/content/logistics/packagePort/frogport")
ROOT = Path(__file__).resolve().parent


def snippet(source, start, end, offset=0):
    begin = source.index(start, offset)
    return source[begin:source.index(end, begin)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("classpath", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    probe = (ROOT / "FrogportPackageEffectsProbe.java").read_text()
    block = (args.checkout / SOURCE / "FrogportBlockEntity.java").read_text()
    sound = (args.checkout / SOURCE / "FrogportSounds.java").read_text()
    effects = snippet(block, "\t\tif (level != null && level.isClientSide()) {",
                      "\n\n\t\tif (level != null && !level.isClientSide())",
                      block.index("public void startAnimation("))
    sounds = snippet(sound, "\tpublic void open(", "\tpublic void close(") + snippet(
        sound, "\tpublic void catchPackage(", "\tprivate boolean isPlayerNear(")
    source = probe.replace("/* ORIGINAL_CLIENT_EFFECTS */", effects).replace("/* ORIGINAL_SOUNDS */", sounds)
    java = Path(os.environ["JAVA_HOME"]) / "bin/java" if os.getenv("JAVA_HOME") else "java"
    with TemporaryDirectory(prefix="hc-java-frogport-effects-") as scratch:
        path = Path(scratch) / "FrogportPackageEffectsProbe.java"
        path.write_text(source)
        result = subprocess.check_output([java, "--class-path", args.classpath.read_text(), path], text=True)
    prefix = "CREATE_FROGPORT_EFFECT "
    rows = [line.removeprefix(prefix) for line in result.splitlines() if line.startswith(prefix)]
    if len(rows) != 18:
        raise RuntimeError(f"Incomplete Java Frogport effects trace, {len(rows)} rows")
    header = "scenario,kind,id,x,y,z,volume_or_dx,pitch_or_dy,delay"
    args.output.write_text("\n".join((header, *rows)) + "\n")
    print(f"Captured {len(rows)} original Java Frogport effects")


if __name__ == "__main__":
    main()
