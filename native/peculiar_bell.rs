use horizon_core::{geometry::Direction, position::BlockPos};
use horizon_world::{level::PlacementContext, registry::BlockStateId};

use super::{Game, GameLevel};

const PECULIAR: &str = "create:peculiar_bell";
const HAUNTED: &str = "create:haunted_bell";

fn can_ring_from(game: &Game<'_>, pos: [i32; 3]) -> bool {
    let Some((_, hit)) = game.native_view_hit() else { return false; };
    let face = [
        if hit.x - f64::from(pos[0]) < 0.001 { -1 } else if hit.x - f64::from(pos[0]) > 0.999 { 1 } else { 0 },
        if hit.y - f64::from(pos[1]) < 0.001 { -1 } else if hit.y - f64::from(pos[1]) > 0.999 { 1 } else { 0 },
        if hit.z - f64::from(pos[2]) < 0.001 { -1 } else if hit.z - f64::from(pos[2]) > 0.999 { 1 } else { 0 },
    ];
    if [hit.block_x, hit.block_y, hit.block_z] != pos || face[1] != 0 || hit.y - f64::from(pos[1]) > 0.8124 { return false; }
    let id = game.world.block(pos[0], pos[1], pos[2]);
    let Some(state) = game.pack.assets.registry.state(id) else { return false; };
    let axis = state.properties.get("facing").map(|f| if matches!(f.as_str(), "east" | "west") { 0 } else { 2 });
    let Some(axis) = axis else { return false; };
    let hit_axis = if face[0] != 0 { 0 } else { 2 };
    match state.properties.get("attachment").map(String::as_str) {
        Some("floor") | Some("ceiling") => axis == hit_axis,
        Some("wall") | Some("single_wall") | Some("double_wall") => axis != hit_axis,
        _ => false,
    }
}

pub(super) fn attack(game: &mut Game<'_>, pos: [i32; 3], canceled: &mut bool) {
    if *canceled || !game.native_authoritative() || !matches!(game.native_block(pos).as_str(), PECULIAR | HAUNTED) || !can_ring_from(game, pos) { return; }
    let (sound, volume, pitch) = if game.native_block(pos) == PECULIAR { ("create:peculiar_bell_use", 2, 0.94) } else { ("create:haunted_bell_use", 4, 1.0) };
    game.native_play_sound_in_place(sound, pos.map(|v| f64::from(v) + 0.5), volume, pitch, 1.0);
    game.swing_arm();
    *canceled = true;
}

fn convert(level: &GameLevel<'_>, state: BlockStateId) -> Option<BlockStateId> {
    let info = level.registry.state(state)?;
    if info.name != PECULIAR {
        return None;
    }
    let default = level.registry.default_state(HAUNTED)?;
    let mut haunted_info = level.registry.state(default)?.clone();
    for property in ["facing", "attachment", "powered"] {
        if let Some(value) = info.properties.get(property) {
            haunted_info.properties.insert(property.to_owned(), value.clone());
        }
    }
    level.registry.resolve(&haunted_info).ok()
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
