import com.simibubi.create.content.logistics.depot.EntityLauncher;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.Locale;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;

public class EjectorTrajectoryProbe {
    public static void main(String[] args) throws Exception {
        var xMotion = EntityLauncher.class.getDeclaredField("xMotion");
        var yMotion = EntityLauncher.class.getDeclaredField("yMotion");
        xMotion.setAccessible(true);
        yMotion.setAccessible(true);
        try (var input = new BufferedReader(new InputStreamReader(System.in))) {
            for (String line; (line = input.readLine()) != null; ) {
                String[] field = line.split(",");
                var pos = new BlockPos(Integer.parseInt(field[0]), Integer.parseInt(field[1]), Integer.parseInt(field[2]));
                var facing = Direction.fromDelta(Integer.parseInt(field[3]), 0, Integer.parseInt(field[4]));
                var launcher = new EntityLauncher(Integer.parseInt(field[5]), Integer.parseInt(field[6]));
                float time = Float.parseFloat(field[7]);
                double duration = launcher.getTotalFlyingTicks() + 3;
                int count = (int) duration / 3 + 1;
                double spacing = duration / count;
                if (args.length > 0 && args[0].equals("--coefficients")) {
                    System.out.printf(Locale.ROOT, "JAVA_COEFFICIENTS %s,%s,%s,%.17g,%.17g,%.17g%n", field[0], field[1], field[2],
                        xMotion.getDouble(launcher), yMotion.getDouble(launcher), launcher.getTotalFlyingTicks());
                    continue;
                }
                System.out.printf(Locale.ROOT, "JAVA_BATCH_ARC %d,%.9f%n", count, spacing);
                for (int i = 0; i < count; i++) {
                    double offset = ((time / 3) % spacing) + i * spacing;
                    var point = launcher.getGlobalPos(offset, facing.getOpposite(), pos);
                    System.out.printf(Locale.ROOT, "JAVA_BATCH_DUST %d,%.9f,%.9f,%.9f,%.9f%n",
                        i, offset, point.x, point.y, point.z);
                }
            }
        }
    }
}
