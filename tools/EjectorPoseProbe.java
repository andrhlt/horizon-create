package com.simibubi.create.content.logistics.depot;

import com.mojang.blaze3d.vertex.PoseStack;
import com.simibubi.create.content.kinetics.base.KineticBlockEntity;
import dev.engine_room.flywheel.lib.transform.PoseTransformStack;
import net.minecraft.SharedConstants;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.Bootstrap;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.entity.BlockEntityType;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import org.joml.Vector3f;

public class EjectorPoseProbe {
    public static void main(String[] args) {
        net.neoforged.fml.loading.LoadingModList.of(java.util.List.of(), java.util.List.of(),
            java.util.List.of(), java.util.List.of(), java.util.Map.of());
        net.neoforged.fml.ModList.of(java.util.List.of(), java.util.List.of());
        SharedConstants.tryDetectVersion();
        Bootstrap.bootStrap();
        for (var direction : Direction.Plane.HORIZONTAL) {
            var state = Blocks.FURNACE.defaultBlockState().setValue(BlockStateProperties.HORIZONTAL_FACING, direction);
            var blockEntity = new KineticBlockEntity(BlockEntityType.FURNACE, BlockPos.ZERO, state);
            for (int i = 0; i <= 4; i++) {
                float lift = i / 4.0f;
                var poses = new PoseStack();
                EjectorRenderer.applyLidAngle(blockEntity, lift * 70, new PoseTransformStack(poses));
                var pose = poses.last().pose();
                var a = pose.transformPosition(new Vector3f(0, 0, 0));
                var b = pose.transformPosition(new Vector3f(1, 0, 0));
                var c = pose.transformPosition(new Vector3f(0, 1, 0));
                var d = pose.transformPosition(new Vector3f(0, 0, 1));
                System.out.printf(java.util.Locale.ROOT, "CREATE_EJECTOR_LID %s,%.8f,"
                    + "%.8f,%.8f,%.8f,%.8f,%.8f,%.8f,%.8f,%.8f,%.8f,%.8f,%.8f,%.8f%n",
                    direction.getName(), lift, a.x, a.y, a.z, b.x, b.y, b.z, c.x, c.y, c.z, d.x, d.y, d.z);
            }
        }
    }
}
