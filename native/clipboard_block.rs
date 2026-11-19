use horizon_core::{geometry::Direction, position::BlockPos};
use horizon_world::{
    fluid::{FluidKind, FluidState},
    level::{PlacementContext, flags, ordered_by_nearest},
    nbt::Tag,
    registry::BlockStateId,
};

use crate::items::ItemStack;

use super::{
    Game, GameLevel, Hand,
    create_clipboard::{COMPONENT, ITEM},
    create_fluids::name as direction_name,
};

const STACK: &str = "ClipboardItem";

fn has_support(level: &GameLevel<'_>, at: BlockPos, support: Direction) -> bool {
    let [dx, dy, dz] = support.normal();
    !level
        .behaviours
        .is_replaceable(level.world.block(at.x + dx, at.y + dy, at.z + dz))
}

fn support_direction(level: &GameLevel<'_>, state: BlockStateId) -> Option<Direction> {
    let state = level
        .registry
        .state(state)
        .filter(|state| state.name == ITEM)?;
    match state.properties.get("face")?.as_str() {
        "floor" => Some(Direction::Down),
        "ceiling" => Some(Direction::Up),
        "wall" => {
            let facing = state.properties.get("facing")?;
            Direction::ALL
                .iter()
                .copied()
                .find(|&side| direction_name(side) == facing.as_str())
                .map(Direction::opposite)
        }
        _ => None,
    }
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
    fluid: FluidState,
) -> Option<Option<BlockStateId>> {
    if !level
        .registry
        .state(state)
        .is_some_and(|state| state.name == ITEM)
    {
        return None;
    }
    if !context.sneaking {
        return Some(None);
    }
    let mut directions = ordered_by_nearest(context.yaw, context.pitch);
    if !context.replace_clicked
        && let Some(index) = directions
            .iter()
            .position(|&side| side == context.face.opposite())
    {
        directions[..=index].rotate_right(1);
    }
    let yaw = (f64::from(context.yaw) / 90.0 + 0.5).floor() as i64 & 3;
    let facing_player = [
        Direction::North,
        Direction::East,
        Direction::South,
        Direction::West,
    ][yaw as usize];
    let waterlogged = if fluid.kind() == FluidKind::Water && fluid.is_source() {
        "true"
    } else {
        "false"
    };
    Some(directions.into_iter().find_map(|support| {
        if !has_support(level, context.pos, support) {
            return None;
        }
        let (face, facing) = match support {
            Direction::Down => ("floor", facing_player),
            Direction::Up => ("ceiling", facing_player),
            side => ("wall", side.opposite()),
        };
        let state = level.native_state_with_property(state, "face", face)?;
        let state = level.native_state_with_property(state, "facing", direction_name(facing))?;
        level.native_state_with_property(state, "waterlogged", waterlogged)
    }))
}

pub(super) fn survive(level: &GameLevel<'_>, at: BlockPos, state: BlockStateId) -> Option<bool> {
    Some(has_support(level, at, support_direction(level, state)?))
}

pub(super) fn update_shape(
    level: &GameLevel<'_>,
    state: BlockStateId,
    changed_side: Direction,
    neighbour: BlockStateId,
) -> Option<BlockStateId> {
    if support_direction(level, state)? != changed_side
        || !level.behaviours.is_replaceable(neighbour)
    {
        return None;
    }
    let replacement = if level.behaviours.fluid(state).kind() == FluidKind::Water {
        "minecraft:water"
    } else {
        "minecraft:air"
    };
    level.registry.default_state(replacement)
}

pub(super) fn placed(game: &mut Game<'_>, at: [i32; 3], source: &ItemStack) {
    if source.item.as_ref() != ITEM || game.native_block(at) != ITEM {
        return;
    }
    let mut stack = source.clone();
    stack.count = 1;
    write_stack(game, at, &stack, None);
}

pub(super) fn stack_at(game: &Game<'_>, at: [i32; 3]) -> Option<ItemStack> {
    let entity = super::create_machines::mod_entity(game, at).filter(|entity| entity.id == ITEM)?;
    Some(
        super::create_depot::compound(&entity.nbt, STACK)
            .and_then(ItemStack::from_nbt)
            .unwrap_or_else(|| ItemStack::new(ITEM, 1)),
    )
}

fn write_stack(game: &mut Game<'_>, at: [i32; 3], stack: &ItemStack, written: Option<bool>) {
    let encoded = super::create_depot::encode(stack);
    let Tag::Compound(data) = &encoded else {
        return;
    };
    let has_components = matches!(data.get(&"components".into()), Some(Tag::Compound(components)) if !components.is_empty());
    if game
        .native_with_mod_block_entity(at, |entity| {
            if has_components {
                entity.nbt.insert(STACK.into(), encoded);
            } else {
                entity.nbt.remove(&STACK.into());
            }
        })
        .is_none()
    {
        return;
    }
    let written = if written.unwrap_or(has_components) {
        "true"
    } else {
        "false"
    };
    game.native_set_block_property_with(at, "written", written, flags::UPDATE_ALL);
    game.native_block_entity_sync(at);
}

pub(super) fn save_contents(game: &mut Game<'_>, at: [i32; 3], content: Option<Tag>) {
    let Some(mut stack) = stack_at(game, at) else {
        return;
    };
    let written = content.is_some();
    let result = match content {
        Some(content) => game.native_set_component(&mut stack, COMPONENT, content),
        None => game.native_remove_component(&mut stack, COMPONENT),
    };
    if result.is_ok() {
        write_stack(game, at, &stack, Some(written));
    }
}

pub(super) fn pickup(game: &mut Game<'_>, at: [i32; 3]) -> bool {
    if !game.native_authoritative() || game.native_block(at) != ITEM {
        return false;
    }
    let stack = stack_at(game, at).unwrap_or_else(|| ItemStack::new(ITEM, 1));
    if !game.with_level(|behaviour, level, ticks| {
        behaviour.destroy_block(level, ticks, BlockPos::new(at[0], at[1], at[2]), false)
    }) {
        return false;
    }
    if game.stack_in(game.selected).is_none() {
        *game.stack_in_mut(game.selected) = Some(stack);
    } else {
        game.give_or_drop(stack);
    }
    game.guest_inventory_resend |= game.lan_acting.is_some();
    true
}

pub(super) fn sneak_pickup(game: &mut Game<'_>, at: [i32; 3]) -> bool {
    game.hand == Hand::Main
        && game.held().is_none()
        && game.offhand.is_none()
        && game.native_sneaking()
        && pickup(game, at)
}
