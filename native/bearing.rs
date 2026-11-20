use std::collections::{BTreeSet, VecDeque};

use horizon_core::geometry::Direction;
use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_depot::{compound, encode};
use super::create_fan::facing;
use super::create_machines::{
    GEARBOX, axis_index, float, int, mod_entity, offset, reset_moved_gearbox, set_float,
};
use super::native_entities::NativeDisplay;

struct GlueBox {
    id: u32,
    position: [f64; 3],
    low: [f64; 3],
    high: [f64; 3],
}

impl GlueBox {
    fn contains(&self, block: [i32; 3]) -> bool {
        (0..3).all(|i| {
            let center = f64::from(block[i]) + 0.5;
            center >= self.low[i] && center < self.high[i]
        })
    }
}

fn vector(tag: Option<&Tag>) -> Option<[f64; 3]> {
    let Some(Tag::List(seq)) = tag else {
        return None;
    };
    let [Tag::Double(x), Tag::Double(y), Tag::Double(z)] = seq.as_slice() else {
        return None;
    };
    Some([*x, *y, *z].map(f64::from_bits))
}

fn glue(game: &Game<'_>) -> Vec<GlueBox> {
    game.others
        .iter()
        .filter_map(|entity| {
            let tag = game.persist.raw.get(&entity.id)?;
            if entity.kind != "create:super_glue"
                && !(entity.kind == "minecraft:marker"
                    && tag.get(super::create_glue::MARKER) == Some(&Tag::Byte(1)))
            {
                return None;
            }
            let from = vector(tag.get("From"))?;
            let to = vector(tag.get("To"))?;
            let at = [entity.position.x, entity.position.y, entity.position.z];
            Some(GlueBox {
                id: entity.id,
                position: at,
                low: std::array::from_fn(|i| at[i] + from[i].min(to[i])),
                high: std::array::from_fn(|i| at[i] + from[i].max(to[i])),
            })
        })
        .collect()
}

pub(super) fn attached_glue(game: &Game<'_>, blocks: &[[i32; 3]], anchor: [i32; 3]) -> Vec<Tag> {
    glue(game)
        .into_iter()
        .filter_map(|area| {
            let joins = blocks.iter().any(|&block| {
                area.contains(block)
                    && Direction::ALL.into_iter().any(|side| {
                        let other = offset(block, side.normal());
                        area.contains(other) && blocks.contains(&other)
                    })
            });
            if !joins {
                return None;
            }
            let uuid = game.persist.uuid_of(area.id)?;
            let relative = area
                .position
                .into_iter()
                .zip(anchor)
                .map(|(x, origin)| Tag::Double((x - f64::from(origin)).to_bits()))
                .collect();
            Some(Tag::Compound(Compound::from([
                ("Uuid".into(), Tag::IntArray(uuid.to_vec())),
                ("Relative".into(), Tag::List(relative)),
            ])))
        })
        .collect()
}

fn glue_entity(game: &Game<'_>, area: &Tag) -> Option<u32> {
    let Tag::IntArray(uuid) = area.get("Uuid")? else {
        return None;
    };
    game.others
        .iter()
        .find(|entity| {
            game.persist
                .uuid_of(entity.id)
                .is_some_and(|known| known.as_slice() == uuid.as_slice())
        })
        .map(|entity| entity.id)
}

pub(super) fn move_glue(game: &mut Game<'_>, glue: &[Tag], at: [f64; 3]) {
    let dimension = game.native_dimension();
    for area in glue {
        let (Some(entity), Some(relative)) =
            (glue_entity(game, area), vector(area.get("Relative")))
        else {
            continue;
        };
        game.native_move_entity(
            dimension,
            entity,
            std::array::from_fn(|i| at[i] + relative[i]),
            0.0,
            0.0,
        );
    }
}

fn rotate_glue(game: &mut Game<'_>, glue: &[Tag], anchor: [i32; 3], axis: usize, angle: f64) {
    let dimension = game.native_dimension();
    let angle = (angle / std::f64::consts::FRAC_PI_2).round() * std::f64::consts::FRAC_PI_2;
    for area in glue {
        let (Some(id), Some(relative)) = (glue_entity(game, area), vector(area.get("Relative")))
        else {
            continue;
        };
        let shifted = rotate(relative.map(|component| component - 0.5), axis, angle);
        let at = std::array::from_fn(|i| f64::from(anchor[i]) + 0.5 + shifted[i]);
        if !game.native_move_entity(dimension, id, at, 0.0, 0.0) {
            continue;
        }
        if let Some(Tag::Compound(tag)) = game.persist.raw.get_mut(&id) {
            for key in ["From", "To"] {
                if let Some(bound) = vector(tag.get(&key.into())) {
                    let rotated = rotate(bound, axis, angle);
                    tag.insert(
                        key.into(),
                        Tag::List(rotated.map(|value| Tag::Double(value.to_bits())).to_vec()),
                    );
                }
            }
        }
    }
}

pub(super) fn saved_block(game: &Game<'_>, world: [i32; 3], anchor: [i32; 3]) -> Option<Compound> {
    let id = game.world.block(world[0], world[1], world[2]);
    let state = game.pack.assets.registry.state(id)?;
    if matches!(
        state.name.as_str(),
        "minecraft:air"
            | "minecraft:cave_air"
            | "minecraft:void_air"
            | "minecraft:water"
            | "minecraft:lava"
            | "minecraft:bedrock"
            | "minecraft:barrier"
            | "minecraft:structure_void"
    ) {
        return None;
    }
    let mut properties = Compound::new();
    for (key, value) in &state.properties {
        properties.insert(key.as_str().into(), Tag::String(value.as_str().into()));
    }
    let mut state_tag = Compound::new();
    state_tag.insert("Name".into(), Tag::String(state.name.as_str().into()));
    if !properties.is_empty() {
        state_tag.insert("Properties".into(), Tag::Compound(properties));
    }
    let mut block = Compound::new();
    block.insert("BlockState".into(), Tag::Compound(state_tag));
    block.insert(
        "Pos".into(),
        Tag::IntArray((0..3).map(|i| world[i] - anchor[i]).collect()),
    );
    if let Some(entity) = mod_entity(game, world) {
        block.insert("Entity".into(), Tag::Compound(entity.nbt.clone()));
        block.insert(
            "Items".into(),
            Tag::List(
                entity
                    .items
                    .iter()
                    .enumerate()
                    .filter_map(|(slot, stack)| {
                        let Tag::Compound(mut tag) = encode(stack.as_ref()?) else {
                            return None;
                        };
                        tag.insert("Slot".into(), Tag::Int(slot as i32));
                        Some(Tag::Compound(tag))
                    })
                    .collect(),
            ),
        );
    } else {
        let key = (world[0], world[1], world[2]);
        if let Some(entity) = game.world.block_entities.get(&key) {
            let nbt = horizon_client::save::encode_block_entity(key, entity, &state.name);
            block.insert("VanillaEntity".into(), nbt);
        }
    }
    Some(block)
}

