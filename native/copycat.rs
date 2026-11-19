use horizon_core::{geometry::Direction, position::BlockPos};
use horizon_world::fluid::{FluidKind, FluidState};
use horizon_world::level::{PlaceContext, PlacementContext, ordered_by_nearest};
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::{containers::BlockEntity, items::ItemStack};

use super::create_cogwheel::direction_axis;
use super::create_depot::{compound, encode};
use super::create_fluids::name as direction_name;
use super::create_machines::mod_entity;
use super::{Game, GameLevel, Hit};

pub(super) const PANEL: &str = "create:copycat_panel";
pub(super) const STEP: &str = "create:copycat_step";
pub(super) const ENTITY: &str = "create:copycat";
pub(super) const BASE: &str = "create:copycat_base";
const WRENCH: &str = "create:wrench";
const PLACEMENT_ASSIST_RANGE: i32 = 12;

fn wrapper(block: &str) -> bool {
    matches!(block, PANEL | STEP)
}

fn horizontal(yaw: f32) -> Direction {
    let index = ((f64::from(yaw) / 90.0 + 0.5).floor() as i32).rem_euclid(4);
    [
        Direction::South,
        Direction::West,
        Direction::North,
        Direction::East,
    ][index as usize]
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
    fluid: FluidState,
) -> Option<Option<BlockStateId>> {
    let facing = match level.native_state_block(state)? {
        PANEL => context.nearest_looking_direction().opposite(),
        STEP => horizontal(context.yaw),
        _ => return None,
    };
    let wet = if fluid.kind() == FluidKind::Water && fluid.is_source() {
        "true"
    } else {
        "false"
    };
    Some((|| {
        let mut state =
            level.native_state_with_property(state, "facing", direction_name(facing))?;
        if level.native_state_block(state) == Some(STEP) {
            let top = context.face == Direction::Down
                || (context.face != Direction::Up
                    && context.hit.y - f64::from(context.pos.y) > 0.5);
            state = level.native_state_with_property(
                state,
                "half",
                if top { "top" } else { "bottom" },
            )?;
        }
        level.native_state_with_property(state, "waterlogged", wet)
    })())
}

pub(super) fn material(game: &Game<'_>, nbt: &Compound) -> Option<BlockStateId> {
    nbt.get(&"Material".into())
        .and_then(|tag| game.state_from_nbt(tag))
}

fn full_outline(outline: &[[f64; 6]]) -> bool {
    !outline.is_empty()
        && (0..3).all(|axis| {
            outline.iter().map(|bounds| bounds[axis]).reduce(f64::min) == Some(0.0)
                && outline
                    .iter()
                    .map(|bounds| bounds[axis + 3])
                    .reduce(f64::max)
                    == Some(1.0)
        })
}

fn set_property(game: &Game<'_>, state: BlockStateId, property: &str, value: &str) -> BlockStateId {
    let registry = &game.pack.assets.registry;
    let Some(mut descriptor) = registry.state(state).cloned() else {
        return state;
    };
    let Some(old) = descriptor.properties.get_mut(property) else {
        return state;
    };
    *old = value.to_owned();
    registry.id(&descriptor).unwrap_or(state)
}

fn is_trapdoor(game: &Game<'_>, state: BlockStateId) -> bool {
    game.res.facts().get(state).has_class("TrapDoorBlock")
}

pub(super) fn is_bars(name: &str, facts: &horizon_client::blocks::StateFacts) -> bool {
    facts.has_class("IronBarsBlock")
        && !facts.has_class("StainedGlassPaneBlock")
        && !name.ends_with("_pane")
}

