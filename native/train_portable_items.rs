use glam::Vec3;
use horizon_core::geometry::Direction;
use horizon_world::java_hash_map::{JavaHashMap, JavaKey};
use horizon_world::nbt::{Compound, Tag};
use std::cmp::Ordering;

use super::Game;
use super::create_bearing::{cargo_items, is_cargo, relative};
use super::create_depot::compound;
use super::create_fan::facing;
use super::create_machines::{int, mod_entity, offset};
pub(super) use super::create_portable_interface::{FLUID, ITEM};
use super::create_portable_interface::{connected, renew};
use super::create_train::{CARRIAGE, Pose, coords, state_name};
use super::create_vault::{SLOTS as VAULT_SLOTS, VAULT};
use crate::containers::{BlockEntity, ModBlockEntity};
use crate::items::ItemStack;
use horizon_client::world::World;

const CONTACT: &str = "TrainPort";
const WORKING: &str = "TrainWorkingPos";
pub(super) const RETRACTION_TICK: &str = "TrainPortRetractionTick";
const ANIMATION: i32 = 4;
const INITIAL_TIMER: i32 = 6 + 2 * ANIMATION;
const STORAGE_SLOTS: usize = 27;
const CARGO_X: i32 = i32::MAX - 16;
type Pos = (i32, i32, i32);

fn cargo_key(id: u32) -> Pos {
    (CARGO_X, super::minecarts::CART_KEY_Y, id as i32)
}

pub(super) fn has_port(data: &Compound) -> bool {
    matches!(data.get(&"Blocks".into()), Some(Tag::List(blocks)) if blocks.iter().any(|tag|
        matches!(tag, Tag::Compound(block) if matches!(state_name(block).as_deref(), Some(ITEM | FLUID)))))
}

#[derive(PartialEq, Eq)]
struct StoragePosition([i32; 3]);

impl JavaKey for StoragePosition {
    fn java_hash(&self) -> i32 {
        let [x, y, z] = self.0;
        y.wrapping_add(z.wrapping_mul(31))
            .wrapping_mul(31)
            .wrapping_add(x)
    }

    fn comparable_compare(&self, other: &Self) -> Option<Ordering> {
        let [x, y, z] = self.0;
        let [other_x, other_y, other_z] = other.0;
        Some([y, z, x].cmp(&[other_y, other_z, other_x]))
    }

    fn tie_break(&self, _other: &Self) -> Ordering {
        Ordering::Less
    }
}

pub(super) fn cargo_blocks(blocks: &[Tag]) -> Vec<usize> {
    // MountedStorageManager builds its combined inventory from a HashMap
    // keyed by the blocks' positions relative to the carriage anchor.
    let mut mounted = JavaHashMap::default();
    for (index, tag) in blocks.iter().enumerate() {
        let Tag::Compound(block) = tag else { continue };
        if cargo_storage(block).is_some() {
            mounted.put(StoragePosition(relative(block)), index);
        }
    }
    mounted.entries().map(|(_, index)| *index).collect()
}

pub(super) fn cargo_storage(block: &Compound) -> Option<(&Compound, usize)> {
    match state_name(block).as_deref() {
        Some(name) if name.starts_with("minecraft:") && is_cargo(name) => {
            Some((compound(block, "VanillaEntity")?, STORAGE_SLOTS))
        }
        Some(VAULT) if compound(block, "Entity").is_some() => Some((block, VAULT_SLOTS)),
        _ => None,
    }
}

fn cargo_slots(storage: &Compound, capacity: usize) -> Vec<Option<ItemStack>> {
    let mut slots = vec![None; capacity];
    if let Some(Tag::List(items)) = storage.get(&"Items".into()) {
        for entry in items {
            let Tag::Compound(item) = entry else { continue };
            if let Some(slot) = int(item, "Slot").and_then(|index| slots.get_mut(index as usize)) {
                *slot = ItemStack::from_nbt(item);
            }
        }
    }
    slots
}

