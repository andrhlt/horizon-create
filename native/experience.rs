use horizon_core::{
    geometry::{Vec3, trig},
    random::RandomSource,
};

use crate::{entities::ExperienceOrb, items::ItemStack};

use super::Game;

const NUGGET: &str = "create:experience_nugget";

fn tracing() -> bool {
    static ENABLED: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *ENABLED.get_or_init(|| std::env::var("CREATE_EXPERIENCE_TRACE").is_ok_and(|v| v == "1"))
}

fn java_sin_cos(radians: f32) -> (f64, f64) {
    let index = radians * 10_430.378_f32;
    let sine = trig::sine_table();
    (
        f64::from(sine[(index as i32 & 65535) as usize]),
        f64::from(sine[((index + 16_384.0) as i32 & 65535) as usize]),
    )
}

pub(super) fn release(game: &mut Game<'_>, stack: &ItemStack, claimed: &mut bool) {
    if *claimed || stack.item.as_ref() != NUGGET || !game.native_authoritative() {
        return;
    }
    let Some(player) = game.native_acting_player() else {
        return;
    };
    let held = game.held_mut();
    let Some(nuggets) = held
        .as_mut()
        .filter(|held| held.item == stack.item && held.count > 0)
    else {
        return;
    };
    let original = nuggets.count;
    let amount = if player.sneaking { 1 } else { original };
    nuggets.count -= amount;
    let remaining = nuggets.count;
    if remaining == 0 {
        *held = None;
    }

    let (sin_yaw, cos_yaw) = java_sin_cos(-player.yaw * trig::DEG_TO_RAD);
    let (sin_pitch, cos_pitch) = java_sin_cos(player.pitch * trig::DEG_TO_RAD);
    let look = Vec3::new(
        f64::from(sin_yaw as f32 * cos_pitch as f32),
        -sin_pitch,
        f64::from(cos_yaw as f32 * cos_pitch as f32),
    );
    let side_angle = (f64::from(-player.yaw) / 180.0 * std::f64::consts::PI) as f32;
    let (side_sine, side_cosine) = java_sin_cos(side_angle);
    let side = Vec3::new(-0.75 * side_cosine, 0.0, 0.75 * side_sine);
    let [x, y, z] = player.position;
    let eye = Vec3::new(x, y + f64::from(player.eye_height), z);
    let origin = eye.add_vector(look.scale(0.5)).add_vector(look.cross(side));
    let forward = look.scale(0.2).add_vector(Vec3::new(0.0, 0.2, 0.0));

    let total = (amount * 3) as i32;
    let orbs = if amount == 1 { 1 } else { 5 };
    let per_orb = 1 + total / orbs;
    let mut emitted = 0;
    let trace = tracing();
    for index in 0..orbs {
        // Java skips zero but preserves negative trailing values for small stacks.
        let value = per_orb.min(total - index * per_orb);
        if value == 0 {
            continue;
        }
        let rng = &mut game.world.random;
        let offset = Vec3::new(
            f64::from((rng.next_float() - 0.5) * 2.0),
            f64::from((rng.next_float() - 0.5) * 2.0),
            f64::from((rng.next_float() - 0.5) * 2.0),
        );
        let velocity = forward.add_vector(offset.normalize().scale(0.1));
        game.next_entity += 1;
        let orb = ExperienceOrb::new(game.next_entity, origin, velocity, value);
        if trace {
            let [dx, dy, dz] = Vec3::new(x, y, z).vector_to(orb.position).components();
            let [vx, vy, vz] = orb.velocity.components();
            eprintln!(
                "CREATE_EXPERIENCE_RELEASE {},{original},{remaining},{emitted},{},{},{dx:.12},{dy:.12},{dz:.12},{vx:.12},{vy:.12},{vz:.12}",
                player.sneaking, orb.value, orb.count
            );
            emitted += 1;
        }
        game.orbs.push(orb);
        game.native_joins_flush(false, 0);
    }
    game.native_play_sound_to(
        player.uuid,
        "minecraft:block.amethyst_block.break",
        "player",
        Some([x.floor() + 0.5, y.floor() + 0.5, z.floor() + 0.5]),
        0.5,
        1.0,
    );
    game.guest_inventory_resend |= game.lan_acting.is_some();
    *claimed = true;
}
