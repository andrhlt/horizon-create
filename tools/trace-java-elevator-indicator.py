#!/usr/bin/env python3
"""Run Create's upstream indicator update body against the elevator GameTest trace."""

import argparse
import os
from pathlib import Path
from subprocess import check_call, check_output
from tempfile import TemporaryDirectory

from prepare import CREATE_REVISION

CONTROLS = Path(
    "src/main/java/com/simibubi/create/content/contraptions/"
    "actors/contraptionControls/ContraptionControlsMovement.java"
)

JAVA_PROBE = """
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import net.createmod.catnip.animation.LerpedFloat;
import net.createmod.catnip.animation.LerpedFloat.Chaser;
import net.minecraft.util.Mth;

class ElevatorIndicatorProbe {
    record Entity(double height) { double getY() { return height; } }
    record Elevator(int clientYTarget) { int getContactYOffset() { return 0; } }
    record Contraption(Entity entity) {}
    static class Controls {
        LerpedFloat indicator = LerpedFloat.angular().startWithValue(0);
        LerpedFloat button = LerpedFloat.linear().startWithValue(0).chase(0, .125f, Chaser.EXP);
        void tickAnimations() {
            button.tickChaser();
            indicator.tickChaser();
        }
    }

    static void advance(Controls cbe, double y, int target) {
        Contraption contraption = new Contraption(new Entity(y));
        Elevator ec = new Elevator(target);
        /* INDICATOR_UPDATE */
    }

    public static void main(String[] args) throws Exception {
        var previous = LerpedFloat.class.getDeclaredField("previousValue");
        previous.setAccessible(true);
        var value = LerpedFloat.class.getDeclaredField("value");
        value.setAccessible(true);
        var host = new Controls();
        var guest = new Controls();
        System.out.println(
            "tick,current_y,target_y,previous_angle,angle,chase_angle,frame,"
            + "host_previous_button,host_button,guest_previous_button,guest_button"
        );
        var rows = Files.readAllLines(Path.of(args[0]));
        for (var row : rows.subList(1, rows.size())) {
            var cells = row.split(",", -1);
            int tick = Integer.parseInt(cells[0]);
            if (cells[1].isEmpty()) continue;
            double y = Double.parseDouble(cells[1]);
            int target = Integer.parseInt(cells[2]);
            advance(host, y, target);
            advance(guest, y, target);
            int frame = (((int) host.indicator.getValue(1) / 45) % 8 + 8) % 8;
            System.out.printf(Locale.ROOT, "%d,%d,%d,%s,%s,%s,%d,%s,%s,%s,%s%n",
                tick, Math.round(y), target, previous.getFloat(host.indicator), value.getFloat(host.indicator),
                host.indicator.getChaseTarget(), frame, previous.getFloat(host.button), value.getFloat(host.button),
                previous.getFloat(guest.button), value.getFloat(guest.button));
            // The guest presses the control immediately after the service trace samples tick 25.
            if (tick == 25) guest.button.setValue(1);
        }
    }
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("create_source", type=Path, help="Checkout at the pinned Create revision")
    parser.add_argument("java_build", type=Path, help="Developer checkout with a completed runGameTestServer build")
    parser.add_argument("ponder_jar", type=Path, help="Pinned Ponder 1.0.82 NeoForge jar")
    parser.add_argument("--java", default="java", help="Java 21 executable")
    args = parser.parse_args()

    revision = check_output(["git", "rev-parse", "HEAD"], cwd=args.create_source, text=True).strip()
    if revision != CREATE_REVISION:
        parser.error(f"expected Create {CREATE_REVISION}, found {revision}")

    source = (args.create_source / CONTROLS).read_text(encoding="utf-8")
    start = source.index("\t\tcbe.tickAnimations();\n\n\t\tint currentY")
    end = source.index("\n\t}\n\n\tpublic static void tickFloorSelection", start)
    probe = JAVA_PROBE.replace("/* INDICATOR_UPDATE */", source[start:end].lstrip())
    moddev = args.java_build.resolve() / "build/moddev"
    runtime = [moddev / "artifacts/neoforge-21.1.219-merged.jar", args.ponder_jar.resolve()]
    classpath = os.pathsep.join(map(str, runtime))
    classpath += os.pathsep + os.pathsep.join(
        (moddev / "gameTestServerLegacyClasspath.txt").read_text(encoding="utf-8").splitlines()
    )
    fixture = Path(__file__).resolve().parents[1] / "fixtures/elevator-service-java.csv"
    java = str(Path(args.java).resolve()) if os.sep in args.java else args.java
    with TemporaryDirectory(prefix="create-elevator-indicator-") as scratch:
        source_file = Path(scratch) / "ElevatorIndicatorProbe.java"
        source_file.write_text(probe, encoding="utf-8")
        check_call([java, "-cp", classpath, str(source_file), str(fixture)], cwd=scratch)


if __name__ == "__main__":
    main()