pub(super) fn begin_block_phase(game: &mut Game<'_>, id: u32, data: &Compound) {
    let Some(Tag::List(blocks)) = data.get(&"Blocks".into()) else {
        return;
    };
    let now = game.world.game_time;
    let mut item_connected = false;
    for tag in blocks {
        let Tag::Compound(block) = tag else { continue };
        let Some(station @ [x, y, z]) = coords(block, WORKING) else {
            continue;
        };
        let name = state_name(block);
        let Some(kind @ (ITEM | FLUID)) = name.as_deref() else {
            continue;
        };
        if attached(&game.world, (x, y, z), kind) != Some(id) {
            // A moving carriage publishes the next contact cell after the previous block phase.
            let Some((receiver, distance)) = Pose::for_port_scan(game, data)
                .and_then(|pose| target(game, block, pose, kind))
            else {
                continue;
            };
            if receiver != station || !attach(game, id, receiver, distance) {
                continue;
            }
        }
        // A powered interface invalidates its capability before adjacent
        // hoppers and pumps tick, even though the carriage still lines up.
        if game.native_neighbor_signal(game.native_dimension(), station) > 0 {
            game.native_with_mod_block_entity(station, |entity| {
                disconnect(entity, now);
            });
        } else {
            item_connected |= kind == ITEM;
        }
    }
    if !item_connected {
        return;
    }
    let slots: Vec<_> = cargo_blocks(blocks)
        .into_iter()
        .filter_map(|index| match &blocks[index] {
            Tag::Compound(block) => cargo_storage(block),
            _ => None,
        })
        .flat_map(|(storage, capacity)| cargo_slots(storage, capacity))
        .collect();
    if slots.is_empty() {
        return;
    }

    game.world
        .block_entities
        .insert(cargo_key(id), BlockEntity::Chest(slots));
}

fn attached(world: &World, station: Pos, kind: &str) -> Option<u32> {
    let BlockEntity::Mod(entity) = world.block_entities.get(&station)? else {
        return None;
    };
    if entity.id != kind
        || entity.nbt.contains_key(&"Bearing".into())
        || !(ANIMATION..=60 + ANIMATION).contains(&int(&entity.nbt, "Timer")?)
    {
        return None;
    }
    let Tag::Long(last) = entity.nbt.get(&"LastContact".into())? else {
        return None;
    };
    // Hopper reads the prior entity phase, before this tick's carriage movement.
    if !(0..=2).contains(&(world.game_time - *last)) {
        return None;
    }
    int(&entity.nbt, CONTACT).map(|id| id as u32)
}

pub(super) fn cargo_at(world: &World, station: Pos) -> Option<Pos> {
    let key = cargo_key(attached(world, station, ITEM)?);
    world.block_entities.contains_key(&key).then_some(key)
}

pub(super) fn fluid_train_at(world: &World, station: [i32; 3]) -> Option<u32> {
    attached(world, (station[0], station[1], station[2]), FLUID)
}

pub(super) fn changed(game: &mut Game<'_>, key: Pos, station: Pos) -> bool {
    if key.0 != CARGO_X || key.1 != super::minecarts::CART_KEY_Y {
        return false;
    }
    let slots = match game.world.block_entities.get(&key) {
        Some(BlockEntity::Chest(slots)) => slots,
        _ => return true,
    };
    let Some(Tag::Compound(entity)) = game.persist.raw.get_mut(&(key.2 as u32)) else {
        return true;
    };
    let Some(Tag::Compound(carriage)) = entity.get_mut(&CARRIAGE.into()) else {
        return true;
    };
    let Some(Tag::List(blocks)) = carriage.get_mut(&"Blocks".into()) else {
        return true;
    };
    // The combined view uses contiguous segments, but each saved storage
    // still numbers its own slots starting at zero.
    let mut offset = 0;
    let mut exchanged = false;
    for index in cargo_blocks(blocks) {
        let Tag::Compound(block) = &mut blocks[index] else { continue };
        let Some((_, capacity)) = cargo_storage(block) else {
            continue;
        };
        let Some(storage_slots) = slots.get(offset..offset + capacity) else {
            break;
        };
        offset += capacity;
        let Some((items, _)) = cargo_items(block) else {
            continue;
        };
        let Tag::List(saved) = horizon_client::save::encode_items(storage_slots) else {
            continue;
        };
        if *items != saved {
            *items = saved;
            exchanged = true;
        }
    }
    if exchanged {
        carriage.insert("CargoIdleTicks".into(), Tag::Int(0));
        renew(game, [station.0, station.1, station.2]);
    }
    true
}

