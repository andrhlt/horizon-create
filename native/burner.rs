use horizon_core::geometry::Direction;
use horizon_core::position::BlockPos;
use horizon_world::level::{LevelAccess, flags};
use horizon_world::nbt::Tag;

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_machines::{int, mod_entity, offset};

pub(super) const BURNER: &str = "create:blaze_burner";
pub(super) const LIT_BURNER: &str = "create:lit_blaze_burner";
pub(super) const HEATER: &str = "create:blaze_heater";
const EMPTY: &str = "create:empty_blaze_burner";
const CAKE: &str = "create:blaze_cake";
const CREATIVE_CAKE: &str = "create:creative_blaze_cake";
const MAX_HEAT: i32 = 10_000;
const REFUEL_THRESHOLD: i32 = 500;

fn heat(kind: i32, remaining: i32) -> &'static str {
    match kind {
        2 => "seething",
        1 if remaining >= 125 => "kindled",
        1 => "fading",
        _ => "smouldering",
    }
}

fn apply_heat(game: &mut Game<'_>, pos: [i32; 3], next: &str) {
    if game.native_block_property(pos, "blaze").as_deref() != Some(next) {
        game.native_set_block_property_with(pos, "blaze", next, flags::UPDATE_ALL);
    }
}

fn write_fuel(entity: &mut ModBlockEntity, kind: i32, time: i32) {
    entity.nbt.insert("fuelLevel".into(), Tag::Int(kind));
    entity
        .nbt
        .insert("burnTimeRemaining".into(), Tag::Int(time));
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    if int(&entity.nbt, "isCreative") == Some(1)
        || game.native_block_property(pos, "blaze").as_deref() == Some("none")
    {
        return;
    }
    let mut kind = int(&entity.nbt, "fuelLevel").unwrap_or(0);
    let remaining = int(&entity.nbt, "burnTimeRemaining").unwrap_or(0);
    let mut time = remaining.saturating_sub(1).max(0);
    if time == 0 {
        if kind == 2 {
            kind = 1;
            time = MAX_HEAT / 2;
        } else {
            kind = 0;
        }
    }
    if kind != 0 || remaining != 0 {
        write_fuel(entity, kind, time);
    }
    apply_heat(game, pos, heat(kind, time));
}

fn return_item(game: &mut Game<'_>, pos: [i32; 3], stack: ItemStack) {
    if game.held().is_none() {
        *game.held_mut() = Some(stack);
    } else if let Some(left) = game.give(stack) {
        let center = pos.map(|value| f64::from(value) + 0.5);
        game.add_item_entity(left, center, None, 10);
    }
}

pub(super) fn capture(
    game: &mut Game<'_>,
    entity: i32,
    kind: &str,
    stack: Option<&ItemStack>,
) -> bool {
    if kind != "minecraft:blaze"
        || !stack.is_some_and(|stack| stack.item.as_ref() == EMPTY)
        || !game.native_remove_mob(game.native_dimension(), entity as u32)
    {
        return false;
    }
    game.consume_held();
    let at = game.player.as_ref().map_or([0; 3], |player| {
        [player.position.x, player.position.y, player.position.z].map(|value| value.floor() as i32)
    });
    return_item(game, at, ItemStack::new(BURNER, 1));
    true
}

fn place_empty(game: &mut Game<'_>, clicked: [i32; 3], normal: [i32; 3]) -> bool {
    let pos = offset(clicked, normal);
    let facing =
        ["north", "east", "south", "west"][(game.yaw / 90.0).round().rem_euclid(4.0) as usize];
    let state = game.with_level(|_, level, _| {
        let mut state = level
            .registry
            .state(level.registry.default_state(BURNER)?)?
            .clone();
        if level
            .registry
            .state(level.world.block(pos[0], pos[1], pos[2]))?
            .name
            != "minecraft:air"
        {
            return None;
        }
        state.properties.insert("blaze".into(), "none".into());
        state.properties.insert("facing".into(), facing.into());
        let state = level.registry.id(&state)?;
        level
            .is_unobstructed(BlockPos::new(pos[0], pos[1], pos[2]), state)
            .then_some(state)
    });
    if state.is_some_and(|state| {
        game.native_set_block(game.native_dimension(), pos, state, flags::UPDATE_ALL)
    }) {
        game.consume_held();
        true
    } else {
        false
    }
}

fn fuel_offer(
    game: &Game<'_>,
    entity: &ModBlockEntity,
    stack: &ItemStack,
    force_overflow: bool,
) -> Option<(i32, i32)> {
    if int(&entity.nbt, "isCreative") == Some(1) {
        return None;
    }
    let active = int(&entity.nbt, "fuelLevel").unwrap_or(0);
    let remaining = int(&entity.nbt, "burnTimeRemaining").unwrap_or(0);
    let (kind, mut time) = if stack.item.as_ref() == CAKE {
        (2, 3200)
    } else {
        let duration = game
            .res
            .providers()
            .burn_time(game.res.items(), stack, false);
        (1, duration)
    };
    if time <= 0 || kind < active {
        return None;
    }
    if kind == active {
        if remaining <= REFUEL_THRESHOLD {
            time += remaining;
        } else if force_overflow && kind == 1 {
            time = remaining.max((remaining + time).min(MAX_HEAT));
        } else {
            return None;
        }
    }
    Some((kind, time))
}