pub(super) fn capture(game: &Game<'_>, bearing: [i32; 3], anchor: [i32; 3]) -> Vec<Compound> {
    capture_attached(game, bearing, anchor, None)
}

pub(super) fn capture_attached(
    game: &Game<'_>,
    bearing: [i32; 3],
    anchor: [i32; 3],
    attached: Option<[i32; 3]>,
) -> Vec<Compound> {
    capture_from(
        game,
        bearing,
        anchor,
        std::iter::once(anchor).chain(attached),
    )
}

pub(super) fn capture_from(
    game: &Game<'_>,
    controller: [i32; 3],
    anchor: [i32; 3],
    sources: impl IntoIterator<Item = [i32; 3]>,
) -> Vec<Compound> {
    capture_excluding(game, controller, anchor, sources, [])
}

pub(super) fn capture_excluding(
    game: &Game<'_>,
    controller: [i32; 3],
    anchor: [i32; 3],
    sources: impl IntoIterator<Item = [i32; 3]>,
    excluded: impl IntoIterator<Item = [i32; 3]>,
) -> Vec<Compound> {
    let glued = glue(game);
    let uses_chassis = matches!(game.native_block(controller).as_str(),
        "create:mechanical_bearing" | WINDMILL | super::create_clockwork::CLOCKWORK);
    let mut seen: BTreeSet<_> = std::iter::once(controller).chain(excluded).collect();
    let mut next: VecDeque<_> = sources.into_iter().collect();
    let mut blocks = Vec::new();
    while let Some(world) = next.pop_front() {
        if !seen.insert(world) {
            continue;
        }
        let Some(block) = saved_block(game, world, anchor) else {
            continue;
        };
        blocks.push(block);
        super::create_sticker::collect(game, world, &mut next);
        if uses_chassis {
            super::create_linear_chassis::collect(game, world, controller, &mut next);
        }
        for side in Direction::ALL {
            let other = offset(world, side.normal());
            let state = game.world.block(other[0], other[1], other[2]);
            let attached = game.pack.assets.registry.state(state).is_some_and(|block| {
                matches!(
                    block.name.as_str(),
                    super::create_roller::ROLLER
                        | super::create_plough::PLOUGH
                        | super::create_harvester::HARVESTER
                ) && facing(game, state) == Some(side)
            });
            if attached
                || super::create_sail::attaches(game, other, side.opposite())
                || glued
                    .iter()
                    .any(|area| area.contains(world) && area.contains(other))
            {
                next.push_back(other);
            }
        }
    }
    blocks
}

pub(super) fn relative(block: &Compound) -> [i32; 3] {
    match block.get(&"Pos".into()) {
        Some(Tag::IntArray(pos)) => pos.as_slice().try_into().unwrap_or([0; 3]),
        _ => [0; 3],
    }
}

pub(super) fn rotate(v: [f64; 3], axis: usize, angle: f64) -> [f64; 3] {
    let a = (axis + 1) % 3;
    let b = (axis + 2) % 3;
    let (sin, cos) = angle.sin_cos();
    let mut moved = v;
    moved[a] = v[a] * cos - v[b] * sin;
    moved[b] = v[a] * sin + v[b] * cos;
    moved
}

pub(super) fn display(
    game: &mut Game<'_>,
    anchor: [i32; 3],
    block: &mut Compound,
    axis: usize,
    angle: f64,
) {
    let Some(saved_state) = compound(block, "BlockState") else {
        return;
    };
    if super::create_train_portable_visuals::has_bearing_pose(block)
        && let Some(kind) = super::create_machines::string(saved_state, "Name")
        && super::create_portable_interface::is_port(&kind)
    {
        let base = display_pose(block, axis, angle);
        draw_bearing_port(game, anchor, block, saved_state.clone(), &kind, base);
        return;
    }
    let dimension = game.native_dimension();
    let id = int(block, "Display")
        .map(|id| id as u32)
        .filter(|id| {
            game.others
                .iter()
                .any(|other| other.id == *id && other.kind == "minecraft:block_display")
        })
        .or_else(|| {
            let mut rendered = super::create_elevator_doors::display_state(block, saved_state);
            super::create_train_portable_visuals::retracted_display(&mut rendered);
            let mut data = Compound::from([("block_state".into(), Tag::Compound(rendered))]);
            // The otherwise invisible glow override identifies this internal
            // contraption proxy on clients; ordinary BlockDisplays stay vanilla.
            if super::create_machines::string(saved_state, "Name").as_deref() == Some(super::create_sticker::STICKER) {
                data.insert("glow_color_override".into(), Tag::Int(0x43535452));
            }
            game.native_summon(
                dimension,
                "minecraft:block_display",
                anchor.map(f64::from),
                data,
            )
        });
    let Some(id) = id else { return };
    block.insert("Display".into(), Tag::Int(id as i32));
    let _ = game.native_set_display(dimension, id, &display_pose(block, axis, angle));
}

const PORT_DISPLAYS: [(&str, &str); 3] = [
    ("Display", "DisplayUuid"),
    ("PortCollarDisplay", "PortCollarUuid"),
    ("PortTipDisplay", "PortTipUuid"),
];