pub(super) fn end_block_phase(game: &mut Game<'_>) {
    game.world
        .block_entities
        .retain(|&(x, y, _), _| x != CARGO_X || y != super::minecarts::CART_KEY_Y);
}

fn target(
    game: &mut Game<'_>,
    block: &Compound,
    pose: Pose,
    kind: &str,
) -> Option<([i32; 3], f32)> {
    let state = block
        .get(&"BlockState".into())
        .and_then(|tag| game.state_from_nbt(tag))?;
    let local_side = facing(game, state)?;
    let normal = Vec3::from_array(local_side.normal().map(|n| n as f32));
    let front = pose.rotation * normal;
    let vector = |direction: Direction| Vec3::from_array(direction.normal().map(|n| n as f32));
    let direction = Direction::ALL
        .into_iter()
        .find(|&dir| vector(dir).distance_squared(front) <= 0.25)?;
    let local = Vec3::from_array(relative(block).map(|v| v as f32));
    let active = pose.position(local + Vec3::new(0.0, 0.5, 0.0) + 1.85 * normal);
    let cell = active.map(|value| value.floor() as i32);
    let normal = direction.normal();
    let target = [cell, offset(cell, normal)].into_iter().find(|&pos| {
        mod_entity(game, pos).is_some_and(|entity| entity.id == kind)
            && facing(game, game.world.block(pos[0], pos[1], pos[2])) == Some(direction.opposite())
            && game.native_neighbor_signal(game.native_dimension(), pos) == 0
    })?;
    let projected = (0..3)
        .map(|i| (f64::from(target[i]) + 0.5 - active[i]) * f64::from(normal[i]))
        .sum::<f64>();
    let distance = (projected.abs() as f32 + 1.85 - 1.0).min(2.0);
    Some((target, distance))
}

fn attach(game: &mut Game<'_>, id: u32, pos: [i32; 3], distance: f32) -> bool {
    let now = game.world.game_time;
    let accepted = game
        .native_with_mod_block_entity(pos, |entity| {
            let last = match entity.nbt.get(&"LastContact".into()) {
                Some(Tag::Long(tick)) => *tick,
                _ => i64::MIN / 2,
            };
            let owner = int(&entity.nbt, CONTACT);
            let ours = owner == Some(id as i32) && now - last < 2;
            if !ours && now - last < 2 {
                return None;
            }
            let was_connected = connected(entity);
            if !ours {
                entity.nbt.remove(&"Bearing".into());
                entity.nbt.remove(&RETRACTION_TICK.into());
                entity.nbt.insert("Timer".into(), Tag::Int(INITIAL_TIMER));
                entity
                    .nbt
                    .insert("Distance".into(), Tag::Float(distance.to_bits()));
            }
            entity.nbt.insert(CONTACT.into(), Tag::Int(id as i32));
            entity.nbt.insert("LastContact".into(), Tag::Long(now));
            Some(!was_connected && connected(entity))
        })
        .flatten();
    if accepted == Some(true) {
        game.container_changed((pos[0], pos[1], pos[2]));
    }
    accepted.is_some()
}

pub(super) fn refresh_port(
    game: &mut Game<'_>,
    id: u32,
    data: &mut Compound,
    pose: Pose,
    station: [i32; 3],
) -> bool {
    let Some(Tag::List(blocks)) = data.get_mut(&"Blocks".into()) else {
        return false;
    };
    for tag in blocks {
        let Tag::Compound(block) = tag else { continue };
        let name = state_name(block);
        let Some(kind @ (ITEM | FLUID)) = name.as_deref() else {
            continue;
        };
        if let Some((pos, distance)) = target(game, block, pose, kind)
            && pos == station
            && attach(game, id, pos, distance)
        {
            block.insert(WORKING.into(), Tag::IntArray(pos.to_vec()));
            return true;
        }
    }
    false
}