fn accepted(
    game: &Game<'_>,
    block: &str,
    stack: &ItemStack,
    pos: [i32; 3],
    face: Direction,
    hit_height: Option<f64>,
) -> Option<BlockStateId> {
    let mut state = game.items().get(&stack.item)?.block?;
    let name = current_block(game, state)?;
    if wrapper(name) {
        return None;
    }
    let facts = game.res.facts().get(state);
    let trapdoor = is_trapdoor(game, state);
    let panel_special = block == PANEL && (trapdoor || is_bars(name, facts));
    let in_tag = |tag| game.native_block_name_in_tag(name, tag).unwrap_or(false);
    if !panel_special && !in_tag("create:copycat_allow") {
        if in_tag("create:copycat_deny")
            || facts.block_entity
            || facts.has_class("StairBlock")
            || !full_outline(&facts.outline)
        {
            return None;
        }
        let mut scene = horizon_client::collisions::SceneCollisions {
            world: &game.world,
            binding: game.collision,
            subject: None,
        };
        if !game
            .collision
            .collision_shape(&mut scene, state, pos)
            .is_ok_and(|shape| !shape.is_empty())
        {
            return None;
        }
    }

    let axis = if face.normal()[0] != 0 {
        "x"
    } else if face.normal()[1] != 0 {
        "y"
    } else {
        "z"
    };
    state = set_property(game, state, "facing", direction_name(face));
    state = set_property(game, state, "axis", axis);

    if panel_special
        && trapdoor
        && let Some(hit_height) = hit_height
    {
        let facing = game.native_block_property(pos, "facing")?;
        if facing == "up" || facing == "down" {
            let player = horizontal(game.yaw);
            state = set_property(game, state, "open", "false");
            state = set_property(game, state, "facing", direction_name(player));
            if facing == "down" {
                state = set_property(game, state, "half", "top");
            }
        } else {
            state = set_property(game, state, "open", "true");
            state = set_property(game, state, "facing", &facing);
            let near_top = hit_height - 0.5 > f64::from(pos[1]);
            state = set_property(game, state, "half", if near_top { "top" } else { "bottom" });
        }
    }
    Some(state)
}

fn current_block<'g>(game: &'g Game<'_>, state: BlockStateId) -> Option<&'g str> {
    Some(game.pack.assets.registry.state(state)?.name.as_str())
}

fn cycle_material(game: &Game<'_>, state: BlockStateId) -> Option<BlockStateId> {
    let read = |property| game.native_block_state_property(state, property);
    let property_and_cycle: [(&str, &[&str]); 6] = [
        (
            "half",
            if read("open") == Some("true") {
                &["top", "bottom"]
            } else {
                &[]
            },
        ),
        (
            "facing",
            if read("facing").is_some_and(|value| {
                let block = current_block(game, state).unwrap_or_default();
                let both_vertical = game
                    .pack
                    .assets
                    .registry
                    .property_values(block, "facing")
                    .contains(&"up");
                both_vertical || matches!(value, "up" | "down")
            }) {
                &["north", "east", "south", "west", "up", "down"]
            } else {
                &["north", "east", "south", "west"]
            },
        ),
        ("axis", &["x", "y", "z"]),
        ("horizontal_axis", &["x", "z"]),
        ("lit", &["false", "true"]),
        ("powering", &["false", "true"]),
    ];
    for (property, values) in property_and_cycle {
        if let Some(index) =
            read(property).and_then(|value| values.iter().position(|&entry| entry == value))
        {
            let next = set_property(game, state, property, values[(index + 1) % values.len()]);
            if next != state {
                return Some(next);
            }
        }
    }
    None
}

fn adjacent_material(
    game: &Game<'_>,
    pos: [i32; 3],
    target: BlockStateId,
    material_in: BlockStateId,
) -> BlockStateId {
    let block = current_block(game, material_in);
    for side in Direction::ALL {
        let normal = side.normal();
        let other: [i32; 3] = std::array::from_fn(|axis| pos[axis] + normal[axis]);
        if game.world.block(other[0], other[1], other[2]) == target
            && let Some(entity) = mod_entity(game, other)
            && let Some(other_material) = material(game, &entity.nbt)
            && current_block(game, other_material) == block
        {
            return other_material;
        }
    }
    material_in
}

fn sync_material(
    game: &mut Game<'_>,
    pos: [i32; 3],
    state: BlockStateId,
    copy_item: Option<&ItemStack>,
) {
    let Some(state) = game.pack.assets.registry.state(state) else {
        return;
    };
    let mut tag = Compound::from([("Name".into(), Tag::String(state.name.as_str().into()))]);
    if !state.properties.is_empty() {
        let properties = state
            .properties
            .iter()
            .map(|(name, value)| (name.as_str().into(), Tag::String(value.as_str().into())))
            .collect();
        tag.insert("Properties".into(), Tag::Compound(properties));
    }
    let item = copy_item.map(|stack| {
        let mut stack = stack.clone();
        stack.count = 1;
        encode(&stack)
    });
    game.native_with_mod_block_entity(pos, |copycat| {
        copycat.nbt.insert("Material".into(), Tag::Compound(tag));
        if let Some(item) = item {
            copycat.nbt.insert("Item".into(), item);
        }
    });
    game.refresh_copycat_panel_material(pos);
    game.native_block_entity_sync(pos);
    game.guest_inventory_resend |= game.lan_acting.is_some();
}