fn port_display_id(
    game: &Game<'_>,
    anchor: [i32; 3],
    block: &Compound,
    part: usize,
) -> Option<u32> {
    let (id_key, uuid_key) = PORT_DISPLAYS[part];
    let cached = int(block, id_key).map(|id| id as u32);
    let origin = anchor.map(f64::from);
    let candidates = game.others.iter().filter(|display| {
        display.kind == "minecraft:block_display"
            && [display.position.x, display.position.y, display.position.z] == origin
    });
    if let Some(Tag::IntArray(uuid)) = block.get(&uuid_key.into()) {
        let same = |id| {
            game.persist
                .uuid_of(id)
                .is_some_and(|id| id.as_slice() == uuid.as_slice())
        };
        if let Some(id) = cached
            && same(id)
            && candidates.clone().any(|display| display.id == id)
        {
            return Some(id);
        }
        return candidates.map(|display| display.id).find(|&id| same(id));
    }
    // A bearing saved before the animated model has one body display.
    let id = cached?;
    candidates
        .filter(|display| display.id == id)
        .filter(|_| {
            let Some(Tag::Compound(data)) = game.persist.raw.get(&id) else {
                return false;
            };
            let Some(state) = data
                .get(&"block_state".into())
                .and_then(|tag| game.state_from_nbt(tag))
            else {
                return false;
            };
            game.pack
                .assets
                .registry
                .state(state)
                .is_some_and(|state| super::create_portable_interface::is_port(&state.name))
        })
        .map(|display| display.id)
        .next()
}

fn draw_bearing_port(
    game: &mut Game<'_>,
    anchor: [i32; 3],
    block: &mut Compound,
    state: Compound,
    kind: &str,
    base: NativeDisplay,
) {
    let mut parts = Vec::with_capacity(PORT_DISPLAYS.len());
    super::create_train_portable_visuals::draw_carriage_port(
        kind,
        block,
        state,
        glam::Quat::from_array(base.left_rotation),
        &mut |part, state, pose| parts.push((part as usize, state.clone(), pose)),
    );
    let dimension = game.native_dimension();
    for (index, state, mut pose) in parts {
        let state = Tag::Compound(state);
        let id = port_display_id(game, anchor, block, index).or_else(|| {
            game.native_summon(
                dimension,
                "minecraft:block_display",
                anchor.map(f64::from),
                Compound::from([("block_state".into(), state.clone())]),
            )
        });
        let Some(id) = id else { continue };
        if let Some(Tag::Compound(data)) = game.persist.raw.get_mut(&id)
            && data.get(&"block_state".into()) != Some(&state)
        {
            data.insert("block_state".into(), state);
        }
        for (axis, offset) in base.translation.into_iter().enumerate() {
            pose.translation[axis] += offset;
        }
        pose.teleport = 0;
        game.native_set_display(dimension, id, &pose);
        let (id_key, uuid_key) = PORT_DISPLAYS[index];
        block.insert(id_key.into(), Tag::Int(id as i32));
        let uuid = game.uuid_for(id);
        if !matches!(block.get(&uuid_key.into()), Some(Tag::IntArray(old)) if old.as_slice() == uuid.as_slice())
        {
            block.insert(uuid_key.into(), Tag::IntArray(uuid.to_vec()));
        }
    }
}

fn display_pose(block: &Compound, axis: usize, angle: f64) -> NativeDisplay {
    let (sin, cos) = (angle / 2.0).sin_cos();
    let mut rotation = [0.0, 0.0, 0.0, cos as f32];
    rotation[axis] = sin as f32;
    let near = relative(block).map(|i| f64::from(i) - 0.5);
    let translation = rotate(near, axis, angle).map(|value| (value + 0.5) as f32);
    NativeDisplay {
        translation,
        left_rotation: rotation,
        interpolation: 1,
        ..NativeDisplay::default()
    }
}

fn dump(game: &mut Game<'_>, anchor: [i32; 3], block: &mut Compound, axis: usize, angle: f64) {
    let id = compound(block, "BlockState").and_then(|state| match state.get(&"Name".into()) {
        Some(Tag::String(name)) => Some(name.to_string_lossy()),
        _ => None,
    });
    if id.as_deref() != Some("create:basin") {
        return;
    }
    let normal = rotate([0.0, 1.0, 0.0], axis, angle);
    if normal[1] >= -normal[0].abs().max(normal[2].abs()) {
        return;
    }
    let Some(Tag::List(stacks)) = block.remove(&"Items".into()) else {
        return;
    };
    let center = rotate(relative(block).map(f64::from), axis, angle);
    let pos = std::array::from_fn(|i| f64::from(anchor[i]) + 0.5 + center[i]);
    for stack in stacks {
        if let Tag::Compound(tag) = stack
            && let Some(item) = ItemStack::from_nbt(&tag)
        {
            game.add_item_entity(item, pos, Some(normal.map(|value| value * 0.05)), 10);
        }
    }
}

fn rotated_state(
    game: &mut Game<'_>,
    state: BlockStateId,
    axis: usize,
    angle: f64,
) -> BlockStateId {
    if let Some(rotated) = super::create_linear_chassis::rotated(game, state, axis, angle) {
        return rotated;
    }
    if game
        .pack
        .assets
        .registry
        .state(state)
        .is_some_and(|block| block.name == GEARBOX)
        && let Some(original) = game.native_block_state_property(state, "axis").and_then(axis_index)
    {
        let mut normal = [0.0; 3];
        normal[original] = 1.0;
        let rotated = rotate(normal, axis, angle);
        if let Some(along) = rotated.iter().position(|coordinate| coordinate.abs() > 0.5) {
            let name = ["x", "y", "z"][along];
            return game
                .with_level(|_, level, _| level.native_state_with_property(state, "axis", name))
                .unwrap_or(state);
        }
    }
    let Some(face) = facing(game, state) else {
        return state;
    };
    let normal =
        rotate(face.normal().map(f64::from), axis, angle).map(|component| component.round() as i32);
    let Some(rotated) = Direction::ALL.into_iter().find(|d| d.normal() == normal) else {
        return state;
    };
    let name = match rotated {
        Direction::Up => "up",
        Direction::Down => "down",
        Direction::North => "north",
        Direction::South => "south",
        Direction::West => "west",
        Direction::East => "east",
    };
    game.with_level(|_, level, _| level.native_state_with_property(state, "facing", name))
        .unwrap_or(state)
}

