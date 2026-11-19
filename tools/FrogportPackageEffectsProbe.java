import java.util.Locale;

import net.minecraft.core.BlockPos;
import net.minecraft.util.RandomSource;
import net.minecraft.world.phys.Vec3;

final class FrogportPackageEffectsProbe {
    private String scenario;
    private final BlockPos worldPosition = new BlockPos(12, 100, -9);
    private final Level level = new Level();
    private final Sounds sounds = new Sounds();
    private boolean currentlyDepositing;
    private BlockPos listener;
    private Vec3 anchor;
    private final Target target = new Target();

    private final class Target {
        Vec3 getExactTargetLocation(FrogportPackageEffectsProbe port, Level level, BlockPos pos) {
            return anchor;
        }
    }

    private enum ParticleTypes { BLOCK }
    private record BlockParticleOption(ParticleTypes type, int state) {}
    private static final class AllBlocks {
        static final AllBlocks ROPE = new AllBlocks();
        int getDefaultState() { return 0; }
    }

    private final class Level {
        RandomSource random;
        boolean isClientSide() { return true; }
        void addParticle(BlockParticleOption particle, double x, double y, double z,
                         double dx, double dy, double dz) {
            System.out.printf(Locale.ROOT, "CREATE_FROGPORT_EFFECT %s,particle,create:rope,%.9f,%.9f,%.9f,%.1f,%.1f,false%n",
                scenario, x, y, z, dx, dy);
        }
        void record(AllSoundEvents cue, Vec3 at, float volume, float pitch, boolean delay) {
            System.out.printf(Locale.ROOT, "CREATE_FROGPORT_EFFECT %s,sound,create:%s,%.9f,%.9f,%.9f,%.1f,%.1f,%b%n",
                scenario, cue.id, at.x, at.y, at.z, volume, pitch, delay);
        }
    }

    private enum AllSoundEvents {
        FROGPORT_OPEN("frogport_open"),
        FROGPORT_CATCH("frogport_catch"),
        FROGPORT_DEPOSIT("frogport_deposit");

        final String id;
        AllSoundEvents(String id) { this.id = id; }
        void playAt(Level level, Vec3 at, float volume, float pitch, boolean delay) {
            level.record(this, at, volume, pitch, delay);
        }
    }

    private final class Sounds {
        /* ORIGINAL_SOUNDS */
        private boolean isPlayerNear(BlockPos pos) {
            return pos.closerThan(listener, 20);
        }
    }

    private void startEffects() {
        /* ORIGINAL_CLIENT_EFFECTS */
    }

    private void sample(String name, boolean deposit, int distance, Vec3 targetAnchor) {
        scenario = name;
        currentlyDepositing = deposit;
        listener = worldPosition.offset(distance, 0, 0);
        anchor = targetAnchor;
        level.random = RandomSource.create(410723);
        startEffects();
    }

    public static void main(String[] args) {
        var probe = new FrogportPackageEffectsProbe();
        Vec3 anchor = new Vec3(13.125, 102.375, -8.75);
        probe.sample("catch_near", false, 4, anchor);
        probe.sample("catch_remote", false, 20, anchor);
        probe.sample("catch_missing_anchor", false, 4, null);
        probe.sample("deposit_near", true, 4, anchor);
        probe.sample("deposit_remote", true, 20, anchor);
    }
}