fn clear_material(nbt: &mut Compound) {
    let material = Compound::from([("Name".into(), Tag::String(BASE.into()))]);
    nbt.insert("Material".into(), Tag::Compound(material));
    nbt.insert("Item".into(), Tag::Compound(Compound::new()));
}

pub(super) fn new_tag() -> Compound {
    let mut tag = Compound::new();
    clear_material(&mut tag);
    tag
}

fn unwrench(game: &mut Game<'_>, pos: [i32; 3], block: &str) -> bool {
    let sneak = game.native_sneaking();
    let stack = mod_entity(game, pos)
        .filter(|copycat| copycat.id == ENTITY)
        .and_then(|copycat| compound(&copycat.nbt, "Item"))
        .and_then(ItemStack::from_nbt);
    if !sneak && stack.is_none() {
        return false;
    }
    if game.native_authoritative() {
        if let Some(stack) = stack {
            if !game.creative {
                game.give_or_drop(stack);
            }
            game.native_with_mod_block_entity(pos, |copycat| clear_material(&mut copycat.nbt));
            game.refresh_copycat_panel_material(pos);
            game.native_block_entity_sync(pos);
            let state = game.world.block(pos[0], pos[1], pos[2]);
            game.level_event_at(2001, pos, state.0 as i32);
        }
        if sneak {
            super::create_wrench::pickup(game, pos, block);
        }
        game.guest_inventory_resend |= game.lan_acting.is_some();
    }
    true
}

fn assist_target(
    game: &Game<'_>,
    origin: BlockPos,
    state: BlockStateId,
    click: [f64; 3],
) -> Option<BlockPos> {
    let source = current_block(game, state)?;
    let facing = game.native_block_state_property(state, "facing")?;
    let facing = Direction::ALL
        .into_iter()
        .find(|&side| direction_name(side) == facing)?;
    let axis = direction_axis(facing);
    let step = source == STEP;
    let center = [origin.x, origin.y, origin.z].map(|value| f64::from(value) + 0.5);
    let edge_distance = |side: Direction| {
        side.normal()
            .into_iter()
            .zip(center)
            .zip(click)
            .map(|((offset, center), actual)| (center + f64::from(offset) * 0.5 - actual).powi(2))
            .sum::<f64>()
    };
    let mut directions: Vec<_> = Direction::ALL
        .into_iter()
        .filter(|&side| direction_axis(side) != axis && (!step || direction_axis(side) != "y"))
        .collect();
    directions.sort_by(|&a, &b| edge_distance(a).total_cmp(&edge_distance(b)));
    let range = if step { PLACEMENT_ASSIST_RANGE } else { 1 };
    for side in directions {
        let [dx, dy, dz] = side.normal();
        for distance in 1..=range {
            let at = origin.offset(dx * distance, dy * distance, dz * distance);
            let other = game.world.block(at.x, at.y, at.z);
            if step
                && current_block(game, other) == Some(STEP)
                && game
                    .native_block_state_property(other, "facing")
                    .and_then(|facing| {
                        Direction::ALL
                            .into_iter()
                            .find(|&d| direction_name(d) == facing)
                    })
                    .is_some_and(|facing| direction_axis(facing) == axis)
            {
                continue;
            }
            if game.res.behaviours().is_replaceable(other) {
                return Some(at);
            }
            break;
        }
    }
    None
}

pub(super) fn redirect_placement(game: &Game<'_>, context: &mut PlaceContext) {
    if context.sneaking || !game.may_build() || !wrapper(&context.item) {
        return;
    }
    let origin = context.clicked_pos;
    let source = game.world.block(origin.x, origin.y, origin.z);
    if current_block(game, source) != Some(&context.item) {
        return;
    }
    let Some(target) = assist_target(game, origin, source, context.hit.components()) else {
        return;
    };
    let other = game.world.block(target.x, target.y, target.z);
    let fluid = game.res.behaviours().fluid(other);
    let wet = fluid.kind() == FluidKind::Water && fluid.is_source();
    context.clicked_pos = target;
    context.state_override = Some(set_property(
        game,
        source,
        "waterlogged",
        if wet { "true" } else { "false" },
    ));
}