pub(super) fn restore(
    game: &mut Game<'_>,
    anchor: [i32; 3],
    blocks: &[Compound],
    axis: usize,
    angle: f64,
) -> bool {
    let angle = (angle / std::f64::consts::FRAC_PI_2).round() * std::f64::consts::FRAC_PI_2;
    let targets: Vec<_> = blocks
        .iter()
        .map(|block| {
            let moved = rotate(relative(block).map(f64::from), axis, angle)
                .map(|coord| coord.round() as i32);
            offset(anchor, moved)
        })
        .collect();
    if targets.iter().any(|&pos| {
        !matches!(
            game.native_block(pos).as_str(),
            "minecraft:air" | "minecraft:water"
        )
    }) {
        return false;
    }
    let Some(states) = blocks
        .iter()
        .map(|block| game.state_from_nbt(block.get(&"BlockState".into())?))
        .collect::<Option<Vec<_>>>()
    else {
        return false;
    };
    let dimension = game.native_dimension();
    for ((block, pos), state) in blocks.iter().zip(targets).zip(states) {
        let state = rotated_state(game, state, axis, angle);
        let current = game.world.block(pos[0], pos[1], pos[2]);
        let fluid = game.res.behaviours().fluid(current);
        let water = fluid.kind() == horizon_world::fluid::FluidKind::Water && fluid.is_source();
        let state = game
            .with_level(|_, level, _| {
                level.native_state_with_property(
                    state,
                    "waterlogged",
                    if water { "true" } else { "false" },
                )
            })
            .unwrap_or(state);
        if game.native_set_block(dimension, pos, state, flags::UPDATE_ALL) {
            let tick = game.world.game_time;
            let restored_gearbox = game.native_with_mod_block_entity(pos, |target| {
                if let Some(data) = compound(block, "Entity") {
                    target.nbt = data.clone();
                }
                if let Some(Tag::List(items)) = block.get(&"Items".into()) {
                    for item in items {
                        let Tag::Compound(item) = item else { continue };
                        if let Some(slot) =
                            int(item, "Slot").and_then(|slot| target.items.get_mut(slot as usize))
                        {
                            *slot = ItemStack::from_nbt(item);
                        }
                    }
                }
                if target.id == GEARBOX {
                    reset_moved_gearbox(target, tick);
                    true
                } else {
                    false
                }
            });
            if restored_gearbox == Some(true) {
                game.native_block_entity_sync(pos);
            }
            if let Some(data) = block.get(&"VanillaEntity".into()) {
                game.set_block_entity_checked(pos, data.clone());
            }
            if super::create_train_portable_visuals::has_bearing_pose(block) {
                for part in 0..PORT_DISPLAYS.len() {
                    if let Some(id) = port_display_id(game, anchor, block, part) {
                        game.native_remove_entity(dimension, id);
                    }
                }
            } else if let Some(id) = int(block, "Display") {
                game.native_remove_entity(dimension, id as u32);
            }
            if let Some(id) = int(block, "ControlHitbox") {
                game.native_remove_entity(dimension, id as u32);
            }
        }
    }
    true
}

pub(super) fn is_cargo(name: &str) -> bool {
    matches!(
        name,
        "minecraft:barrel"
            | "minecraft:chest"
            | "minecraft:trapped_chest"
            | "minecraft:shulker_box"
            | "create:item_vault"
    ) || name.ends_with("_shulker_box")
}

pub(super) fn cargo_items(block: &mut Compound) -> Option<(&mut Vec<Tag>, usize)> {
    let name = super::create_machines::string(compound(block, "BlockState")?, "Name")?;
    if !is_cargo(&name) {
        return None;
    }
    let (data, slots) = if name == "create:item_vault" {
        (block, super::create_vault::SLOTS)
    } else {
        let Some(Tag::Compound(entity)) = block.get_mut(&"VanillaEntity".into()) else {
            return None;
        };
        (entity, 27)
    };
    let items = data
        .entry("Items".into())
        .or_insert_with(|| Tag::List(Vec::new()));
    match items {
        Tag::List(items) => Some((items, slots)),
        _ => None,
    }
}

pub(super) fn deposit(
    blocks: &mut [Compound],
    mut stack: ItemStack,
    limit: u32,
) -> Option<ItemStack> {
    for cargo in blocks {
        let Some((items, slots)) = cargo_items(cargo) else {
            continue;
        };
        for entry in items.iter_mut() {
            let Tag::Compound(tag) = entry else { continue };
            let Some(current) =
                ItemStack::from_nbt(tag).filter(|item| item.same_item_same_components(&stack))
            else {
                continue;
            };
            let added = stack.count.min(limit.saturating_sub(current.count));
            tag.insert("count".into(), Tag::Int((current.count + added) as i32));
            stack.count -= added;
            if stack.count == 0 {
                return None;
            }
        }
        let slot = (0..slots).find(|slot| {
            !items.iter().any(|entry| matches!(entry, Tag::Compound(data) if int(data, "Slot") == Some(*slot as i32)))
        });
        if let Some(slot) = slot
            && let Tag::Compound(mut tag) = encode(&stack)
        {
            tag.insert("Slot".into(), Tag::Byte(slot as i8));
            items.push(Tag::Compound(tag));
            return None;
        }
    }
    Some(stack)
}

fn mount_items(
    game: &Game<'_>,
    anchor: [i32; 3],
    blocks: &mut [Compound],
    items: &mut Vec<Option<ItemStack>>,
) {
    for block in blocks {
        let [x, y, z] = offset(anchor, relative(block));
        let name = game.native_block([x, y, z]);
        if !is_cargo(&name) {
            continue;
        }
        let Some(source) = game.world.block_entities.get(&(x, y, z)) else {
            continue;
        };
        let slots = source.slots();
        let range = items.len() as i32..(items.len() + slots.len()) as i32;
        block.insert(
            "CargoRange".into(),
            Tag::IntArray(vec![range.start, range.end]),
        );
        items.extend_from_slice(slots);
        if let Some(Tag::Compound(vanilla)) = block.get_mut(&"VanillaEntity".into()) {
            vanilla.remove(&"Items".into());
        } else {
            block.remove(&"Items".into());
        }
    }
}

fn load_items(entity: &mut ModBlockEntity, blocks: &[Compound]) {
    let count = blocks
        .iter()
        .filter_map(|block| match block.get(&"CargoRange".into()) {
            Some(Tag::IntArray(range)) => range
                .get(1)
                .copied()
                .and_then(|end| usize::try_from(end).ok()),
            _ => None,
        })
        .max()
        .unwrap_or(0);
    let Some(Tag::List(cargo)) = entity.nbt.remove(&"MountedItems".into()) else {
        return;
    };
    entity.items.resize(count, None);
    for tag in cargo {
        let Tag::Compound(item) = tag else { continue };
        if let Some(target) =
            int(&item, "Slot").and_then(|slot| entity.items.get_mut(slot as usize))
        {
            *target = ItemStack::from_nbt(&item);
        }
    }
}

