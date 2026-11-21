use horizon_core::geometry::Direction;
use horizon_core::position::BlockPos;
use horizon_world::level::{LevelAccess, flags};
use horizon_world::nbt::{Compound, Tag};
use horizon_world::worldgen::structure::StructureTemplate;

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_machines::{int, offset, set_float, string};

pub(super) const CANNON: &str = "create:schematicannon";
pub(super) const SCHEMATIC: &str = "create:schematic";
const EMPTY: &str = "create:empty_schematic";
pub(super) const GUNPOWDER: &str = "minecraft:gunpowder";
const SHOTS_PER_GUNPOWDER: i32 = 400;
const SHOT_COOLDOWN: i32 = 10;

pub(super) fn new_tag() -> Compound {
    let mut tag = Compound::new();
    set_status(&mut tag, "STOPPED", "idle");
    tag
}

fn set_status(tag: &mut Compound, state: &str, status: &str) {
    tag.insert("State".into(), Tag::String(state.into()));
    tag.insert("Status".into(), Tag::String(status.into()));
}

fn xyz(tag: Option<&Tag>) -> Option<[i32; 3]> {
    let Some(Tag::IntArray(coordinates)) = tag else {
        return None;
    };
    coordinates.as_slice().try_into().ok()
}

fn within(pos: [i32; 3], at: [i32; 3], radius: f64) -> bool {
    (0..3)
        .map(|i| (f64::from(pos[i]) - f64::from(at[i])).powi(2))
        .sum::<f64>()
        < radius * radius
}

fn valid_id(id: &str) -> bool {
    let Some((namespace, path)) = id.split_once(':') else {
        return false;
    };
    !namespace.is_empty()
        && namespace.bytes().all(|byte| {
            byte.is_ascii_lowercase() || byte.is_ascii_digit() || b"_-.".contains(&byte)
        })
        && namespace != "."
        && namespace != ".."
        && path.split('/').all(|segment| {
            !segment.is_empty()
                && segment != "."
                && segment != ".."
                && segment.bytes().all(|byte| {
                    byte.is_ascii_lowercase() || byte.is_ascii_digit() || b"_-.".contains(&byte)
                })
        })
}

pub(super) fn valid_template_id(id: &str) -> bool {
    valid_id(id)
}

fn start(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
) -> Result<(), &'static str> {
    let data = entity
        .items
        .first()
        .and_then(Option::as_ref)
        .filter(|item| item.item.as_ref() == SCHEMATIC)
        .and_then(ItemStack::custom_data)
        .ok_or("schematicInvalid")?;
    let name = string(data, "Template")
        .filter(|name| valid_id(name))
        .ok_or("schematicInvalid")?;
    let anchor = xyz(data.get(&"Anchor".into())).ok_or("schematicNotPlaced")?;
    if !within(anchor, pos, 256.0) {
        return Err("targetOutsideRange");
    }
    let id = game.template_entry(&name).ok_or("schematicExpired")?;
    let transforms = game.state_transforms().ok_or("schematicErrored")?;
    let registry = game.pack.assets.registry;
    let template = StructureTemplate::from_nbt(&id.tag, registry, transforms);
    let palette = template.palettes().first().ok_or("schematicExpired")?;
    let mut blocks: Vec<_> = palette
        .blocks()
        .iter()
        .filter(|block| {
            registry
                .state(block.state)
                .is_some_and(|state| state.name != "minecraft:structure_void")
        })
        .collect();
    if blocks.is_empty() {
        return Err("schematicExpired");
    }
    blocks.sort_by_key(|block| (block.pos[1], block.pos[2], block.pos[0]));
    let queue: Vec<_> = blocks
        .iter()
        .filter_map(|block| {
            let state = registry.state(block.state)?;
            let target = anchor[0]
                .checked_add(block.pos[0])
                .zip(anchor[1].checked_add(block.pos[1]))
                .zip(anchor[2].checked_add(block.pos[2]))
                .map(|((x, y), z)| [x, y, z])?;
            let mut entry = Compound::new();
            entry.insert("Target".into(), Tag::IntArray(target.to_vec()));
            entry.insert(
                "Block".into(),
                Tag::compound([
                    ("id", Tag::String(state.name.as_str().into())),
                    (
                        "properties",
                        Tag::Compound(
                            state
                                .properties
                                .iter()
                                .map(|(k, v)| (k.as_str().into(), Tag::String(v.as_str().into())))
                                .collect(),
                        ),
                    ),
                ]),
            );
            // Java prepares safe block-entity data, never a raw saved inventory.
            // Full safe-writer support is separate; keep ordinary container names only.
            if let Some(data) = &block.nbt {
                let mut safe = if state.name.starts_with("create:")
                    && game
                        .native_block_name_in_tag(&state.name, "create:safe_nbt")
                        .unwrap_or(false)
                {
                    (**data).clone()
                } else {
                    Compound::new()
                };
                if let Some(name) = data.get(&"CustomName".into()) {
                    safe.insert("CustomName".into(), name.clone());
                }
                if !safe.is_empty() {
                    if let Some(id) = data.get(&"id".into()) {
                        safe.insert("id".into(), id.clone());
                    }
                    entry.insert("BlockEntity".into(), Tag::Compound(safe));
                }
            }
            Some(Tag::Compound(entry))
        })
        .collect();
    entity.nbt.insert(
        "AmountToPlace".into(),
        Tag::Int(
            blocks
                .iter()
                .filter(|block| !game.res.behaviours().is_air(block.state))
                .count() as i32,
        ),
    );
    entity.nbt.insert("Queue".into(), Tag::List(queue));
    entity.nbt.insert("Cursor".into(), Tag::Int(0));
    entity.nbt.insert("AmountPlaced".into(), Tag::Int(0));
    Ok(())
}