pub(super) fn use_material(game: &mut Game<'_>, hit: &Hit) -> bool {
    let pos = hit.pos;
    let block = game.native_block(pos);
    if !wrapper(&block) || !game.may_build() {
        return false;
    }
    let Some(stack) = game.held().cloned() else {
        return false;
    };
    if stack.item.as_ref() == WRENCH {
        return unwrench(game, pos, &block);
    }
    if game.native_sneaking() {
        return false;
    }
    if block == PANEL && stack.item.as_ref() == PANEL {
        let pos = BlockPos::new(pos[0], pos[1], pos[2]);
        let state = game.world.block(pos.x, pos.y, pos.z);
        // Java's Panel claims the click even when none of its four edges is available.
        let blocked = assist_target(game, pos, state, hit.point).is_none();
        if blocked {
            game.guest_inventory_resend |= game.lan_acting.is_some();
        }
        return blocked;
    }
    let Some(face) = Direction::ALL
        .into_iter()
        .find(|side| side.normal() == hit.face)
    else {
        return false;
    };
    let Some(next) = accepted(game, &block, &stack, pos, face, Some(hit.point[1])) else {
        return false;
    };
    let Some(copycat) = mod_entity(game, pos) else {
        return false;
    };
    let current =
        material(game, &copycat.nbt).filter(|&state| current_block(game, state) != Some(BASE));
    let at = pos.map(|axis| f64::from(axis) + 0.5);
    if let Some(current) = current {
        if current_block(game, current) != current_block(game, next) {
            return false;
        }
        let Some(cycled) = cycle_material(game, current) else {
            return false;
        };
        if game.native_authoritative() {
            sync_material(game, pos, cycled, None);
            game.native_play_sound_in_place(
                "minecraft:entity.item_frame.add_item",
                at,
                4,
                0.75,
                0.95,
            );
        }
    } else if game.native_authoritative() {
        let state = game.world.block(pos[0], pos[1], pos[2]);
        let next = adjacent_material(game, pos, state, next);
        let sound = game.res.facts().get(next).sounds.place.clone();
        sync_material(game, pos, next, Some(&stack));
        game.native_play_sound_in_place(&sound, at, 4, 1.0, 0.75);
        if !game.creative {
            game.consume_held();
        }
    }
    true
}

pub(super) fn placed(game: &mut Game<'_>, pos: [i32; 3], state: BlockStateId) {
    if !game.native_authoritative() {
        return;
    }
    let Some(block) = current_block(game, state).filter(|block| wrapper(block)) else {
        return;
    };
    let Some(stack) = game.offhand.clone() else {
        return;
    };
    let face = ordered_by_nearest(game.yaw, game.pitch)[0];
    let Some(next) = accepted(game, block, &stack, pos, face, None) else {
        return;
    };
    if mod_entity(game, pos).is_none_or(|copycat| {
        material(game, &copycat.nbt)
            .is_some_and(|material| current_block(game, material) != Some(BASE))
    }) {
        return;
    }
    let next = adjacent_material(game, pos, state, next);
    sync_material(game, pos, next, Some(&stack));
    if !game.creative
        && let Some(held) = game.offhand.as_mut()
    {
        held.count -= 1;
        if held.count == 0 {
            game.offhand = None;
        }
        game.guest_inventory_resend |= game.lan_acting.is_some();
    }
}

pub(super) fn before_destroy(game: &mut Game<'_>, pos: [i32; 3], state: BlockStateId) {
    if game.creative && current_block(game, state).is_some_and(wrapper) {
        game.native_with_mod_block_entity(pos, |copycat| clear_material(&mut copycat.nbt));
    }
}

pub(super) fn remove(level: &mut GameLevel<'_>, pos: BlockPos, side_effects: bool) {
    let key = (pos.x, pos.y, pos.z);
    let Some(BlockEntity::Mod(copycat)) = level.world.block_entities.get(&key) else {
        return;
    };
    if copycat.id != ENTITY {
        return;
    }
    let stack = (side_effects && level.native_authoritative)
        .then(|| compound(&copycat.nbt, "Item").and_then(ItemStack::from_nbt))
        .flatten();
    level.world.set_copycat_panel_material(key, None);
    if let Some(stack) = stack {
        level.pop_resource([pos.x, pos.y, pos.z], stack);
    }
}
