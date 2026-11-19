import java.util.Locale;

import net.createmod.catnip.animation.LerpedFloat;
import net.createmod.catnip.animation.LerpedFloat.Chaser;

class FrogportOpenProbe {
    public static void main(String[] args) {
        // FrogportBlockEntity's chaser and FrogportRenderer's manual pose.
        LerpedFloat progress = LerpedFloat.linear()
            .startWithValue(0)
            .chase(0, 0.35, Chaser.LINEAR);
        int[] viewers = {0, 1, 2, 1, 1, 0, 1, 1, 0, 0, 0, 0};
        System.out.println("tick,viewers,partial,progress,head_pitch,tongue,close");
        for (int tick = 0; tick < viewers.length; tick++) {
            progress.updateChaseTarget(viewers[tick] > 0 ? 1 : 0);
            boolean wasOpen = progress.getValue() > 0;
            progress.tickChaser();
            boolean close = wasOpen && progress.getValue() == 0;
            for (float partial : new float[] {0, 0.25f, 0.5f, 1}) {
                float value = progress.getValue(partial);
                System.out.printf(Locale.ROOT, "%d,%d,%.2f,%.9f,%.9f,%.9f,%b%n",
                    tick, viewers[tick], partial, value, value * 60, value * 0.25f, close);
            }
        }
    }
}
