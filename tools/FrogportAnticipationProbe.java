import java.util.Locale;

import net.createmod.catnip.animation.LerpedFloat;
import net.createmod.catnip.animation.LerpedFloat.Chaser;

class FrogportAnticipationProbe {
    public static void main(String[] args) {
        LerpedFloat progress = LerpedFloat.linear();
        int request = -1;
        System.out.println("tick,request,reset,partial,anticipation,head_factor");
        for (int tick = 0; tick < 19; tick++) {
            if (tick < 4 || tick == 10 || tick == 12) {
                progress.chase(1, 0.1, Chaser.LINEAR);
                request = tick;
            }
            if (progress.getValue() == 1)
                progress.startWithValue(0);
            progress.tickChaser();
            boolean reset = tick == 16;
            if (reset)
                progress.startWithValue(0);
            for (float partial : new float[] {0, 0.25f, 0.5f, 1}) {
                float phase = progress.getValue(partial);
                float head = phase > 0 ? (float) Math.max(0, 1 - Math.pow((phase * 1.25) * 2 - 1, 4)) : 0;
                System.out.printf(Locale.ROOT, "%d,%d,%b,%.2f,%.9f,%.9f%n",
                    tick, request, reset, partial, phase, head);
            }
        }
    }
}
