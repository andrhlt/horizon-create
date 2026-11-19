package com.simibubi.create.content.kinetics.chainConveyor;

import java.util.HashMap;
import java.util.List;
import java.util.Locale;

import net.minecraft.SharedConstants;
import net.minecraft.core.BlockPos;
import net.minecraft.server.Bootstrap;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.entity.BlockEntityType;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

public final class ChainRideProbe {
    static final class Client {
        static Client active;
        final Player player = new Player();
        final HashMap<BlockPos, BlockEntity> wheels = new HashMap<>();
        final Level level = new Level();
        int tick;
        int keepalives;
        int stops;
        float serverSpeed = 1;
        Vec3 target;

        static Client getInstance() { return active; }

        final class Level {
            BlockEntity getBlockEntity(BlockPos at) { return wheels.get(at); }
        }

        boolean isPaused() { return false; }

        void send(boolean stop) {
            if (stop)
                stops++;
            else
                keepalives++;
        }
    }

    static final class Player {
        Vec3 feet = new Vec3(0, -2, 0);
        Vec3 velocity = Vec3.ZERO;
        Vec3 look = new Vec3(1, 0, 0);
        boolean holding = true;
        boolean sneaking;

        Vec3 position() { return feet; }
        Vec3 getLookAngle() { return look; }
        float getScale() { return 1; }
        AABB getBoundingBox() { return new AABB(0, 0, 0, .6, 1.8, .6); }
        boolean isShiftKeyDown() { return sneaking; }
        Vec3 getDeltaMovement() { return velocity; }
        void setDeltaMovement(Vec3 value) { velocity = value; }
    }

    private static ChainConveyorBlockEntity wheel(BlockPos pos, BlockPos link) {
        var entity = new ChainConveyorBlockEntity(BlockEntityType.FURNACE, pos,
            Blocks.FURNACE.defaultBlockState());
        entity.connections.add(link);
        entity.setSpeed(128);
        return entity;
    }

    private static void capture(String scenario, BlockPos delta, BlockPos entry, float progress, int limit) {
        var client = new Client();
        Client.active = client;
        var a = wheel(BlockPos.ZERO, delta);
        var b = wheel(delta, delta.multiply(-1));
        client.wheels.put(BlockPos.ZERO, a);
        client.wheels.put(delta, b);
        var branch = new BlockPos(0, 0, 7);
        if (scenario.equals("junction")) {
            a.connections.add(branch);
            client.wheels.put(branch, wheel(branch, branch.multiply(-1)));
            client.player.look = Vec3.atLowerCornerOf(branch).normalize();
        } else {
            client.player.look = Vec3.atLowerCornerOf(delta).normalize();
        }
        // Values that the original click selection supplies to embark.
        ChainConveyorRidingHandler.embark(BlockPos.ZERO, progress, entry);
        for (int tick = 1; tick <= limit; tick++) {
            client.tick = tick;
            boolean pauseCase = scenario.equals("rising_power_pause");
            if ((scenario.equals("rising_reversal") || pauseCase) && tick == 6) {
                a.setSpeed(-128);
                b.setSpeed(-128);
            }
            if (pauseCase && tick == 9) {
                a.setSpeed(0);
                b.setSpeed(0);
            }
            if (pauseCase && tick == 14) {
                a.setSpeed(128);
                b.setSpeed(128);
            }
            if (scenario.equals("rising_reversal") && tick == 15)
                client.serverSpeed = .75f;
            if (scenario.equals("straight") && tick == 32)
                client.player.sneaking = true;
            if (scenario.equals("disconnect") && tick == 5)
                a.connections.clear();
            if (scenario.equals("release_tool") && tick == 4)
                client.player.holding = false;

            // Supply a known player pose and prior velocity to the original
            // controller. Its output is recorded before vanilla integration.
            client.player.feet = client.target == null
                ? new Vec3(.5, -2, .5) : client.target.add(-.125, -2.425, .0625);
            if (scenario.equals("catchup_timeout"))
                client.player.feet = new Vec3(-8, -4, -8);
            Vec3 feet = client.player.feet;
            Vec3 prior = client.player.velocity;
            client.target = null;
            ChainConveyorRidingHandler.clientTick();
            var owner = ChainConveyorRidingHandler.ridingChainConveyor;
            String wheel = owner == null ? "-" : owner.equals(delta) ? "B" : owner.equals(branch) ? "C" : "A";
            var connection = ChainConveyorRidingHandler.ridingConnection;
            var target = client.target;
            var velocity = client.player.velocity;
            System.out.printf(Locale.ROOT,
                "CREATE_CHAIN_RIDE %s,%d,%.2f,%.2f,%s,%s,%.9f,%d,%b,%d,%d,%s,%s,%s,%s%n",
                scenario, tick, a.getSpeed(), client.serverSpeed, wheel,
                connection == null ? "-" : connection.getX() + ":" + connection.getY() + ":" + connection.getZ(),
                ChainConveyorRidingHandler.chainPosition, ChainConveyorRidingHandler.catchingUp,
                ChainConveyorRidingHandler.flipped, client.keepalives, client.stops,
                vector(feet), vector(prior), vector(target), vector(velocity));
        }
    }

    private static String vector(Vec3 value) {
        return value == null ? "-,-,-" : String.format(Locale.ROOT, "%.9f,%.9f,%.9f", value.x, value.y, value.z);
    }

    private static void captureAuthority(String scenario, int limit) {
        var player = new java.util.UUID(0, 1);
        ServerChainConveyorHandler.hangingPlayers.clear();
        ServerChainConveyorHandler.ticks = 0;
        ServerChainConveyorHandler.probeSyncs = 0;
        for (int tick = 1; tick <= limit; tick++) {
            ServerChainConveyorHandler.tick();
            String action = "-";
            if (tick == 1 || (scenario.equals("expiry") && (tick == 11 || tick == 21))) {
                ServerChainConveyorHandler.handleTTLPacket(player);
                action = "keepalive";
            } else if (scenario.equals("stop") && tick == 12) {
                ServerChainConveyorHandler.handleStopRidingPacket(player);
                action = "stop";
            }
            System.out.printf(Locale.ROOT, "CREATE_CHAIN_RIDE_AUTHORITY %s,%d,%s,%d,%d%n",
                scenario, tick, action, ServerChainConveyorHandler.hangingPlayers.getInt(player),
                ServerChainConveyorHandler.probeSyncs);
        }
    }

    public static void main(String[] args) {
        net.neoforged.fml.loading.LoadingModList.of(List.of(), List.of(), List.of(), List.of(), java.util.Map.of());
        net.neoforged.fml.ModList.of(List.of(), List.of());
        SharedConstants.tryDetectVersion();
        Bootstrap.bootStrap();
        captureAuthority("expiry", 42);
        captureAuthority("stop", 15);
        var straight = new BlockPos(7, 0, 0);
        var rising = new BlockPos(6, 2, 3);
        capture("straight", straight, null, 40, 32);
        capture("rising_reversal", rising, rising, 2, 40);
        capture("rising_power_pause", rising, rising, 2, 28);
        capture("junction", straight, null, 315, 20);
        capture("disconnect", straight, straight, 1, 5);
        capture("release_tool", straight, null, 40, 4);
        capture("catchup_timeout", straight, null, 40, 20);
    }
}
