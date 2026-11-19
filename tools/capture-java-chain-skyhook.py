#!/usr/bin/env python3
"""Capture model-part poses from the original Java Chain Conveyor renderer."""

import argparse
from importlib import import_module
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

prepare = import_module("capture-java-elevator-standing").prepare
ROOT = Path(__file__).resolve().parent
SOURCE = Path("src/main/java/com/simibubi/create/foundation/render/PlayerSkyhookRenderer.java")


def adapt(source):
    start = source.index("\tprivate static void setHangingPose(")
    method = source[start:source.rindex("}")]
    replacements = {
        "private static void setHangingPose(boolean isLeftArmMain, HumanoidModel<?> model)":
            "static void setHangingPose(boolean isLeftArmMain, HumanoidModel<?> model, float time)",
        "\t\tif (Minecraft.getInstance().isPaused())\n\t\t\treturn;\n\n": "",
        "\t\tfloat time = AnimationTickHolder.getTicks(true) + AnimationTickHolder.getPartialTicks();\n": "",
    }
    for before, after in replacements.items():
        if method.count(before) != 1:
            raise ValueError(f"unexpected original skyhook method: {before!r}")
        method = method.replace(before, after)
    return (
        "import net.createmod.catnip.math.AngleHelper;\n"
        "import net.minecraft.client.model.HumanoidModel;\n"
        "import net.minecraft.client.model.geom.ModelPart;\n"
        "import net.minecraft.util.Mth;\n"
        "final class SkyhookPose {\n" + method + "}\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--classpath", type=Path)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    jdk = os.environ.get("JAVA_HOME")

    def tool(name):
        return str(Path(jdk) / "bin" / name) if jdk else name

    with TemporaryDirectory(prefix="hc-java-skyhook-") as directory:
        scratch = Path(directory)
        if args.classpath is None:
            prepare(args.checkout.resolve(strict=True), scratch, args.offline)
        classpath = (args.classpath or scratch / "client.classpath").read_text()
        source = scratch / "SkyhookPose.java"
        source.write_text(adapt((args.checkout / SOURCE).read_text()))
        subprocess.run([tool("javac"), "-proc:none", "-cp", classpath, "-d", scratch,
                        source, ROOT / "ChainSkyhookProbe.java"], check=True)
        trace = subprocess.check_output([tool("java"), "-cp", os.pathsep.join((str(scratch), classpath)),
                                         "ChainSkyhookProbe"], cwd=scratch, text=True)
    prefix = "CREATE_CHAIN_SKYHOOK "
    rows = [line.removeprefix(prefix) for line in trace.splitlines() if line.startswith(prefix)]
    if len(rows) != 168 or any(len(row.split(",")) != 10 for row in rows):
        raise ValueError(f"incomplete Java skyhook trace, {len(rows)} rows")
    header = "slim,left,time,part,x,y,z,x_rot,y_rot,z_rot"
    args.output.write_text("\n".join((header, *rows)) + "\n")
    print(f"Captured {len(rows)} Java skyhook model-part poses")


if __name__ == "__main__":
    main()
