use horizon_core::position::BlockPos;
use horizon_world::nbt::Tag;
use horizon_world::registry::BlockStateId;

use crate::containers::{BlockEntity, ModBlockEntity};
use crate::items::ItemStack;

use super::create_machines::int;
use super::{Game, GameLevel};

pub(super) const VAULT: &str = "create:item_vault";
pub(super) const SLOTS: usize = 20;

pub(super) fn parts(
    world: &crate::game::World,
    registry: &horizon_world::registry::BlockRegistry,
    pos: [i32; 3],
) -> Option<(usize, Vec<[i32; 3]>)> {
    super::create_multiblock::parts(
        pos,
        |at| {
            let state = registry.state(world.block(at[0], at[1], at[2]))?;
            if state.name != VAULT {
                return None;
            }
            state.properties.get("axis")?.chars().next()
        },
        |size| size * 3,
    )
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    if let Some(Tag::Compound(inventory)) = entity.nbt.remove(&"Inventory".into())
        && let Some(Tag::List(legacy)) = inventory.get(&"Items".into())
    {
        entity.items.resize(SLOTS, None);
        for item in legacy.iter() {
            let Tag::Compound(item) = item else { continue };
            let slot = int(item, "Slot").unwrap_or(-1);
            if let Some(target) = entity.items.get_mut(slot as usize)
                && target.is_none()
            {
                *target = ItemStack::from_nbt(item);
            }
        }
    }

    if let Some((size, _)) = parts(&game.world, &game.pack.assets.registry, pos) {
        let visual = if size == 3 { "true" } else { "false" };
        if game.native_block_property(pos, "large").as_deref() != Some(visual) {
            game.native_set_block_property_with(pos, "large", visual, 2);
        }
    }
}

pub(super) fn has_output(level: &GameLevel<'_>, state: BlockStateId, output: &mut bool) {
    *output |= level
        .registry
        .state(state)
        .is_some_and(|block| block.name == VAULT);
}

pub(super) fn output(level: &GameLevel<'_>, pos: BlockPos, state: BlockStateId, output: &mut i32) {
    if level
        .registry
        .state(state)
        .is_none_or(|block| block.name != VAULT)
    {
        return;
    }
    let Some((_, parts)) = parts(level.world, level.registry, [pos.x, pos.y, pos.z]) else {
        return;
    };
    let capacity = parts.len() * SLOTS;
    let mut displayed = 0.0_f32;
    for [x, y, z] in parts {
        let Some(BlockEntity::Mod(part)) = level.world.block_entities.get(&(x, y, z)) else {
            continue;
        };
        for stack in part.items.iter().take(SLOTS).flatten() {
            let max = level
                .items
                .get(&stack.item)
                .map_or(64, |item| item.max_stack)
                .max(1);
            displayed += stack.count as f32 / max as f32;
        }
    }
    *output = if displayed > 0.0 {
        (displayed / capacity as f32 * 14.0).floor() as i32 + 1
    } else {
        0
    };
}
