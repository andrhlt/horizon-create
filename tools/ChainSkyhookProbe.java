import java.util.Locale;
import net.minecraft.client.model.PlayerModel;
import net.minecraft.client.model.geom.builders.CubeDeformation;
import net.minecraft.client.model.geom.builders.LayerDefinition;

public final class ChainSkyhookProbe {
    public static void main(String[] args) {
        for (boolean slim : new boolean[] {false, true}) {
            for (boolean left : new boolean[] {false, true}) {
                for (float time : new float[] {0f, 1f, 7.25f, 11.5f, 20.75f, 60f}) {
                    var definition = LayerDefinition.create(PlayerModel.createMesh(CubeDeformation.NONE, slim), 64, 64);
                    var model = new PlayerModel<>(definition.bakeRoot(), slim);
                    model.head.xRot = .24f;
                    model.head.yRot = -.38f;
                    model.hat.xRot = .24f;
                    model.hat.yRot = -.38f;
                    var parts = new net.minecraft.client.model.geom.ModelPart[] {
                        model.head, model.body, model.rightArm, model.leftArm, model.rightLeg, model.leftLeg, model.hat
                    };
                    SkyhookPose.setHangingPose(left, model, time);
                    for (int part = 0; part < parts.length; part++) {
                        var pose = parts[part];
                        System.out.printf(Locale.ROOT, "CREATE_CHAIN_SKYHOOK %b,%b,%.2f,%d,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f%n",
                            slim, left, time, part, pose.x, pose.y, pose.z, pose.xRot, pose.yRot, pose.zRot);
                    }
                }
            }
        }
    }
}
