#!/usr/bin/env python3
"""Capture the pinned Java Ejector renderer's lid transforms."""
import argparse
from importlib import import_module
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

prepare = import_module("capture-java-elevator-standing").prepare
PROBE = Path(__file__).with_name("EjectorPoseProbe.java")
PREFIX = "CREATE_EJECTOR_LID "
HEADER = "facing,lift,origin_x,origin_y,origin_z,right_x,right_y,right_z,up_x,up_y,up_z,back_x,back_y,back_z"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    java_home = os.environ.get("JAVA_HOME")
    java = str(Path(java_home) / "bin/java") if java_home else "java"
    javac = str(Path(java_home) / "bin/javac") if java_home else "javac"
    with TemporaryDirectory(prefix="hc-java-ejector-lid-") as directory:
        scratch = Path(directory)
        prepare(args.checkout.resolve(strict=True), scratch, args.offline)
        classpath = (scratch / "client.classpath").read_text()
        subprocess.run([javac, "-proc:none", "-cp", classpath, "-d", scratch, PROBE], check=True)
        trace = subprocess.check_output([
            java, "-cp", os.pathsep.join((str(scratch), classpath)),
            "com.simibubi.create.content.logistics.depot.EjectorPoseProbe",
        ], text=True)
    rows = [line.removeprefix(PREFIX) for line in trace.splitlines() if line.startswith(PREFIX)]
    if len(rows) != 20:
        raise RuntimeError(f"Expected 20 lid poses from Java. Captured {len(rows)}.")
    args.output.write_text("\n".join([HEADER, *rows]) + "\n")
    print(f"Captured {len(rows)} original lid poses in {args.output}.")


if __name__ == "__main__":
    main()
