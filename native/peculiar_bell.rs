use horizon_core::{geometry::Direction, position::BlockPos};
use horizon_world::{level::PlacementContext, registry::BlockStateId};

use super::GameLevel;

const PECULIAR: &str = "create:peculiar_bell";
const HAUNTED: &str = "create:haunted_bell";

fn convert(level: &GameLevel<'_>, state: BlockStateId) -> Option<BlockStateId> {
    let info = level.registry.state(state)?;
    if info.name != PECULIAR {
        return None;
    }
    let mut haunted = level.native_default_state(HAUNTED)?;
    for property in ["facing", "attachment", "powered"] {
        if let Some(value) = info.properties.get(property) {
            haunted = level.native_state_with_property(haunted, property, value)?;
        }
    }
    Some(haunted)
}

fn soul_fire(level: &GameLevel<'_>, pos: BlockPos) -> bool {
    let block = level.world.block(pos.x, pos.y, pos.z);
    level.registry.state(block).is_some_and(|state| {
        state.name == "minecraft:soul_fire"
            || (state.name == "minecraft:soul_campfire"
                && state.properties.get("lit").is_some_and(|lit| lit == "true"))
    })
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    ctx: &PlacementContext,
) -> Option<Option<BlockStateId>> {
    if level.native_state_block(state) != Some(PECULIAR) {
        return None;
    }
    let below = BlockPos::new(ctx.pos.x, ctx.pos.y - 1, ctx.pos.z);
    if soul_fire(level, below) {
        Some(convert(level, state))
    } else {
        None
    }
}

pub(super) fn update_shape(
    level: &GameLevel<'_>,
    state: BlockStateId,
    direction: Direction,
    neighbour: BlockStateId,
    result: &mut Option<BlockStateId>,
) {
    if direction != Direction::Down {
        return;
    }
    let Some(info) = level.registry.state(neighbour) else {
        return;
    };
    if info.name != "minecraft:soul_fire"
        && !(info.name == "minecraft:soul_campfire"
            && info.properties.get("lit").is_some_and(|lit| lit == "true"))
    {
        return;
    }
    *result = convert(level, state);
}
