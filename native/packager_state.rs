use horizon_world::nbt::{Compound, Tag};

use crate::items::ItemStack;

use super::create_depot::{compound, encode};
use super::create_machines::int;

const ANIMATION_LENGTH: i32 = 20;
const BUTTON_COOLDOWN: i32 = 40;
pub(super) const LAZY_TICK_RATE: i32 = 10;

pub(super) fn initialize() -> Compound {
    let mut state = Compound::new();
    state.insert("AnimationInward".into(), Tag::Byte(1));
    state
}

// The rising edge sets Active before attempting to move any cargo. Call
// finish_activation after that attempt, since it reads the previous cooldown.
pub(super) fn activate(state: &mut Compound) {
    state.insert("Active".into(), Tag::Byte(1));
}

pub(super) fn finish_activation(state: &mut Compound) {
    if cooldown(state) <= 0 {
        state.insert("ButtonCooldown".into(), Tag::Int(BUTTON_COOLDOWN));
    }
}

pub(super) fn may_send(state: &Compound) -> bool {
    animation(state) == 0 && cooldown(state) == 0 && held(state).is_none()
}

pub(super) fn held(state: &Compound) -> Option<ItemStack> {
    compound(state, "HeldBox").and_then(ItemStack::from_nbt)
}

pub(super) fn comparator(state: &Compound) -> i32 {
    if animation(state) > 0 || held(state).is_some() {
        15
    } else {
        0
    }
}

pub(super) fn start_animation(state: &mut Compound, package: &ItemStack, inward: bool) {
    let key = if inward { "InsertedBox" } else { "HeldBox" };
    state.insert(key.into(), encode(package));
    state.insert("AnimationInward".into(), Tag::Byte(i8::from(inward)));
    state.insert("AnimationTicks".into(), Tag::Int(ANIMATION_LENGTH));
}

// The lazy callback runs before animation/cooldown decrement. Its return
// controls a possible retry while a redstone signal remains present.
pub(super) fn lazy_update(state: &mut Compound, phase: &mut i32, powered: bool) -> bool {
    *phase -= 1;
    if *phase >= 0 {
        return false;
    }
    *phase = LAZY_TICK_RATE;
    if int(state, "Active").unwrap_or_default() == 0 {
        return false;
    }
    state.insert("Active".into(), Tag::Byte(i8::from(powered)));
    may_send(state)
}

pub(super) fn tick_animation(state: &mut Compound) {
    let cooldown = cooldown(state);
    if cooldown > 0 {
        state.insert("ButtonCooldown".into(), Tag::Int(cooldown - 1));
    }
    let animation = animation(state);
    if animation > 0 {
        state.insert("AnimationTicks".into(), Tag::Int(animation - 1));
    } else {
        state.remove(&"InsertedBox".into());
    }
}

pub(super) fn animation(state: &Compound) -> i32 {
    int(state, "AnimationTicks").unwrap_or_default()
}

fn cooldown(state: &Compound) -> i32 {
    int(state, "ButtonCooldown").unwrap_or_default()
}