pub(super) fn update(
    game: &mut Game<'_>,
    id: u32,
    data: &mut Compound,
    pose: Pose,
    speed: f64,
    moved: bool,
) -> bool {
    let Some(Tag::List(blocks)) = data.get_mut(&"Blocks".into()) else {
        return false;
    };
    let mut visual_changed = false;
    let now = game.world.game_time;
    for tag in blocks {
        let Tag::Compound(block) = tag else { continue };
        let name = state_name(block);
        let Some(kind @ (ITEM | FLUID)) = name.as_deref() else {
            continue;
        };
        let scanning = speed.abs() <= 0.25;
        let contact = scanning.then(|| target(game, block, pose, kind)).flatten();
        let chase_target = contact.map(|(pos, distance)| {
            mod_entity(game, pos)
                .and_then(|entity| super::create_machines::float(&entity.nbt, "Distance"))
                .filter(|distance| *distance > 0.0)
                .unwrap_or(distance)
                * 0.5
        });
        visual_changed |= super::create_train_portable_visuals::chase_carriage_port(
            block,
            scanning.then_some(chase_target.unwrap_or(0.0)),
            now,
        );
        if let Some((pos, distance)) = contact {
            let [x, y, z] = pos;
            let new_moving_contact = moved && attached(&game.world, (x, y, z), kind) != Some(id);
            if new_moving_contact || attach(game, id, pos, distance) {
                block.insert(WORKING.into(), Tag::IntArray(pos.to_vec()));
                continue;
            }
        }
        if let Some(prior) = coords(block, WORKING) {
            let still_alive = game
                .native_with_mod_block_entity(prior, |entity| {
                    let Some(Tag::Long(last)) = entity.nbt.get(&"LastContact".into()) else {
                        return false;
                    };
                    if int(&entity.nbt, CONTACT) != Some(id as i32) {
                        return false;
                    }
                    if now - *last < 2 {
                        return true;
                    }
                    disconnect(entity, now);
                    false
                })
                .unwrap_or(false);
            if !still_alive {
                block.remove(&WORKING.into());
            }
        }
    }
    visual_changed
}

fn disconnect(entity: &mut ModBlockEntity, now: i64) {
    entity.nbt.remove(&CONTACT.into());
    entity.nbt.insert("Timer".into(), Tag::Int(ANIMATION - 1));
    entity.nbt.insert(RETRACTION_TICK.into(), Tag::Long(now));
}

/// The fixed block entity updates before its adjacent logistics machines
/// in their normal world ticker order. A later transfer can then refresh
/// the original timeout without the moving carriage decrementing it again.
pub(super) fn tick_stationary(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    if !entity.nbt.contains_key(&"Powered".into()) {
        let powered = game.native_neighbor_signal(game.native_dimension(), pos) != 0;
        entity
            .nbt
            .insert("Powered".into(), Tag::Byte(i8::from(powered)));
    }
    let now = game.world.game_time;
    if super::create_portable_interface::tick_bearing_port(game, pos, entity) {
        // The bearing publishes the opening endpoints after advancing its actor.
        if super::create_portable_interface::bearing_contact_starts_now(entity, now) {
            return;
        }
        let first_retraction_tick = matches!(entity.nbt.get(&RETRACTION_TICK.into()), Some(Tag::Long(start)) if *start == now);
        super::create_train_portable_visuals::update(game, pos, entity, first_retraction_tick);
        return;
    }
    if !entity.nbt.contains_key(&"Distance".into()) {
        return;
    }
    let linked = entity.nbt.contains_key(&CONTACT.into());
    if linked
        && matches!(entity.nbt.get(&"LastContact".into()), Some(Tag::Long(last)) if now - *last >= 2)
    {
        disconnect(entity, now);
    }
    let first_retraction_tick =
        matches!(entity.nbt.get(&RETRACTION_TICK.into()), Some(Tag::Long(start)) if *start == now);
    if !first_retraction_tick {
        let timer = int(&entity.nbt, "Timer").unwrap_or(0);
        let next = (timer - 1).max(if linked { ANIMATION } else { 0 });
        if next != timer {
            entity.nbt.insert("Timer".into(), Tag::Int(next));
            if next < ANIMATION && (next == 0 || int(&entity.nbt, "Powered") == Some(1)) {
                game.container_changed((pos[0], pos[1], pos[2]));
            }
        }
    }
    super::create_train_portable_visuals::update(game, pos, entity, first_retraction_tick);
}