fn options(nbt: &Compound) -> Option<&Compound> {
    match nbt.get(&"Options".into()) {
        Some(Tag::Compound(tag)) => Some(tag),
        _ => None,
    }
}

fn clear_job(entity: &mut ModBlockEntity, finished: bool) {
    for field in ["Queue", "Cursor", "Cooldown", "MissingItem", "MissingCount"] {
        entity.nbt.remove(&field.into());
    }
    for field in ["AmountPlaced", "AmountToPlace"] {
        entity.nbt.insert(field.into(), Tag::Int(0));
    }
    set_float(&mut entity.nbt, "Progress", 0.0);
    if finished {
        if let [input, output, ..] = entity.items.as_mut_slice() {
            *input = None;
            let count = output.as_ref().map_or(1, |item| item.count + 1);
            *output = Some(ItemStack::new(EMPTY, count));
        }
        set_status(&mut entity.nbt, "STOPPED", "finished");
    }
}

fn mark_flight(game: &mut Game<'_>, entity: &mut ModBlockEntity) {
    let Some(Tag::List(flights)) = entity.nbt.remove(&"FlyingBlocks".into()) else {
        return;
    };
    let mut remaining = Vec::with_capacity(flights.len());
    for item in flights {
        let Tag::Compound(mut flight) = item else {
            continue;
        };
        let Some(target) = xyz(flight.get(&"Target".into())) else {
            continue;
        };
        let ticks = int(&flight, "TicksLeft").unwrap_or(0);
        if ticks > 0 {
            flight.insert("TicksLeft".into(), Tag::Int(ticks - 1));
            remaining.push(Tag::Compound(flight));
            continue;
        }
        if !game.world.loaded(target[0], target[2]) {
            remaining.push(Tag::Compound(flight));
            continue;
        }
        let state = flight
            .get(&"Block".into())
            .and_then(|tag| game.pack.assets.registry.saved_state_id(tag));
        if let Some(state) = state {
            game.native_set_block(game.native_dimension(), target, state, flags::UPDATE_ALL);
            if let Some(Tag::Compound(data)) = flight.remove(&"BlockEntity".into()) {
                game.with_level(|_, level, _| {
                    level.load_block_entity(BlockPos::new(target[0], target[1], target[2]), data);
                });
                game.native_block_entity_sync(target);
            }
        }
    }
    entity
        .nbt
        .insert("FlyingBlocks".into(), Tag::List(remaining));
}