fn unmount_items(blocks: &mut [Compound], items: &[Option<ItemStack>]) {
    for block in blocks {
        let Some(Tag::IntArray(range)) = block.get(&"CargoRange".into()) else {
            continue;
        };
        let &[start, end] = range.as_slice() else {
            continue;
        };
        let Some(slots) = items.get(start as usize..end as usize) else {
            continue;
        };
        if let Some(Tag::Compound(vanilla)) = block.get_mut(&"VanillaEntity".into()) {
            vanilla.insert("Items".into(), horizon_client::save::encode_items(slots));
        } else {
            let entries = slots
                .iter()
                .enumerate()
                .filter_map(|(i, slot)| {
                    let Tag::Compound(mut item) = encode(slot.as_ref()?) else {
                        return None;
                    };
                    item.insert("Slot".into(), Tag::Int(i as i32));
                    Some(Tag::Compound(item))
                })
                .collect();
            block.insert("Items".into(), Tag::List(entries));
        }
    }
}

fn farm(
    game: &mut Game<'_>,
    blocks: &[Compound],
    entity: &mut ModBlockEntity,
    anchor: [i32; 3],
    axis: usize,
    previous: f32,
    angle: f32,
) {
    use super::{create_contraption_controls::disabled, create_harvester, create_plough};
    for block in blocks {
        let Some(state) = block
            .get(&"BlockState".into())
            .and_then(|tag| game.state_from_nbt(tag))
        else {
            continue;
        };
        let name = game.res.facts().get(state).name.as_ref();
        if !matches!(name, create_plough::PLOUGH | create_harvester::HARVESTER)
            || disabled(&entity.nbt, name)
        {
            continue;
        }
        let plough = name == create_plough::PLOUGH;
        let Some(face) = facing(game, state) else {
            continue;
        };
        let normal = face.normal().map(f64::from);
        let local = relative(block);
        let point = |angle: f32| {
            let point = std::array::from_fn(|i| f64::from(local[i]) + normal[i] * 0.45);
            let rotated = rotate(point, axis, f64::from(angle).to_radians());
            std::array::from_fn::<_, 3, _>(|i| f64::from(anchor[i]) + 0.5 + rotated[i])
        };
        let (before, now) = (point(previous), point(angle));
        let at = now.map(|v| v.floor() as i32);
        if at == before.map(|v| v.floor() as i32) {
            continue;
        }
        let direction = rotate(normal, axis, f64::from(angle).to_radians());
        let forward = (0..3)
            .map(|i| (now[i] - before[i]) * direction[i])
            .sum::<f64>();
        if forward < 0.0 {
            continue;
        }
        if plough {
            create_plough::till(game, at);
        } else {
            for stack in create_harvester::cut(game, at) {
                if let Some(rest) = create_harvester::store(game, &mut entity.items, stack) {
                    game.pop_resource(at, rest);
                }
            }
        }
    }
}

pub(super) fn tick(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    rpm: f32,
    source_ticked: bool,
    sequenced_angle: Option<f64>,
) {
    let Some(face) = facing(game, game.world.block(pos[0], pos[1], pos[2])) else {
        return;
    };
    let normal = face.normal();
    let Some(axis) = normal.iter().position(|&step| step != 0) else {
        return;
    };
    let anchor = offset(pos, normal);
    let mut angle = float(&entity.nbt, "Angle").unwrap_or(0.0);
    let mut blocks = match entity.nbt.remove(&"MovedBlocks".into()) {
        Some(Tag::List(blocks)) => blocks
            .into_iter()
            .filter_map(|tag| match tag {
                Tag::Compound(block) => Some(block),
                _ => None,
            })
            .collect(),
        _ => Vec::new(),
    };
    load_items(entity, &blocks);
    let was_running = !blocks.is_empty();
    let previous_rpm = float(&entity.nbt, "BearingRPM").unwrap_or(0.0);
    let ended_sequence = rpm == 0.0
        && previous_rpm != 0.0
        && matches!(entity.nbt.get(&"SequencedAngleLimit".into()),
            Some(Tag::Double(bits)) if f64::from_bits(*bits) >= 0.0);
    if rpm != previous_rpm {
        if was_running
            && previous_rpm != 0.0
            && (rpm == 0.0 || rpm.signum() != previous_rpm.signum())
            && int(&entity.nbt, "Stalled") != Some(1)
        {
            angle = (angle + 0.5).floor();
        }
        entity.nbt.insert(
            "SequencedAngleLimit".into(),
            Tag::Double(sequenced_angle.unwrap_or(-1.0).to_bits()),
        );
        set_float(&mut entity.nbt, "BearingRPM", rpm);
    }
    let scheduled = source_ticked || int(&entity.nbt, "AssembleNextTick") == Some(1);
    if blocks.is_empty() {
        entity
            .nbt
            .insert("AssembleNextTick".into(), Tag::Byte(i8::from(rpm != 0.0)));
    }
    if blocks.is_empty() && rpm != 0.0 && scheduled {
        blocks = capture(game, pos, anchor);
        let attached: Vec<_> = blocks
            .iter()
            .map(|block| offset(anchor, relative(block)))
            .collect();
        let glue = attached_glue(game, &attached, anchor);
        if !glue.is_empty() {
            entity.nbt.insert("AttachedGlue".into(), Tag::List(glue));
        }
        entity.items.clear();
        mount_items(game, anchor, &mut blocks, &mut entity.items);
        if let Some(air) = game.native_default_state("minecraft:air") {
            for block in &blocks {
                game.native_set_block(
                    game.native_dimension(),
                    offset(anchor, relative(block)),
                    air,
                    flags::UPDATE_ALL | flags::UPDATE_SKIP_BLOCK_ENTITY_SIDEEFFECTS,
                );
            }
        }
    }
    if !blocks.is_empty() {
        let physical_angle = f64::from(angle).to_radians();
        let can_place = match int(&entity.nbt, "ScrollValue").unwrap_or(0) {
            1 => angle.abs() < 22.5 || angle.abs() > 337.5,
            2 => false,
            _ => true,
        };
        let stopping = rpm == 0.0 && can_place && !ended_sequence;
        if stopping {
            unmount_items(&mut blocks, &entity.items);
        }
        if stopping && restore(game, anchor, &blocks, axis, physical_angle) {
            super::create_portable_interface::bearing_stopped(game, pos, &blocks);
            if let Some(Tag::List(glue)) = entity.nbt.remove(&"AttachedGlue".into()) {
                rotate_glue(game, &glue, anchor, axis, physical_angle);
            }
            blocks.clear();
            entity.items.clear();
            entity.nbt.remove(&"Stalled".into());
            entity.nbt.remove(&"ActorAngle".into());
            entity.nbt.remove(&"DisabledActors".into());
            entity.nbt.remove(&"AssembleNextTick".into());
            angle = 0.0;
        } else {
            if was_running && rpm != 0.0 {
                let previous = float(&entity.nbt, "ActorAngle").unwrap_or(0.0);
                super::create_mounted_dispenser::rotate_actors(
                    game,
                    &mut blocks,
                    &mut entity.items,
                    anchor,
                    face,
                    axis,
                    previous,
                    angle,
                );
                farm(game, &blocks, entity, anchor, axis, previous, angle);
                set_float(&mut entity.nbt, "ActorAngle", angle);
            }
            for block in &mut blocks {
                dump(game, anchor, block, axis, physical_angle);
            }
            let sequence_just_started =
                was_running && previous_rpm == 0.0 && sequenced_angle.is_some();
            if !sequence_just_started && int(&entity.nbt, "Stalled") != Some(1) {
                let mut speed = rpm * 360.0 / 60.0 / 20.0;
                if let Some(Tag::Double(bits)) = entity.nbt.get(&"SequencedAngleLimit".into()) {
                    let limit = f64::from_bits(*bits);
                    if limit >= 0.0 {
                        speed = f64::from(speed).clamp(-limit, limit) as f32;
                        entity.nbt.insert(
                            "SequencedAngleLimit".into(),
                            Tag::Double((limit - f64::from(speed.abs())).max(0.0).to_bits()),
                        );
                    }
                }
                angle = (angle + speed) % 360.0;
            }
            let stalled = super::create_portable_interface::update_bearing(
                game,
                pos,
                anchor,
                &mut blocks,
                axis,
                physical_angle,
                f64::from(angle).to_radians(),
            );
            entity
                .nbt
                .insert("Stalled".into(), Tag::Byte(i8::from(stalled)));
            for block in &mut blocks {
                display(game, anchor, block, axis, f64::from(angle).to_radians());
                super::create_contraption_controls::position(
                    game,
                    pos,
                    anchor,
                    block,
                    axis,
                    f64::from(angle).to_radians(),
                );
            }
        }
    }
    entity
        .nbt
        .insert("Running".into(), Tag::Byte(i8::from(!blocks.is_empty())));
    set_float(&mut entity.nbt, "Angle", angle);
    if !blocks.is_empty() {
        entity.nbt.insert(
            "MovedBlocks".into(),
            Tag::List(blocks.into_iter().map(Tag::Compound).collect()),
        );
    }
}