fn accept_fuel(game: &mut Game<'_>, pos: [i32; 3], kind: i32, time: i32) {
    game.native_with_mod_block_entity(pos, |burner| write_fuel(burner, kind, time));
    apply_heat(game, pos, heat(kind, time));
}

fn arm_offer(game: &Game<'_>, pos: [i32; 3], stack: &ItemStack) -> Option<(i32, i32)> {
    if game.native_block_property(pos, "blaze").as_deref() == Some("none") {
        return None;
    }
    fuel_offer(game, mod_entity(game, pos)?, stack, false)
}

pub(super) fn accepts_from_arm(game: &Game<'_>, pos: [i32; 3], stack: &ItemStack) -> bool {
    arm_offer(game, pos, stack).is_some()
}

pub(super) fn feed_from_arm(
    game: &mut Game<'_>,
    pos: [i32; 3],
    mut stack: ItemStack,
) -> Option<ItemStack> {
    let Some((kind, time)) = arm_offer(game, pos, &stack) else {
        return Some(stack);
    };
    accept_fuel(game, pos, kind, time);
    stack.count -= 1;
    let remainder = game
        .res
        .items()
        .get(&stack.item)
        .and_then(|item| item.crafting_remainder.as_deref())
        .map(|item| ItemStack::new(item, 1));
    if stack.count == 0 {
        return remainder;
    }
    if let Some(remainder) = remainder {
        let center = pos.map(|value| f64::from(value) + 0.5);
        game.add_item_entity(remainder, center, None, 10);
    }
    Some(stack)
}

pub(super) fn use_item(
    game: &mut Game<'_>,
    pos: [i32; 3],
    normal: [i32; 3],
    stack: &ItemStack,
) -> bool {
    if game.native_block(pos) == LIT_BURNER {
        let item = stack.item.as_ref();
        if matches!(item, "minecraft:wooden_shovel" | "minecraft:stone_shovel" | "minecraft:iron_shovel" | "minecraft:golden_shovel" | "minecraft:diamond_shovel" | "minecraft:netherite_shovel") {
            let state = game.with_level(|_, level, _| {
                let mut state = level.registry.state(level.registry.default_state(BURNER)?)?.clone();
                state.properties.insert("blaze".into(), "none".into());
                level.registry.id(&state)
            });
            if state.is_some_and(|state| game.native_set_block(game.native_dimension(), pos, state, flags::UPDATE_ALL)) {
                game.damage_held(1);
                return true;
            }
        } else if matches!(item, "minecraft:soul_sand" | "minecraft:soul_soil")
            && game.native_block_property(pos, "flame_type").as_deref() == Some("regular")
        {
            game.native_set_block_property_with(pos, "flame_type", "soul", flags::UPDATE_ALL);
            game.guest_inventory_resend = true;
            return true;
        }
        return false;
    }
    if stack.item.as_ref() == EMPTY {
        return place_empty(game, pos, normal);
    }
    if game.native_block(pos) != BURNER {
        return false;
    }
    let Some(current) = game.native_block_property(pos, "blaze") else {
        return false;
    };
    if current == "none" {
        if stack.item.as_ref() == "minecraft:flint_and_steel"
            && let Some(state) = game.native_default_state(LIT_BURNER)
            && game.native_set_block(game.native_dimension(), pos, state, flags::UPDATE_ALL)
        {
            game.damage_held(1);
            return true;
        }
        return false;
    }
    let Some(entity) = mod_entity(game, pos) else {
        return false;
    };
    if stack.item.as_ref() == CREATIVE_CAKE {
        let next = match current.as_str() {
            "smouldering" | "fading" => "kindled",
            "kindled" => "seething",
            _ => "smouldering",
        };
        game.native_with_mod_block_entity(pos, |burner| {
            burner.nbt.insert("isCreative".into(), Tag::Byte(1));
            write_fuel(burner, 0, 0);
        });
        apply_heat(game, pos, next);
        return true;
    }
    let Some((kind, time)) = fuel_offer(game, entity, stack, true) else {
        return false;
    };
    let remainder = game
        .res
        .items()
        .get(&stack.item)
        .and_then(|item| item.crafting_remainder.as_ref())
        .cloned();
    accept_fuel(game, pos, kind, time);
    if !game.creative {
        game.consume_held();
        if let Some(item) = remainder {
            return_item(game, pos, ItemStack::new(&item, 1));
        }
    }
    true
}