fn take_adjacent(game: &mut Game<'_>, pos: [i32; 3], name: &str, count: u32) -> bool {
    // Plan the whole extraction first: a short supply must not eat partial inputs.
    let mut sources = Vec::new();
    let mut needed = count;
    let dim = game.native_dimension();
    for face in Direction::ALL {
        let at = offset(pos, face.normal());
        let face = face.opposite();
        let Some(slots) = game.native_container_slots(dim, at, face) else {
            continue;
        };
        for slot in slots {
            if slot.can_take {
                if let Some(stack) = slot
                    .stack
                    .as_ref()
                    .filter(|item| item.item.as_ref() == name)
                {
                    let take = needed.min(stack.count);
                    sources.push((at, face, slot.slot, take));
                    needed -= take;
                    if needed == 0 {
                        for (at, face, slot, count) in sources {
                            game.native_extract_item(dim, at, face, slot, count);
                        }
                        return true;
                    }
                }
            }
        }
    }
    false
}

fn ready_fuel(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    creative: bool,
) -> i32 {
    if creative {
        return 0;
    }
    let remaining = int(&entity.nbt, "RemainingFuel").unwrap_or(0);
    if remaining > 0 {
        return remaining;
    }
    if let Some(item) = entity
        .items
        .get_mut(4)
        .and_then(Option::as_mut)
        .filter(|item| item.item.as_ref() == GUNPOWDER)
    {
        item.count -= 1;
        if item.count == 0 {
            entity.items[4] = None;
        }
        SHOTS_PER_GUNPOWDER
    } else if take_adjacent(game, pos, GUNPOWDER, 1) {
        SHOTS_PER_GUNPOWDER
    } else {
        0
    }
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let had_flights =
        matches!(entity.nbt.get(&"FlyingBlocks".into()), Some(Tag::List(list)) if !list.is_empty());
    mark_flight(game, entity);
    let state = string(&entity.nbt, "State");
    if state.as_deref() != Some("RUNNING") {
        let resumable = matches!(
            string(&entity.nbt, "Status").as_deref(),
            Some("targetNotLoaded" | "missingBlock" | "noGunpowder")
        );
        if !resumable {
            if had_flights {
                game.native_block_entity_sync(pos);
            }
            return;
        }
    }
    if entity.items.first().and_then(Option::as_ref).is_none() {
        clear_job(entity, false);
        set_status(&mut entity.nbt, "STOPPED", "idle");
        game.native_block_entity_sync(pos);
        return;
    }
    if !entity.nbt.contains_key(&"Queue".into()) {
        if let Err(status) = start(game, pos, entity) {
            set_status(&mut entity.nbt, "STOPPED", status);
            game.native_block_entity_sync(pos);
            return;
        }
    }
    let creative = Direction::ALL.into_iter().any(|direction| {
        game.native_block(offset(pos, direction.normal())) == super::create_belt_funnel::CRATE
    });
    if !creative {
        let fuel = ready_fuel(game, pos, entity, false);
        entity.nbt.insert("RemainingFuel".into(), Tag::Int(fuel));
    }
    let cooldown = int(&entity.nbt, "Cooldown").unwrap_or(0);
    if cooldown > 0 {
        entity.nbt.insert("Cooldown".into(), Tag::Int(cooldown - 1));
        if had_flights {
            game.native_block_entity_sync(pos);
        }
        return;
    }
    let mut cursor = int(&entity.nbt, "Cursor").unwrap_or(0).max(0) as usize;
    loop {
        let Some(Tag::Compound(mut block)) = entity.nbt.get(&"Queue".into()).and_then(|queue| {
            if let Tag::List(entries) = queue {
                entries.get(cursor).cloned()
            } else {
                None
            }
        }) else {
            if creative {
                entity.nbt.insert("RemainingFuel".into(), Tag::Int(0));
            }
            clear_job(entity, true);
            break;
        };
        let target = xyz(block.get(&"Target".into())).unwrap_or(pos);
        let state = block
            .get(&"Block".into())
            .and_then(|tag| game.pack.assets.registry.saved_state_id(tag));
        let opts = options(&entity.nbt);
        let replace_entities = opts
            .and_then(|nbt| int(nbt, "replace_block_entities"))
            .unwrap_or(0)
            != 0;
        let skip_missing = opts.and_then(|nbt| int(nbt, "skip_missing")).unwrap_or(1) != 0;
        let mode = opts.and_then(|nbt| int(nbt, "replace_mode")).unwrap_or(2);
        if !game.world.loaded(target[0], target[2]) {
            set_status(&mut entity.nbt, "PAUSED", "targetNotLoaded");
            break;
        }
        let target_state = game.world.block(target[0], target[1], target[2]);
        let conductor = |state| {
            game.res.behaviours().facts(state).flags
                & horizon_world::level::data::state_flags::CONDUCTOR
                != 0
        };
        if state.is_none()
            || state == Some(target_state)
            || mode != 3 && state.is_some_and(|state| game.res.behaviours().is_air(state))
            || game.res.behaviours().facts(target_state).hardness == -1.0
            || within(target, pos, 2.0)
            || !replace_entities
                && game
                    .world
                    .block_entities
                    .contains_key(&(target[0], target[1], target[2]))
            || mode == 0 && conductor(target_state)
            || mode == 1 && conductor(target_state) && !state.is_some_and(conductor)
        {
            cursor += 1;
            continue;
        }
        let fuel = if creative {
            0
        } else {
            int(&entity.nbt, "RemainingFuel").unwrap_or(0)
        };
        if !creative && fuel <= 0 {
            set_status(&mut entity.nbt, "PAUSED", "noGunpowder");
            break;
        }
        let state = state.expect("resolved block state");
        let air = game.res.behaviours().is_air(state);
        let name = game.native_state_block(state).unwrap_or("minecraft:air");
        let item = match name {
            "minecraft:farmland" | "minecraft:dirt_path" => "minecraft:dirt",
            "minecraft:wall_torch" => "minecraft:torch",
            "minecraft:redstone_wall_torch" => "minecraft:redstone_torch",
            "minecraft:soul_wall_torch" => "minecraft:soul_torch",
            _ => name,
        }
        .to_owned();
        if !air && game.items().get(&item).is_none() {
            cursor += 1;
            continue;
        }
        let required = game.pack.assets.registry.state(state).map_or(1, |state| {
            if state
                .properties
                .get("type")
                .is_some_and(|value| value == "double")
            {
                2
            } else {
                ["eggs", "pickles", "layers"]
                    .into_iter()
                    .find_map(|key| {
                        state
                            .properties
                            .get(key)
                            .and_then(|value| value.parse::<i32>().ok())
                    })
                    .unwrap_or(1)
            }
        });
        if !air && !creative && !take_adjacent(game, pos, &item, required as u32) {
            if skip_missing {
                cursor += 1;
                continue;
            }
            entity
                .nbt
                .insert("MissingItem".into(), Tag::String(item.as_str().into()));
            entity.nbt.insert("MissingCount".into(), Tag::Int(required));
            set_status(&mut entity.nbt, "PAUSED", "missingBlock");
            break;
        }
        entity.nbt.remove(&"MissingItem".into());
        entity.nbt.remove(&"MissingCount".into());
        let distance_sq: f64 = (0..3)
            .map(|axis| (f64::from(target[axis]) - f64::from(pos[axis])).powi(2))
            .sum();
        let duration = (distance_sq.sqrt().sqrt() * 4.0).max(10.0) as i32;
        block.insert("TicksLeft".into(), Tag::Int(duration));
        block.insert("TotalTicks".into(), Tag::Int(duration));
        block.insert("Item".into(), Tag::String(item.as_str().into()));
        let key = "FlyingBlocks".into();
        let mut flights = match entity.nbt.remove(&key) {
            Some(Tag::List(flights)) => flights,
            _ => Vec::new(),
        };
        flights.push(Tag::Compound(block));
        entity.nbt.insert(key, Tag::List(flights));
        cursor += 1;
        entity
            .nbt
            .insert("RemainingFuel".into(), Tag::Int(fuel - 1));
        let placed = int(&entity.nbt, "AmountPlaced").unwrap_or(0) + i32::from(!air);
        entity.nbt.insert("AmountPlaced".into(), Tag::Int(placed));
        entity
            .nbt
            .insert("Cooldown".into(), Tag::Int(SHOT_COOLDOWN));
        let total = int(&entity.nbt, "AmountToPlace").unwrap_or(0).max(1);
        set_float(&mut entity.nbt, "Progress", placed as f32 / total as f32);
        set_status(
            &mut entity.nbt,
            "RUNNING",
            if air { "clearing" } else { "placing" },
        );
        break;
    }
    if entity.nbt.contains_key(&"Queue".into()) {
        entity.nbt.insert("Cursor".into(), Tag::Int(cursor as i32));
    }
    game.native_block_entity_sync(pos);
}