pub(super) const WINDMILL: &str = "create:windmill_bearing";
pub(super) const WINDMILL_TOP: &str = "create:block/bearing/top_wooden";

pub(super) fn windmill_place(
    level: &super::GameLevel<'_>,
    state: BlockStateId,
    context: &horizon_world::level::PlacementContext,
) -> Option<Option<BlockStateId>> {
    let name = level.native_state_block(state)?;
    let looking = context.nearest_looking_direction();
    if matches!(name, "create:cuckoo_clock" | "create:mysterious_cuckoo_clock") {
        use horizon_core::geometry::Direction;
        let preferred = super::create_hand_crank::preferred_in_directions(
            level, context.pos, [Direction::North, Direction::South, Direction::West, Direction::East],
        );
        let yaw = (f64::from(context.yaw) / 90.0 + 0.5).floor() as i64 & 3;
        let horizontal = [Direction::South, Direction::West, Direction::North, Direction::East][yaw as usize];
        let face = preferred.unwrap_or_else(|| horizontal.opposite());
        return Some(level.native_state_with_property(state, "facing", super::create_fluids::name(face)));
    }
    let face = match name {
        WINDMILL | super::create_clockwork::CLOCKWORK if !context.sneaking => super::create_hand_crank::preferred_direction(level, context.pos)
            .unwrap_or_else(|| looking.opposite()),
        WINDMILL | super::create_clockwork::CLOCKWORK => looking,
        "create:sail_frame" | "create:white_sail" | "create:red_sail" => {
            if context.sneaking { looking.opposite() } else { looking }
        }
        _ => return None,
    };
    let facing = super::create_fluids::name(face);
    Some(level.native_state_with_property(state, "facing", facing))
}

pub(super) fn windmill_generated(nbt: &Compound) -> f32 {
    float(nbt, "LastGenerated").unwrap_or(0.0)
}

