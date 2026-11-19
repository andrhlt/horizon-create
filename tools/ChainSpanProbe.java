import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.simibubi.create.content.kinetics.chainConveyor.ChainConveyorBlockEntity;
import com.simibubi.create.content.kinetics.chainConveyor.ChainConveyorRenderer;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.entity.BlockEntityType;
import net.minecraft.world.phys.Vec3;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.Locale;

public class ChainSpanProbe {
    public static void main(String[] args) {
        net.neoforged.fml.loading.LoadingModList.of(java.util.List.of(), java.util.List.of(),
            java.util.List.of(), java.util.List.of(), java.util.Map.of());
        net.neoforged.fml.ModList.of(java.util.List.of(), java.util.List.of());
        net.minecraft.SharedConstants.tryDetectVersion();
        net.minecraft.server.Bootstrap.bootStrap();
        var renderer = new ChainConveyorRenderer(null);
        var wheel = new ChainConveyorBlockEntity(BlockEntityType.FURNACE, BlockPos.ZERO,
            Blocks.FURNACE.defaultBlockState());
        for (double distance : new double[] {63, 64, 96, 128, 255, 256, 257}) {
            var camera = Vec3.atCenterOf(BlockPos.ZERO).add(0, distance, 0);
            System.out.printf(Locale.ROOT, "CREATE_CHAIN_VISIBILITY %.0f,%b,%b,%d%n",
                distance, renderer.shouldRender(wheel, camera),
                renderer.shouldRenderOffScreen(wheel), renderer.getViewDistance());
        }
        for (double distance : new double[] {47, 48, 49, 60}) {
            boolean far = !Vec3.ZERO.closerThan(new Vec3(0, 0, distance), ChainConveyorRenderer.MIP_DISTANCE);
            var lights = new ArrayList<int[]>();
            var positions = new ArrayList<float[]>();
            var uvs = new ArrayList<float[]>();
            var consumer = (VertexConsumer) Proxy.newProxyInstance(
                VertexConsumer.class.getClassLoader(), new Class<?>[] {VertexConsumer.class},
                (proxy, method, values) -> {
                    if (method.isDefault())
                        return InvocationHandler.invokeDefault(proxy, method, values);
                    switch (method.getName()) {
                    case "addVertex" -> positions.add(new float[] {
                        (float) values[0], (float) values[1], (float) values[2]});
                    case "setUv" -> uvs.add(new float[] {(float) values[0], (float) values[1]});
                    case "setUv2" -> lights.add(new int[] {(int) values[0] / 16, (int) values[1] / 16});
                    }
                    return proxy;
                });
            ChainConveyorRenderer.renderChain(new PoseStack(), type -> consumer, 0.25f, 6,
                LightTexture.pack(8, 0), LightTexture.pack(11, 0), far);
            double width = 2 * positions.stream().mapToDouble(p -> Math.max(Math.abs(p[0] - .5), Math.abs(p[2] - .5)))
                .max().orElseThrow();
            double minU = uvs.stream().mapToDouble(uv -> uv[0]).min().orElseThrow();
            double maxU = uvs.stream().mapToDouble(uv -> uv[0]).max().orElseThrow();
            double minV = uvs.stream().mapToDouble(uv -> uv[1]).min().orElseThrow();
            double maxV = uvs.stream().mapToDouble(uv -> uv[1]).max().orElseThrow();
            if (positions.size() != 16 || uvs.size() != positions.size() || lights.size() != positions.size())
                throw new IllegalStateException("Expected four chain quads");
            if (distance <= 48) {
                for (int i = 0; i < positions.size(); i++) {
                    var light = lights.get(i);
                    System.out.printf(Locale.ROOT, "CREATE_CHAIN_SPAN_LIGHT %.0f,%d,%.0f,%d,%d%n",
                        distance, i, positions.get(i)[1] / 6.0, light[0], light[1]);
                }
            }
            System.out.printf(Locale.ROOT, "CREATE_CHAIN_MIP %.0f,%b,%d,%.8f,%.8f,%.8f,%.8f,%.8f%n",
                distance, far, positions.size() / 4, width, minU, maxU, minV, maxV);
        }
    }
}
