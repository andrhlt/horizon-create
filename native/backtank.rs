use horizon_core::position::BlockPos;
use horizon_world::{
    fluid::{FluidKind, FluidState},
    level::PlacementContext,
    nbt::Tag,
    registry::BlockStateId,
};

use crate::{
    containers::{BlockEntity, ModBlockEntity},
    items::ItemStack,
    save::item_to_nbt,
};

use super::{
    Game, GameLevel,
    create_machines::{int, mod_entity},
};

pub(super) const TANK: &str = "create:copper_backtank";
pub(super) const NETHERITE_TANK: &str = "create:netherite_backtank";
pub(super) const ENTITY: &str = "create:backtank";
pub(super) const AIR: &str = "create:banktank_air";
const CAPACITY_ENCHANTMENT: &str = "create:capacity";
const MAX_BASE: i32 = 900;
const EXTRA_CAPACITY: i32 = 300;

pub(super) fn block(id: &str) -> bool {
    matches!(id, TANK | NETHERITE_TANK)
}

pub(super) fn has_diving_air(armor: &[Option<ItemStack>; 4]) -> bool {
    let helmet = armor[0].as_ref().map(|stack| stack.item.as_ref());
    let Some(tank) = armor[1].as_ref().filter(|tank| block(&tank.item)) else {
        return false;
    };
    matches!(
        helmet,
        Some("create:copper_diving_helmet" | "create:netherite_diving_helmet")
    ) && matches!(tank.data().and_then(|data| data.other(AIR)), Some(Tag::Int(air)) if *air > 0)
}

pub(super) fn breathe_player(
    armor: &mut [Option<ItemStack>; 4],
    breath: &mut crate::breathing::Breath,
    in_lava: bool,
    charge_due: bool,
) -> bool {
    if breath.can_breathe || in_lava || !has_diving_air(armor) {
        return false;
    }
    breath.can_breathe = true;
    breath.refill = 300;
    if !charge_due {
        return false;
    }
    let Some(tank) = armor[1].as_mut() else {
        return false;
    };
    let Some(Tag::Int(air)) = tank.data().and_then(|data| data.other(AIR)) else {
        return false;
    };
    let capacity = MAX_BASE + EXTRA_CAPACITY * tank.enchantment_level(CAPACITY_ENCHANTMENT) as i32;
    let remaining = (*air).min(capacity) - 1;
    tank.data_mut().set_other(AIR, Some(Tag::Int(remaining)));
    true
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
    fluid: FluidState,
) -> Option<BlockStateId> {
    if !level.native_state_block(state).is_some_and(block) {
        return None;
    }
    let yaw = ((f64::from(context.yaw) / 90.0 + 0.5).floor() as i32).rem_euclid(4) as usize;
    let facing = ["north", "east", "south", "west"][yaw];
    let state = level.native_state_with_property(state, "facing", facing)?;
    let wet = fluid.kind() == FluidKind::Water && fluid.is_source();
    level.native_state_with_property(state, "waterlogged", if wet { "true" } else { "false" })
}

fn capacity(entity: &ModBlockEntity) -> i32 {
    let enchantment = int(&entity.nbt, "CapacityEnchantment").unwrap_or(0).max(0);
    MAX_BASE + EXTRA_CAPACITY * enchantment
}

fn signal(air: i32, max: i32) -> i32 {
    let fraction = f64::from(air as f32 / max as f32);
    (fraction * 14.0 + if fraction > 0.0 { 1.0 } else { 0.0 })
        .clamp(0.0, 15.0)
        .floor() as i32
}

pub(super) fn output(level: &GameLevel<'_>, pos: BlockPos, state: BlockStateId, result: &mut i32) {
    if level.native_state_block(state).is_some_and(block)
        && let Some(BlockEntity::Mod(entity)) =
            level.world.block_entities.get(&(pos.x, pos.y, pos.z))
    {
        *result = signal(int(&entity.nbt, "Air").unwrap_or(0), capacity(entity));
    }
}

pub(super) fn placed(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) {
    if !block(&game.native_block(pos)) {
        return;
    }
    let level = stack.enchantment_level(CAPACITY_ENCHANTMENT);
    let air = match game.native_component(stack, AIR) {
        Ok(Some(Tag::Int(value))) => *value,
        _ => 0,
    };
    let saved = item_to_nbt(stack);
    game.native_with_mod_block_entity(pos, |entity| {
        entity.nbt.insert("Air".into(), Tag::Int(air));
        entity
            .nbt
            .insert("CapacityEnchantment".into(), Tag::Int(level as i32));
        entity.nbt.insert("TankItem".into(), saved);
    });
    game.native_block_entity_sync(pos);
}

pub(super) fn packed(game: &Game<'_>, pos: [i32; 3]) -> Option<ItemStack> {
    let id = game.native_block(pos);
    if !block(&id) {
        return None;
    }
    let entity = mod_entity(game, pos)?;
    let mut stack = match entity.nbt.get(&"TankItem".into()) {
        Some(Tag::Compound(item)) => ItemStack::from_nbt(item),
        _ => None,
    }
    .unwrap_or_else(|| ItemStack::new(id.as_str(), 1));
    stack.item = id.into();
    stack.count = 1;
    game.native_set_component(
        &mut stack,
        AIR,
        Tag::Int(int(&entity.nbt, "Air").unwrap_or(0)),
    )
    .ok()?;
    Some(stack)
}

pub(super) fn equip(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if !game.native_authoritative() || game.native_sneaking() || game.armor[1].is_some() {
        return false;
    }
    if game.stack_in(game.selected).is_some_and(|stack| {
        !block(stack.item.as_ref())
            && game
                .items()
                .get(&stack.item)
                .is_some_and(|info| info.block.is_some())
    }) {
        return false;
    }
    let Some(stack) = packed(game, pos) else {
        return false;
    };
    let at = BlockPos::new(pos[0], pos[1], pos[2]);
    if !game.with_level(|behaviour, level, ticks| behaviour.destroy_block(level, ticks, at, false))
    {
        return false;
    }
    game.armor[1] = Some(stack);
    game.apply_equipment();
    game.guest_inventory_resend |= game.lan_acting.is_some();
    game.native_play_sound_in_place(
        "minecraft:entity.item.pickup",
        pos.map(|v| f64::from(v) + 0.5),
        7,
        0.75,
        1.0,
    );
    game.swing_arm();
    true
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity, rpm: f32) {
    if rpm == 0.0 || game.native_block_property(pos, "waterlogged").as_deref() == Some("true") {
        return;
    }
    let timer = int(&entity.nbt, "Timer").unwrap_or(0);
    if timer > 0 {
        entity.nbt.insert("Timer".into(), Tag::Int(timer - 1));
        return;
    }
    let air = int(&entity.nbt, "Air").unwrap_or(0);
    let max = capacity(entity);
    if air >= max {
        return;
    }
    let speed = rpm.abs();
    let increment = ((speed as i32 - 100) / 20).clamp(1, 5);
    let charged = (air + increment).min(max);
    let timer = ((128.0 - speed / 5.0) as i32 - 108).clamp(0, 20);
    entity.nbt.insert("Air".into(), Tag::Int(charged));
    entity.nbt.insert("Timer".into(), Tag::Int(timer));
    if signal(air, max) != signal(charged, max) {
        game.native_update_output_neighbors(game.native_dimension(), pos);
    }
    if charged == max {
        game.native_block_entity_sync(pos);
    }
}
