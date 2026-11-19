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
    let mode = options(&entity.nbt)
        .and_then(|tag| int(tag, "replace_mode"))
        .unwrap_or(2);
    let mut blocks: Vec<_> = palette
        .blocks()
        .iter()
        .filter(|block| {
            registry.state(block.state).is_some_and(|state| {
                state.name != "minecraft:structure_void"
                    && (mode == 3 || !game.res.behaviours().is_air(block.state))
            })
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
            if let Some(data) = &block.nbt {
                entry.insert("BlockEntity".into(), Tag::Compound((**data).clone()));
            }
            Some(Tag::Compound(entry))
        })
        .collect();
    entity
        .nbt
        .insert("AmountToPlace".into(), Tag::Int(queue.len() as i32));
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
    for field in ["Queue", "Cursor", "Cooldown"] {
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

fn take_adjacent(game: &mut Game<'_>, pos: [i32; 3], name: &str) -> bool {
    let dim = game.native_dimension();
    for face in Direction::ALL {
        let at = offset(pos, face.normal());
        let face = face.opposite();
        let Some(slots) = game.native_container_slots(dim, at, face) else {
            continue;
        };
        for slot in slots {
            if slot.can_take
                && slot
                    .stack
                    .as_ref()
                    .is_some_and(|item| item.item.as_ref() == name)
                && game
                    .native_extract_item(dim, at, face, slot.slot, 1)
                    .is_some()
            {
                return true;
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
    } else if take_adjacent(game, pos, GUNPOWDER) {
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
        let target_state = game.world.block(target[0], target[1], target[2]);
        if state.is_none()
            || within(target, pos, 2.0)
            || !replace_entities
                && game
                    .world
                    .block_entities
                    .contains_key(&(target[0], target[1], target[2]))
            || mode == 0 && !game.res.behaviours().is_air(target_state)
        {
            cursor += 1;
            continue;
        }
        if !game.world.loaded(target[0], target[2]) {
            set_status(&mut entity.nbt, "PAUSED", "targetNotLoaded");
            break;
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
        let item = game
            .native_state_block(state)
            .unwrap_or("minecraft:air")
            .to_owned();
        if !air && !creative && !take_adjacent(game, pos, &item) {
            if skip_missing {
                cursor += 1;
                continue;
            }
            set_status(&mut entity.nbt, "PAUSED", "missingBlock");
            break;
        }
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
            let Some(slot) = entity.items.first_mut() else {
                return false;
            };
            if slot.is_some() {
                return false;
            }
            *slot = Some(stack.clone());
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