pub(super) fn use_item(
    game: &mut Game<'_>,
    pos: [i32; 3],
    face: [i32; 3],
    stack: &ItemStack,
) -> bool {
    use crate::containers::BlockEntity;

    let block = game.native_block(pos);
    if stack.item.as_ref() == EMPTY {
        let Some(BlockEntity::StructureBlock(saved)) =
            game.world.block_entities.get(&(pos[0], pos[1], pos[2]))
        else {
            return false;
        };
        let name = saved.structure_name().to_owned();
        if !valid_id(&name) || game.template_entry(&name).is_none() {
            return false;
        }
        let mut schematic = ItemStack::new(SCHEMATIC, 1);
        schematic.data_mut().set_other(
            "minecraft:custom_data",
            Some(Tag::compound([(
                "Template",
                Tag::String(name.as_str().into()),
            )])),
        );
        if stack.count == 1 {
            *game.held_mut() = Some(schematic);
        } else {
            game.consume_held();
            let player = game.native_acting_id();
            if let Some(rest) = game.native_give_stack(player, schematic) {
                game.pop_resource(pos, rest);
            }
        }
        return true;
    }
    if stack.item.as_ref() == GUNPOWDER && block == CANNON {
        let accepted = game.native_with_mod_block_entity(pos, |entity| {
            if entity.items.len() < 5 {
                entity.items.resize(5, None);
            }
            let Some(slot) = entity.items.get_mut(4) else {
                return false;
            };
            match slot {
                None => *slot = Some(ItemStack::new(GUNPOWDER, 1)),
                Some(fuel) if fuel.item.as_ref() == GUNPOWDER && fuel.count < 64 => fuel.count += 1,
                _ => return false,
            }
            true
        });
        if accepted == Some(true) {
            game.consume_held();
            game.native_block_entity_sync(pos);
        }
        return true;
    }
    if stack.item.as_ref() != SCHEMATIC {
        return false;
    }
    let Some(data) = stack.custom_data() else {
        return false;
    };
    if block == CANNON {
        if xyz(data.get(&"Anchor".into())).is_none() {
            return false;
        }
        let accepted = game.native_with_mod_block_entity(pos, |entity| {
            if entity.items.len() < 5 {
                entity.items.resize(5, None);
            }
            let Some(slot) = entity.items.first_mut() else {
                return false;
            };
            if slot.is_some() {
                return false;
            }
            let mut input = stack.clone();
            input.count = 1;
            *slot = Some(input);
            set_status(&mut entity.nbt, "RUNNING", "running");
            true
        });
        if accepted == Some(true) {
            game.consume_held();
            game.native_block_entity_sync(pos);
        }
    } else {
        let mut tagged = data.clone();
        tagged.insert("Anchor".into(), Tag::IntArray(offset(pos, face).to_vec()));
        if let Some(held) = game.held_mut() {
            held.data_mut()
                .set_other("minecraft:custom_data", Some(Tag::Compound(tagged)));
        }
    }
    true
}

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    entity: &ModBlockEntity,
    draw: &mut super::native_block_entity_draw::BlockEntityDraw,
) {
    let flights = match entity.nbt.get(&"FlyingBlocks".into()) {
        Some(Tag::List(flights)) => flights.as_slice(),
        _ => &[],
    };
    let relative = |target: [i32; 3]| [0, 1, 2].map(|i| target[i] as f32 - pos[i] as f32);
    let last_target = flights.last().and_then(|flight| xyz(flight.get("Target")));
    let (yaw, pitch) = if let Some(at) = last_target {
        let [x, y, z] = relative(at);
        let distance = x.hypot(z);
        (
            x.atan2(z).to_degrees(),
            distance.atan2(y * 3.0 + distance * 2.0).to_degrees() + 10.0,
        )
    } else {
        (
            super::create_machines::float(&entity.nbt, "DefaultYaw").unwrap_or(0.0),
            40.0,
        )
    };

    draw.push();
    draw.rotate_about([0.0, 1.0, 0.0], yaw + 90.0, [0.5, 0.0, 0.5]);
    game.native_draw_model(draw, "create:block/schematicannon/connector", 0xFFFFFF);
    draw.pop();

    let mut recoil = 0.0_f32;
    for flight in flights {
        let (Some(at), Some(Tag::Int(ticks)), Some(Tag::Int(total))) = (
            xyz(flight.get("Target")),
            flight.get("TicksLeft"),
            flight.get("TotalTicks"),
        ) else {
            continue;
        };
        if *ticks <= 0 || *total <= 0 {
            continue;
        }
        let ticks_left = (*ticks + 1) as f32 - draw.partial;
        recoil = recoil.max(ticks_left - *total as f32 + 10.0);
        let [x, y, z] = relative(at);
        let y = y - 1.0;
        let throw_height = (x * x + y * y + z * z).sqrt() * 0.6 + y;
        let cannon_height = y + throw_height;
        let length = (x * x + cannon_height * cannon_height + z * z).sqrt();
        let [ox, oy, oz] = [x, cannon_height, z].map(|n| n * 2.0 / length.max(f32::EPSILON));
        let t = 1.0 - ticks_left / *total as f32;
        let height = 2.0 * (1.0 - t) * t * throw_height + t * t * (y - oy);
        let state = flight
            .get("Block")
            .and_then(|tag| game.pack.assets.registry.saved_state_id(tag))
            .and_then(|id| game.pack.assets.registry.state(id));
        if let Some(state) = state {
            let properties: Vec<_> = state
                .properties
                .iter()
                .map(|(key, value)| (key.as_str(), value.as_str()))
                .collect();
            draw.push();
            draw.translate([
                0.5 + ox + (x - ox) * t,
                1.5 + oy + height,
                0.5 + oz + (z - oz) * t,
            ]);
            draw.rotate_about([0.0, 1.0, 0.0], 360.0 * t, [0.125; 3]);
            draw.rotate_about([1.0, 0.0, 0.0], 360.0 * t, [0.125; 3]);
            draw.scale([0.3; 3]);
            game.native_draw_block(draw, &state.name, &properties);
            draw.pop();
        }
    }
    draw.push();
    draw.rotate_about([0.0, 1.0, 0.0], yaw + 90.0, [0.5, 15.0 / 16.0, 0.5]);
    draw.rotate_about([0.0, 0.0, 1.0], pitch, [0.5, 15.0 / 16.0, 0.5]);
    draw.translate([0.0, -recoil / 100.0, 0.0]);
    game.native_draw_model(draw, "create:block/schematicannon/pipe", 0xFFFFFF);
    draw.pop();
}

