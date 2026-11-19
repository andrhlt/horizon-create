use std::sync::OnceLock;

use horizon_world::consumable::UseAnimation;

use crate::items::ItemStack;

use super::{Game, create_package_style::dimensions, create_package_world, pick_view_vector};

const USE_TICKS: i32 = 72_000;

fn is_package(stack: &ItemStack) -> bool {
    dimensions(&stack.item).is_some()
}

pub(super) fn duration(stack: &ItemStack, duration: &mut i32) {
    if is_package(stack) {
        *duration = USE_TICKS;
    }
}

pub(super) fn animation(stack: &ItemStack, animation: &mut UseAnimation) {
    if is_package(stack) {
        *animation = UseAnimation::Bow;
    }
}

fn charge_speed(held_ticks: i32) -> Option<f64> {
    let charge = held_ticks as f32 / 20.0;
    let strength = ((charge * charge + charge * 2.0) / 3.0).min(1.0);
    (held_ticks >= 0 && f64::from(strength) >= 0.1).then(|| f64::from(strength * 2.0))
}

pub(super) fn release(game: &mut Game<'_>, stack: &ItemStack, remaining: i32, used: &mut bool) {
    if *used || !game.native_authoritative() || !is_package(stack) {
        return;
    }
    let charge = USE_TICKS - remaining;
    trace_charge("release", charge);
    let Some(speed) = charge_speed(charge) else {
        return;
    };
    let Some(player) = game.player.as_ref() else {
        return;
    };
    let feet = player.position.components();
    let midpoint = [
        feet[0],
        feet[1] + f64::from(player.dimensions.height) / 2.0,
        feet[2],
    ];
    let velocity = pick_view_vector(player.yaw, player.pitch).map(|axis| axis * speed);
    let position = std::array::from_fn(|axis| midpoint[axis] + velocity[axis]);
    let owner = game.native_acting_id();
    if create_package_world::spawn(game, stack, position, velocity, Some(owner)).is_none() {
        return;
    }

    if !game.creative
        && let Some(held) = game.held_mut().as_mut()
    {
        held.count -= 1;
        if held.count == 0 {
            *game.held_mut() = None;
        }
    }
    game.native_play_sound_in_place(
        "minecraft:entity.snowball.throw",
        feet,
        horizon_client::sound_engine::NEUTRAL,
        0.5,
        0.5,
    );
    *used = true;
}

pub(super) fn tick(game: &Game<'_>, stack: &ItemStack, remaining: i32) {
    if game.native_authoritative() && is_package(stack) {
        trace_charge("tick", USE_TICKS - remaining);
    }
}

fn trace_charge(event: &str, ticks: i32) {
    static TRACE: OnceLock<bool> = OnceLock::new();
    if *TRACE.get_or_init(|| std::env::var_os("HORIZON_CREATE_PACKAGE_TRACE").is_some()) {
        eprintln!("CREATE_PACKAGE_CHARGE {event},{ticks}");
    }
}