fn with_windmill(
    game: &mut Game<'_>,
    pos: [i32; 3],
    action: impl FnOnce(&mut Game<'_>, &mut ModBlockEntity),
) {
    let key = (pos[0], pos[1], pos[2]);
    let Some(mut entry) = game.world.block_entities.remove(&key) else {
        return;
    };
    if let crate::containers::BlockEntity::Mod(mill) = &mut entry
        && mill.id == WINDMILL
    {
        action(game, mill);
        game.world.modified.insert((key.0 >> 4, key.2 >> 4));
    }
    game.world.block_entities.insert(key, entry);
}

fn windmill_blocks(mill: &mut ModBlockEntity) -> Vec<Compound> {
    match mill.nbt.remove(&"MovedBlocks".into()) {
        Some(Tag::List(blocks)) => blocks
            .into_iter()
            .filter_map(|block| match block {
                Tag::Compound(data) => Some(data),
                _ => None,
            })
            .collect(),
        _ => Vec::new(),
    }
}

fn save_windmill_blocks(mill: &mut ModBlockEntity, blocks: Vec<Compound>) {
    mill.nbt.insert(
        "MovedBlocks".into(),
        Tag::List(blocks.into_iter().map(Tag::Compound).collect()),
    );
}

pub(super) fn resolve_saved_display(
    game: &Game<'_>,
    anchor: [i32; 3],
    block: &mut Compound,
    axis: usize,
    angle: f64,
) {
    let key = "Display".into();
    let old_id = int(block, "Display");
    block.remove(&key);
    let origin = anchor.map(f64::from);
    let mut candidates = game.others.iter().filter(|entity| {
        entity.kind == "minecraft:block_display"
            && [entity.position.x, entity.position.y, entity.position.z] == origin
    });
    let display = if let Some(Tag::IntArray(uuid)) = block.get(&"DisplayUuid".into()) {
        candidates
            .find(|entity| {
                game.persist
                    .uuid_of(entity.id)
                    .is_some_and(|known| known.as_slice() == uuid.as_slice())
            })
            .map(|entity| entity.id)
    } else if old_id.is_some() {
        // Earlier saves recorded a session-local ID. Find the blade at its
        // saved pose, since reloading can give the ID to another entity.
        let Some(state) = compound(block, "BlockState") else {
            return;
        };
        let expected = super::create_elevator_doors::display_state(block, state);
        let Some(expected) = game.state_from_nbt(&Tag::Compound(expected)) else {
            return;
        };
        let pose = display_pose(block, axis, angle);
        candidates
            .find(|entity| {
                let Some(data) = game.persist.raw.get(&entity.id) else {
                    return false;
                };
                let Some((translation, rotation, _, _)) = data
                    .get("transformation")
                    .and_then(horizon_client::text_display::transformation)
                else {
                    return false;
                };
                data.get("block_state")
                    .and_then(|state| game.state_from_nbt(state))
                    == Some(expected)
                    && translation == pose.translation
                    && rotation == pose.left_rotation
            })
            .map(|entity| entity.id)
    } else {
        None
    };
    if let Some(id) = display {
        block.insert(key, Tag::Int(id as i32));
    }
}

pub(super) fn show_saved_displays(
    game: &mut Game<'_>,
    anchor: [i32; 3],
    blocks: &mut [Compound],
    axis: usize,
    previous_angle: f32,
    angle: f32,
) {
    for block in blocks.iter_mut() {
        resolve_saved_display(
            game,
            anchor,
            block,
            axis,
            f64::from(previous_angle).to_radians(),
        );
    }
    for block in blocks {
        display(game, anchor, block, axis, f64::from(angle).to_radians());
        if let Some(id) = int(block, "Display") {
            let uuid = game.uuid_for(id as u32);
            block.insert("DisplayUuid".into(), Tag::IntArray(uuid.to_vec()));
        }
    }
}

fn windmill_sound(game: &mut Game<'_>, pos: [i32; 3], assembling: bool) {
    let at = pos.map(|coord| f64::from(coord) + 0.5);
    if assembling {
        game.native_play_sound_in_place("create:contraption_assemble", at, 4, 0.5, 0.5);
        game.native_play_sound_in_place("create:contraption_assemble_compounded_1", at, 4, 0.045, 0.74);
    } else {
        game.native_play_sound_in_place("create:contraption_disassemble", at, 4, 0.35, 0.75);
    }
}

fn windmill_geometry(game: &Game<'_>, pos: [i32; 3]) -> Option<(Direction, usize, [i32; 3])> {
    let face = facing(game, game.world.block(pos[0], pos[1], pos[2]))?;
    let normal = face.normal();
    let axis = normal.iter().position(|&step| step != 0)?;
    Some((face, axis, offset(pos, normal)))
}

fn windmill_rpm(mill: &ModBlockEntity) -> f32 {
    let count = int(&mill.nbt, "Sails").unwrap_or(0);
    if int(&mill.nbt, "Running") != Some(1) {
        return 0.0;
    }
    let sign = if int(&mill.nbt, "ScrollValue") == Some(1) { -1.0 } else { 1.0 };
    (count / 8).clamp(1, 16) as f32 * sign
}

fn windmill_direction(game: &mut Game<'_>, pos: [i32; 3], mill: &mut ModBlockEntity) {
    let previous = windmill_generated(&mill.nbt);
    let speed = windmill_rpm(mill);
    if previous == speed {
        return;
    }
    if previous != 0.0 && speed != 0.0 && previous.signum() != speed.signum() {
        let prior = float(&mill.nbt, "Angle").unwrap_or(0.0);
        let angle = (prior + 0.5).floor();
        set_float(&mut mill.nbt, "Angle", angle);
        if let Some((_, axis, anchor)) = windmill_geometry(game, pos) {
            let mut blocks = windmill_blocks(mill);
            show_saved_displays(game, anchor, &mut blocks, axis, prior, angle);
            save_windmill_blocks(mill, blocks);
        }
    }
    set_float(&mut mill.nbt, "LastGenerated", speed);
    super::create_machines::refresh_windmill_network(game, pos, mill);
}

pub(super) fn windmill_setting(game: &mut Game<'_>, pos: [i32; 3], value: i32) {
    with_windmill(game, pos, |game, mill| {
        let value = value.clamp(0, 1);
        if int(&mill.nbt, "ScrollValue").unwrap_or(0) == value {
            return;
        }
        mill.nbt.insert("ScrollValue".into(), Tag::Int(value));
        windmill_direction(game, pos, mill);
        let at = pos.map(|coordinate| f64::from(coordinate) + 0.5);
        game.native_play_sound_in_place("minecraft:entity.item_frame.add_item", at, 4, 0.25, 2.0);
        game.native_play_sound_in_place("minecraft:block.note_block.iron_xylophone", at, 4, 0.03, 1.125);
        game.native_block_entity_sync(pos);
    });
}

pub(super) fn windmill_loaded(game: &mut Game<'_>, pos: [i32; 3]) {
    if game.native_block(pos) == WINDMILL {
        with_windmill(game, pos, |game, mill| windmill_direction(game, pos, mill));
    }
}

pub(super) fn windmill_click(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.native_block(pos) != WINDMILL
        || !game.may_build()
        || game.native_sneaking()
        || game.held().is_some()
    {
        return false;
    }
    if game.hand != horizon_client::first_person::Hand::Main {
        return true;
    }
    let Some((_, axis, anchor)) = windmill_geometry(game, pos) else {
        return false;
    };
    with_windmill(game, pos, |game, mill| {
        if int(&mill.nbt, "Running") != Some(1) {
            mill.nbt.insert("AssembleNextTick".into(), Tag::Byte(1));
            return;
        }
        let mut blocks = windmill_blocks(mill);
        let angle = f64::from(float(&mill.nbt, "Angle").unwrap_or(0.0)).to_radians();
        for block in &mut blocks {
            resolve_saved_display(game, anchor, block, axis, angle);
        }
        load_items(mill, &blocks);
        unmount_items(&mut blocks, &mill.items);
        if !restore(game, anchor, &blocks, axis, 0.0) {
            save_windmill_blocks(mill, blocks);
            return;
        }
        if let Some(Tag::List(glue)) = mill.nbt.remove(&"AttachedGlue".into()) {
            rotate_glue(game, &glue, anchor, axis, 0.0);
        }
        mill.items.clear();
        mill.nbt.insert("Running".into(), Tag::Byte(0));
        mill.nbt.insert("Sails".into(), Tag::Int(0));
        set_float(&mut mill.nbt, "Angle", 0.0);
        windmill_direction(game, pos, mill);
        windmill_sound(game, pos, false);
    });
    game.native_block_entity_sync(pos);
    game.swing_arm();
    true
}

pub(super) fn windmill_advance(game: &mut Game<'_>, pos: [i32; 3], mill: &mut ModBlockEntity) {
    let Some((_, axis, anchor)) = windmill_geometry(game, pos) else {
        return;
    };
    if mill.nbt.remove(&"AssembleNextTick".into()) == Some(Tag::Byte(1)) {
        let mut blocks = capture(game, pos, anchor);
        let sails = blocks
            .iter()
            .filter(|block| {
                matches!(
                    compound(block, "BlockState").and_then(|state| state.get(&"Name".into())),
                    Some(Tag::String(name))
                        if game.items().block_in_tag("create:windmill_sails", &name.to_string_lossy())
                )
            })
            .count() as i32;
        if sails < 8 {
            if !blocks.is_empty() {
                mill.nbt.insert("NotEnoughSails".into(), Tag::Int(sails));
            }
            return;
        }
        let Some(air) = game.native_default_state("minecraft:air") else {
            return;
        };
        mill.nbt.remove(&"NotEnoughSails".into());
        let moved: Vec<_> = blocks
            .iter()
            .map(|block| offset(anchor, relative(block)))
            .collect();
        let glue = attached_glue(game, &moved, anchor);
        if !glue.is_empty() {
            mill.nbt.insert("AttachedGlue".into(), Tag::List(glue));
        }
        mill.items.clear();
        mount_items(game, anchor, &mut blocks, &mut mill.items);
        for block in moved {
            game.native_set_block(
                game.native_dimension(),
                block,
                air,
                flags::UPDATE_ALL | flags::UPDATE_SKIP_BLOCK_ENTITY_SIDEEFFECTS,
            );
        }
        mill.nbt.insert("Sails".into(), Tag::Int(sails));
        mill.nbt.insert("Running".into(), Tag::Byte(1));
        set_float(&mut mill.nbt, "Angle", 0.0);
        save_windmill_blocks(mill, blocks);
        windmill_direction(game, pos, mill);
        windmill_sound(game, pos, true);
    }
    if int(&mill.nbt, "Running") != Some(1) {
        return;
    }
    let prior = float(&mill.nbt, "Angle").unwrap_or(0.0);
    let speed = if super::create_machines::reading(mill, 0) == 0.0 {
        0.0
    } else {
        windmill_generated(&mill.nbt) * 360.0 / 60.0 / 20.0
    };
    let angle = (prior + speed) % 360.0;
    let mut blocks = windmill_blocks(mill);
    show_saved_displays(game, anchor, &mut blocks, axis, prior, angle);
    save_windmill_blocks(mill, blocks);
    set_float(&mut mill.nbt, "Angle", angle);
    game.native_block_entity_sync(pos);
}

pub(super) fn windmill_update_tag(mill: &ModBlockEntity) -> Compound {
    let mut visual = Compound::new();
    for name in ["Angle", "LastGenerated", "NotEnoughSails", "Running", "ScrollValue", "Speed"] {
        if let Some(value) = mill.nbt.get(&name.into()) {
            visual.insert(name.into(), value.clone());
        }
    }
    visual
}

pub(super) fn windmill_render(
    game: &Game<'_>,
    state: BlockStateId,
    mill: &ModBlockEntity,
    draw: &mut super::native_block_entity_draw::BlockEntityDraw,
) {
    let angle = float(&mill.nbt, "Angle").unwrap_or(0.0);
    let rpm = float(&mill.nbt, "Speed").unwrap_or(0.0);
    render_top(game, state, (angle, rpm), WINDMILL_TOP, draw);
}

pub(super) fn render_top(
    game: &Game<'_>,
    state: BlockStateId,
    (angle, rpm): (f32, f32),
    top: &str,
    draw: &mut super::native_block_entity_draw::BlockEntityDraw,
) {
    let Some(face) = facing(game, state) else {
        return;
    };
    let normal = face.normal().map(|component| component as f32);
    let center = [0.5; 3];
    let x = [1.0, 0.0, 0.0];
    let y = [0.0, 1.0, 0.0];
    let z = [0.0, 0.0, 1.0];
    draw.push();
    draw.rotate_about(normal.map(f32::abs), angle, center);
    match face {
        Direction::Up => {}
        Direction::Down => draw.rotate_about(x, 180.0, center),
        Direction::North => draw.rotate_about(x, -90.0, center),
        Direction::South => draw.rotate_about(x, 90.0, center),
        Direction::West => draw.rotate_about(z, 90.0, center),
        Direction::East => draw.rotate_about(z, -90.0, center),
    }
    game.native_draw_model(draw, top, 0xFFFFFF);
    draw.pop();
    draw.push();
    let shaft_angle = super::create_visuals::wheel_angle(draw.game_time, draw.partial, rpm, 0.0);
    draw.rotate_about(normal.map(f32::abs), shaft_angle, center);
    match face {
        Direction::Up => draw.rotate_about(x, 90.0, center),
        Direction::Down => draw.rotate_about(x, -90.0, center),
        Direction::North => {}
        Direction::South => draw.rotate_about(y, 180.0, center),
        Direction::West => draw.rotate_about(y, 90.0, center),
        Direction::East => draw.rotate_about(y, -90.0, center),
    }
    game.native_draw_model(draw, "create:block/shaft_half", 0xFFFFFF);
    draw.pop();
}