pub(super) fn open(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.hand != super::Hand::Main
        || game.native_sneaking()
        || game.held().is_some()
        || game.native_block(pos) != CANNON
    {
        return false;
    }
    game.open_menu(pos);
    true
}

pub(super) fn layout() -> crate::mod_api::NativeScreen {
    crate::mod_api::NativeScreen {
        width: 250.0,
        height: 240.0,
        slots: vec![
            Some([16.0, 25.0]),
            Some([52.0, 25.0]),
            None,
            None,
            Some([88.0, 25.0]),
        ],
        inventory_x: 44.0,
        inventory_y: 158.0,
        own_labels: true,
        own_background: true,
    }
}

const CONTROLS: [(&str, [f32; 4]); 6] = [
    ("Start", [118.0, 23.0, 38.0, 20.0]),
    ("Pause", [160.0, 23.0, 38.0, 20.0]),
    ("Stop", [202.0, 23.0, 36.0, 20.0]),
    ("Skip missing", [12.0, 51.0, 104.0, 18.0]),
    ("Replace mode", [124.0, 51.0, 114.0, 18.0]),
    ("Replace containers", [12.0, 73.0, 146.0, 18.0]),
];

pub(super) fn screen_click([x, y]: [f32; 2]) -> Option<i32> {
    CONTROLS
        .iter()
        .position(|(_, [left, top, width, height])| {
            (*left..left + width).contains(&x) && (*top..top + height).contains(&y)
        })
        .map(|id| id as i32)
}

