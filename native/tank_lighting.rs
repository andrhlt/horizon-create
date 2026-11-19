use crate::containers::BlockEntity;
use horizon_core::position::BlockPos;
use horizon_world::nbt::Tag;
use horizon_world::registry::BlockStateId;
use super::GameLevel;
use super::create_depot::compound;
use super::create_fluids::read_fluid;
use super::create_fluid_tank::{TANK, CREATIVE};
use super::create_machines::int;

pub(super) fn has_output(level: &GameLevel<'_>, state: BlockStateId, output: &mut bool) {
    *output |= matches!(level.native_state_block(state), Some(TANK | CREATIVE));
}

pub(super) fn output(level: &GameLevel<'_>, pos: BlockPos, state: BlockStateId, output: &mut i32) {
    if !matches!(level.native_state_block(state), Some(TANK | CREATIVE)) { return; }
    let at = [pos.x, pos.y, pos.z];
    let entity = |p: [i32; 3]| match level.world.block_entities.get(&(p[0], p[1], p[2])) {
        Some(BlockEntity::Mod(entity)) => Some(entity),
        _ => None,
    };
    let Some(part) = entity(at) else { return };
    let root = super::create_fluid_tank::stored_controller(part, at).unwrap_or(at);
    let Some(controller) = entity(root) else { return };
    let width = int(&controller.nbt, "Size").unwrap_or(1);
    let height = int(&controller.nbt, "Height").unwrap_or(1);
    let capacity = super::create_fluid_tank::retained_capacity(controller, 8000 * width * width * height);
    let amount = compound(&controller.nbt, "TankContent")
        .and_then(|tank| read_fluid(compound(tank, "Fluid")?)).map_or(0, |fluid| fluid.amount);
    let amount = if controller.id == CREATIVE && amount > 0 { capacity } else { amount };
    *output = if amount > 0 && capacity > 0 {
        ((amount as f32 / capacity as f32) as f64 * 14.0 + 1.0).clamp(0.0, 15.0).floor() as i32
    } else { 0 };
}

// Java divides lava's emission (15) by 1.2 and lights the filled layers;
// unfilled layers of a luminous tank retain emission 1.
pub(super) fn sync(game: &mut super::Game<'_>, root: [i32; 3], width: usize,
                   parts: &[[i32; 3]], entity: &crate::containers::ModBlockEntity) {
    let height = parts.len() / (width * width);
    if height == 0 { return; }
    let window = !matches!(entity.nbt.get(&"Window".into()), Some(Tag::Byte(0)));
    let fluid = compound(&entity.nbt, "TankContent")
        .and_then(|tank| read_fluid(compound(tank, "Fluid")?));
    let amount = fluid.as_ref().map_or(0, |f| f.amount);
    let luminous = fluid.as_ref().is_some_and(|f| f.id == "minecraft:lava" && f.amount > 0);
    let capacity = super::create_fluid_tank::retained_capacity(entity, (8000 * parts.len()) as i32);
    let amount = if entity.id == CREATIVE && amount > 0 { capacity } else { amount };
    let max_y = (amount as f32 / capacity.max(1) as f32 * height as f32 + 1.0) as i32;
    for &pos in parts {
        let light = if !window || !luminous { 0 } else if pos[1] - root[1] < max_y { 12 } else { 1 };
        game.native_set_dynamic_emission(pos, Some(light));
    }
}

// Split hooks run at the level seam, before a Game is available to relight.
pub(super) fn sync_singleton_level(level: &mut GameLevel<'_>, pos: [i32; 3]) {
    let key = (pos[0], pos[1], pos[2]);
    let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get(&key) else { return };
    let window = !matches!(entity.nbt.get(&"Window".into()), Some(Tag::Byte(0)));
    let luminous = compound(&entity.nbt, "TankContent")
        .and_then(|tank| read_fluid(compound(tank, "Fluid")?))
        .is_some_and(|fluid| fluid.id == "minecraft:lava" && fluid.amount > 0);
    let light = if window && luminous { 12 } else { 0 };
    let Some(chunk) = level.world.chunks.get_mut(&(pos[0] >> 4, pos[2] >> 4)) else { return };
    let chunk = std::sync::Arc::make_mut(chunk);
    if chunk.dynamic_emission.get(&key).copied() == Some(light) { return; }
    chunk.dynamic_emission.insert(key, light);
    level.world.light_edits.push((key, u32::MAX, 0));
}
