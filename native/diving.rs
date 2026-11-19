use horizon_world::nbt::Tag;

use super::{Mob, MobWorld, gear};

const BOOTS: &str = "create:netherite_diving_boots";
const HELMET: &str = "create:netherite_diving_helmet";
const BACKTANK: &str = "create:netherite_backtank";
const AIR: &str = "create:banktank_air";

fn air(stack: &crate::items::ItemStack) -> i32 {
    match stack.data().and_then(|data| data.other(AIR)) {
        Some(Tag::Int(air)) => *air,
        _ => 0,
    }
}

fn tank(mob: &Mob) -> Option<&crate::items::ItemStack> {
    let stack = gear::gear(mob)?.stacks[gear::CHEST].as_ref()?;
    (mob.extra.chest.as_deref() == Some(BACKTANK) && stack.item.as_ref() == BACKTANK)
        .then_some(stack)
}

pub(super) fn fire_immune(mob: &Mob) -> bool {
    !mob.first_tick
        && mob.extra.head.as_deref() == Some(HELMET)
        && tank(mob).is_some_and(|stack| air(stack) > 0)
        && mob.extra.legs.as_deref() == Some("minecraft:netherite_leggings")
        && matches!(
            mob.extra.feet.as_deref(),
            Some(BOOTS | "minecraft:netherite_boots")
        )
}

pub(super) fn breathe(mob: &mut Mob, world: &MobWorld<'_>) {
    if !mob.fluids.in_lava
        || world.game_time.rem_euclid(20) != 0
        || mob.extra.head.as_deref() != Some(HELMET)
    {
        return;
    }
    if let Some(remaining) = tank(mob).map(air).filter(|amount| *amount > 0) {
        let gear = mob.extra.gear.as_mut().expect("the tank has stored air");
        let stack = gear.stacks[gear::CHEST]
            .as_mut()
            .expect("the tank was just read");
        stack
            .data_mut()
            .set_other(AIR, Some(Tag::Int(remaining - 1)));
    }
}

pub(super) fn breathe_underwater(
    mob: &mut Mob,
    world: &MobWorld<'_>,
    breath: &mut crate::breathing::Breath,
) {
    if breath.can_breathe
        || mob.fluids.in_lava
        || !matches!(
            mob.extra.head.as_deref(),
            Some(HELMET | "create:copper_diving_helmet")
        )
    {
        return;
    }
    let Some(stack) = mob
        .extra
        .gear
        .as_mut()
        .and_then(|gear| gear.stacks[gear::CHEST].as_mut())
    else {
        return;
    };
    if !matches!(stack.item.as_ref(), BACKTANK | "create:copper_backtank") {
        return;
    }
    let remaining = air(stack);
    if remaining <= 0 {
        return;
    }
    if world.game_time.rem_euclid(20) == 0 {
        let capacity = 900 + 300 * stack.enchantment_level("create:capacity") as i32;
        stack
            .data_mut()
            .set_other(AIR, Some(Tag::Int(remaining.min(capacity) - 1)));
    }
    breath.can_breathe = true;
    breath.refill = mob.max_air_supply();
}

pub(super) fn lava_movement(mob: &mut Mob, _world: &MobWorld<'_>) {
    if mob.extra.feet.as_deref() != Some(BOOTS) {
        return;
    }
    let y = mob.velocity.y;
    let vertical = if y < 0.0 {
        (2.5 - y.abs() * 2.0).max(0.0)
    } else if !mob.on_ground && y > 0.0 {
        1.3
    } else {
        1.0
    };
    let horizontal = if mob.on_ground && mob.extra.sprinting {
        1.85
    } else {
        1.75
    };
    mob.velocity.x *= horizontal;
    mob.velocity.y *= vertical;
    mob.velocity.z *= horizontal;
}