pub(super) fn menu_button(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    id: i32,
) {
    match id {
        0 => set_status(&mut entity.nbt, "RUNNING", "running"),
        1 => set_status(&mut entity.nbt, "PAUSED", "paused"),
        2 => {
            clear_job(entity, false);
            set_status(&mut entity.nbt, "STOPPED", "stopped");
        }
        3..=5 => {
            let mut opts = options(&entity.nbt).cloned().unwrap_or_default();
            let (key, default) = match id {
                3 => ("skip_missing", 1),
                4 => ("replace_mode", 2),
                _ => ("replace_block_entities", 0),
            };
            let old = int(&opts, key).unwrap_or(default);
            opts.insert(
                key.into(),
                Tag::Int(if id == 4 {
                    (old + 1) % 4
                } else {
                    i32::from(old == 0)
                }),
            );
            entity.nbt.insert("Options".into(), Tag::Compound(opts));
        }
        _ => return,
    }
    game.native_block_entity_sync(pos);
}

pub(super) fn draw_screen(
    game: &Game<'_>,
    draw: &mut horizon_client::hud::HudBatch,
    [x, y]: [f32; 2],
) {
    use crate::containers::BlockEntity;
    game.native_fill(draw, [x, y, 250.0, 240.0], 0xFF303030);
    game.native_text(draw, "Schematicannon", [x + 12.0, y + 7.0], 0xFFFFFF, false);
    game.native_text(draw, "Inventory", [x + 44.0, y + 147.0], 0xFFFFFF, false);
    for slot in 0..36 {
        let (left, top) = game.slot_position(slot);
        game.native_fill(
            draw,
            [x + left - 1.0, y + top - 1.0, 18.0, 18.0],
            0xFF777777,
        );
        game.native_fill(draw, [x + left, y + top, 16.0, 16.0], 0xFF444444);
    }
    for [left, top] in [[16.0, 25.0], [52.0, 25.0], [88.0, 25.0]] {
        game.native_fill(
            draw,
            [x + left - 1.0, y + top - 1.0, 18.0, 18.0],
            0xFF777777,
        );
    }
    for (label, [left, top, width, height]) in CONTROLS {
        let bounds = [x + left, y + top, width, height];
        horizon_client::widgets::record(label, bounds, true);
        game.native_fill(draw, bounds, 0xFF606060);
        game.native_text(
            draw,
            if label == "Replace mode" { "" } else { label },
            [bounds[0] + 3.0, bounds[1] + 5.0],
            0xFFFFFF,
            false,
        );
    }
    if let Some(pos) = game.native_screen_pos()
        && let Some(BlockEntity::Mod(entity)) =
            game.world.block_entities.get(&(pos[0], pos[1], pos[2]))
    {
        let status = string(&entity.nbt, "Status").unwrap_or_else(|| "idle".into());
        let status = game.translate(&format!("create.schematicannon.status.{status}"), &status);
        let fuel = int(&entity.nbt, "RemainingFuel").unwrap_or(0);
        let opts = options(&entity.nbt);
        let skip = opts.and_then(|nbt| int(nbt, "skip_missing")).unwrap_or(1) != 0;
        let mode = opts.and_then(|nbt| int(nbt, "replace_mode")).unwrap_or(2);
        let replace = opts
            .and_then(|nbt| int(nbt, "replace_block_entities"))
            .unwrap_or(0)
            != 0;
        game.native_text(
            draw,
            &format!("{status}"),
            [x + 12.0, y + 98.0],
            0xFFFFFF,
            false,
        );
        let mode_name = match mode {
            0 => "Fill gaps",
            1 => "Replace solid",
            3 => "Clear and replace",
            _ => "Replace blocks",
        };
        game.native_text(
            draw,
            mode_name,
            [x + 124.0, y + 51.0 + 5.0],
            0xFFFFFF,
            false,
        );
        game.native_text(
            draw,
            &format!("Ammo: {fuel}  Skip missing: {skip}"),
            [x + 12.0, y + 112.0],
            0xFFFFFF,
            false,
        );
        game.native_text(
            draw,
            if replace { "ON" } else { "OFF" },
            [x + 168.0, y + 78.0],
            0xFFFFFF,
            false,
        );
        if let Some(item) = string(&entity.nbt, "MissingItem").filter(|item| !item.is_empty()) {
            game.native_text(
                draw,
                "Missing material:",
                [x + 12.0, y + 134.0],
                0xFFFFFF,
                false,
            );
            game.native_item_stack(
                draw,
                &ItemStack::new(&item, int(&entity.nbt, "MissingCount").unwrap_or(1) as u32),
                [x + 116.0, y + 128.0],
                16.0,
            );
        }
    }
}
