use horizon_core::{geometry::Direction, position::BlockPos};
use horizon_world::{
    fluid::{FluidKind, FluidState},
    level::{PlacementContext, flags, ordered_by_nearest},
    nbt::Tag,
    registry::BlockStateId,
};

use crate::{items::ItemStack, containers::{BlockEntity, ModBlockEntity}};
use horizon_assets::item_model::DisplayContext;

use super::{
    Game, GameLevel,

    create_fluids::name as direction_name,
};

pub(super) const ITEM: &str = "create:placard";
const STACK: &str = "Item";

fn has_support(level: &GameLevel<'_>, at: BlockPos, support: Direction) -> bool {
    let [dx, dy, dz] = support.normal();
    let state = level.world.block(at.x + dx, at.y + dy, at.z + dz);
    level
        .behaviours
        .collision_shape(state)
        .is_some_and(|shape| !shape.is_empty())
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
            Direction::Up => ("ceiling", facing_player.opposite()),
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
        || level
            .behaviours
            .collision_shape(neighbour)
            .is_some_and(|shape| !shape.is_empty())
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


pub(super) fn click(game: &mut Game<'_>, at: [i32; 3]) -> bool {
    if game.native_block(at) != ITEM || game.native_sneaking() { return false; }
    let Some(held) = game.held().cloned() else { return false; };
    let existing = super::create_machines::mod_entity(game, at)
        .and_then(|entity| super::create_depot::compound(&entity.nbt, STACK))
        .and_then(ItemStack::from_nbt);
    if let Some(existing) = existing {
        let matches = match super::create_depot::encode(&existing) {
            Tag::Compound(data) if matches!(existing.item.as_ref(), "create:filter" | "create:attribute_filter" | "create:package_filter") => super::create_item_filters::matches(game.items(), &data, &held, true),
            _ => existing.same_item_same_components(&held),
        };
        if matches && game.native_block_property(at, "powered").as_deref() != Some("true") {
            game.native_with_mod_block_entity(at, |entity| { entity.nbt.insert("PoweredTicks".into(), Tag::Int(19)); });
            game.native_set_block_property_with(at, "powered", "true", horizon_world::level::flags::UPDATE_ALL);
            game.native_update_signal_neighbors(game.native_dimension(), at);
            game.native_block_entity_sync(at);
        }
        return true;
    }
    let mut one = held;
    one.count = 1;
    if game.native_with_mod_block_entity(at, |entity| { entity.nbt.insert(STACK.into(), super::create_depot::encode(&one)); }).is_none() { return false; }
    if !game.creative {
        if let Some(stack) = game.held_mut() { stack.count -= 1; if stack.count == 0 { *game.held_mut() = None; } }
    }
    game.native_block_entity_sync(at);
    game.swing_arm();
    true
}

pub(super) fn attack(game: &mut Game<'_>, at: [i32; 3]) -> bool {
    if !game.native_authoritative() || game.native_block(at) != ITEM { return false; }
    let stack = game.native_with_mod_block_entity(at, |entity| entity.nbt.remove(&STACK.into()))
        .flatten().and_then(|tag| match tag { Tag::Compound(data) => ItemStack::from_nbt(&data), _ => None });
    let Some(stack) = stack else { return false; };
    game.give_or_drop(stack);
    game.native_block_entity_sync(at);
    true
}

pub(super) fn remove(level: &mut GameLevel<'_>, pos: BlockPos, side_effects: bool) {
    if !side_effects || !level.native_authoritative { return; }
    let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get(&(pos.x, pos.y, pos.z)) else { return; };
    if entity.id != ITEM { return; }
    let stack = super::create_depot::compound(&entity.nbt, STACK).and_then(ItemStack::from_nbt);
    if let Some(stack) = stack { level.drop_lost_contents(pos, vec![Some(stack)]); }
}

pub(super) fn render(game: &Game<'_>, state: BlockStateId, entity: &ModBlockEntity, draw: &mut crate::game::native_block_entity_draw::BlockEntityDraw) {
    let Some(stack) = super::create_depot::compound(&entity.nbt, STACK).and_then(ItemStack::from_nbt) else { return; };
    let face = game.native_block_state_property(state, "face");
    let facing = game.native_block_state_property(state, "facing");
    let yaw = match facing { Some("east") => 90.0, Some("south") => 180.0, Some("west") => 270.0, _ => 0.0 };
    draw.push();
    draw.translate([0.5, 0.5, 0.5]);
    draw.rotate_about([0.0, 1.0, 0.0], yaw + if face == Some("ceiling") {180.0} else {0.0}, [0.0; 3]);
    draw.rotate_about([1.0, 0.0, 0.0], match face { Some("floor") => 90.0, Some("ceiling") => -90.0, _ => 0.0 }, [0.0; 3]);
    draw.translate([0.0, 0.0, 0.28125]);
    // Create's PlacardRenderer uses 0.5 for a 3D block model and 0.375 for
    // flat item models. A registered block default state is the native item
    // model's 3D-block equivalent for the imported Create assets.
    let scale = if game.native_default_state(&stack.item).is_some() {
        0.5
    } else {
        0.375
    };
    draw.scale([scale; 3]);
    game.native_draw_item(draw, &stack, DisplayContext::Fixed, None, 0);
    draw.pop();
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let ticks = super::create_machines::int(&entity.nbt, "PoweredTicks").unwrap_or(0);
    if ticks <= 0 { return; }
    entity.nbt.insert("PoweredTicks".into(), Tag::Int(ticks - 1));
    if ticks == 1 {
        game.native_set_block_property_with(pos, "powered", "false", horizon_world::level::flags::UPDATE_ALL);
        game.native_update_signal_neighbors(game.native_dimension(), pos);
    }
}

pub(super) fn signal(level: &GameLevel<'_>, state: BlockStateId, face: Direction, direct: bool, out: &mut i32) {
    let Some(data) = level.registry.state(state).filter(|data| data.name == ITEM) else { return; };
    if data.properties.get("powered").is_some_and(|v| v == "true") && (!direct || support_direction(level, state).is_some_and(|support| support.opposite() == face)) { *out = 15; }
}
