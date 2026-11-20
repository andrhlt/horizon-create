use horizon_core::geometry::Direction;
use horizon_core::position::BlockPos;
use horizon_world::level::PlacementContext;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use super::create_bearing::{relative, rotate};
use super::create_depot::compound;
use super::create_fan::facing;
use super::create_machines::{advancement_owner, int, mod_entity, offset};
use super::{Game, GameLevel};
use crate::containers::{BlockEntity, ModBlockEntity};

pub(super) const ITEM: &str = "create:portable_storage_interface";
pub(super) const FLUID: &str = "create:portable_fluid_interface";
const DRIVE_BY: &str = "create:portable_storage_interface";
const DRIVE_BY_TRIGGER: &str = "create:portable_storage_interface_builtin";
const ANIMATION: i32 = 4;
const INITIAL_TIMER: i32 = 6 + ANIMATION * 2;
const CONNECTED_AT: &str = "ConnectedAt";
const FIRST_EXCHANGE: &str = "BearingFirstExchange";
const ACTOR_STALL_AT: &str = "PortActorStallAt";
const ACTOR_CONTACT_AT: &str = "PortActorContactAt";

fn time(nbt: &Compound, key: &str) -> Option<i64> {
    let Tag::Long(value) = nbt.get(&key.into())? else {
        return None;
    };
    Some(*value)
}

pub(super) fn bearing_contact_starts_now(entity: &ModBlockEntity, now: i64) -> bool {
    time(&entity.nbt, CONNECTED_AT) == Some(now - 1)
}

pub(super) fn is_port(block: &str) -> bool {
    matches!(block, ITEM | FLUID)
}

pub(super) fn connected(entity: &ModBlockEntity) -> bool {
    int(&entity.nbt, "Timer").is_some_and(|timer| (ANIMATION..=60 + ANIMATION).contains(&timer))
}

pub(super) fn has_output(level: &GameLevel<'_>, state: BlockStateId, out: &mut bool) {
    *out |= level.native_state_block(state).is_some_and(is_port);
}

pub(super) fn output(level: &GameLevel<'_>, pos: BlockPos, state: BlockStateId, out: &mut i32) {
    if level.native_state_block(state).is_some_and(is_port) {
        *out = if matches!(
            level.world.block_entities.get(&(pos.x, pos.y, pos.z)),
            Some(BlockEntity::Mod(entity)) if connected(entity)
        ) {
            15
        } else {
            0
        };
    }
}

pub(super) fn powered_changed(game: &mut Game<'_>, pos: [i32; 3]) {
    if !game.native_authoritative() {
        return;
    }
    let powered = game.native_neighbor_signal(game.native_dimension(), pos) != 0;
    if mod_entity(game, pos).and_then(|entity| int(&entity.nbt, "Powered"))
        == Some(i32::from(powered))
    {
        return;
    }
    let unlocked = game.native_with_mod_block_entity(pos, |entity| {
        let was_powered = int(&entity.nbt, "Powered") == Some(1);
        entity
            .nbt
            .insert("Powered".into(), Tag::Byte(i8::from(powered)));
        was_powered && !powered
    });
    if unlocked == Some(true) {
        super::create_train::refresh_port(game, pos);
    }
}

pub(super) fn update_bearing(
    game: &mut Game<'_>,
    bearing: [i32; 3],
    anchor: [i32; 3],
    blocks: &mut [Compound],
    axis: usize,
    previous: f64,
    angle: f64,
) -> bool {
    let dim = game.native_dimension();
    let now = game.world.game_time;
    let mut stalled = false;
    for block in blocks {
        let Some(state) = block
            .get(&"BlockState".into())
            .and_then(|tag| game.state_from_nbt(tag))
        else {
            continue;
        };
        if !matches!(
            game.pack
                .assets
                .registry
                .state(state)
                .map(|state| state.name.as_str()),
            Some(ITEM | FLUID)
        ) {
            continue;
        }
        let Some(side) = facing(game, state) else {
            continue;
        };
        let front = rotate(side.normal().map(f64::from), axis, angle);
        let direction = Direction::ALL
            .into_iter()
            .max_by(|a, b| {
                let projection = |side: Direction| {
                    (0..3)
                        .map(|i| f64::from(side.normal()[i]) * front[i])
                        .sum::<f64>()
                };
                projection(*a).total_cmp(&projection(*b))
            })
            .unwrap_or(side);
        let n = direction.normal();
        let local = relative(block);
        let actor_offset = std::array::from_fn(|i| {
            f64::from(local[i]) + f64::from(side.normal()[i]) * f64::from(1.85_f32)
        });
        let active = |theta| {
            let rotated = rotate(actor_offset, axis, theta);
            std::array::from_fn::<_, 3, _>(|i| f64::from(anchor[i]) + 0.5 + rotated[i])
        };
        let old = active(previous);
        let point = active(angle);
        let cell = point.map(|value| value.floor() as i32);
        let entered_cell = old.map(|value| value.floor() as i32) != cell;
        let prior: Option<[i32; 3]> = match block.get(&"WorkingPos".into()) {
            Some(Tag::IntArray(pos)) => pos.as_slice().try_into().ok(),
            _ => None,
        };
        // On reopen the bearing may tick before its receiver's chunk is loaded.
        if previous == angle && prior.is_some_and(|[x, _, z]| !game.world.loaded(x, z)) {
            stalled |= int(block, "Stalled") == Some(1);
            continue;
        }
        let kind = game
            .pack
            .assets
            .registry
            .state(state)
            .map(|state| state.name.as_str());
        let aligned = (0..3)
            .map(|i| (front[i] - f64::from(n[i])).powi(2))
            .sum::<f64>()
            <= 0.25;
        let station = aligned
            .then(|| {
                prior
                    .filter(|_| !entered_cell)
                    .into_iter()
                    .chain([cell, offset(cell, n)])
                    .find(|&pos| {
                        mod_entity(game, pos).is_some_and(|entity| Some(entity.id.as_str()) == kind)
                            && facing(game, game.world.block(pos[0], pos[1], pos[2]))
                                == Some(direction.opposite())
                            && game.native_neighbor_signal(dim, pos) == 0
                    })
            })
            .flatten();
        if let Some(prior) = prior
            && station != Some(prior)
        {
            leave_port(game, bearing, prior);
        }
        let Some(station) = station else {
            block.remove(&"WorkingPos".into());
            block.remove(&"Stalled".into());
            animate_bearing_port(block, now, None, false);
            continue;
        };
        let (timer, first_live) = game
            .native_with_mod_block_entity(station, |entity| {
                let owns_receiver = matches!(
                    entity.nbt.get(&"Bearing".into()),
                    Some(Tag::IntArray(owner)) if owner.as_slice() == bearing
                );
                let recent_contact = matches!(
                    time(&entity.nbt, "LastContact"),
                    Some(last) if last == now || last == now - 1
                );
                entity
                    .nbt
                    .insert("Bearing".into(), Tag::IntArray(bearing.to_vec()));
                entity.nbt.insert("LastContact".into(), Tag::Long(now));
                if prior != Some(station) || !owns_receiver || !recent_contact {
                    entity.nbt.insert(CONNECTED_AT.into(), Tag::Long(now));
                    entity.nbt.remove(&FIRST_EXCHANGE.into());
                    entity
                        .nbt
                        .remove(&super::create_train_portable_items::RETRACTION_TICK.into());
                    // Recognition precedes the first active transfer tick. The placed
                    // entity still owns its old timer while the actor approaches.
                    return (INITIAL_TIMER, false);
                }
                let first_live = bearing_contact_starts_now(entity, now);
                if first_live {
                    let distance =
                        bearing_distance(anchor, station, actor_offset, axis, previous, n);
                    super::create_train_portable_visuals::start_bearing_connection(
                        entity, distance,
                    );
                }
                let exchanged = entity.nbt.remove(&FIRST_EXCHANGE.into()).is_some();
                let duration = if first_live && !exchanged {
                    INITIAL_TIMER
                } else {
                    int(&entity.nbt, "Timer").unwrap_or_default()
                };
                // Keep the connection at four until the actor leaves the active cell.
                let timer = duration - i32::from(duration > ANIMATION);
                entity.nbt.insert("Timer".into(), Tag::Int(timer));
                (timer, first_live)
            })
            .unwrap_or_default();
        if first_live {
            super::create_train_portable_visuals::show_bearing_connection(game, station);
            game.container_changed((station[0], station[1], station[2]));
        }
        block.insert("WorkingPos".into(), Tag::IntArray(station.to_vec()));
        let distance = |point: [f64; 3]| {
            (0..3)
                .map(|i| (point[i] - f64::from(station[i]) - 0.5).powi(2))
                .sum::<f64>()
        };
        let ahead = std::array::from_fn(|i| 2.0 * point[i] - old[i]);
        let past_center = distance(point) < distance(ahead);
        let docked = timer > ANIMATION && (past_center || int(block, "Stalled") == Some(1));
        block.insert("Stalled".into(), Tag::Byte(i8::from(docked)));
        let distance = mod_entity(game, station)
            .and_then(|entity| super::create_machines::float(&entity.nbt, "Distance"))
            .unwrap_or_default();
        animate_bearing_port(block, now, Some(distance), docked);
        stalled |= docked;
    }
    stalled
}

fn animate_bearing_port(block: &mut Compound, now: i64, contact: Option<f32>, docked: bool) {
    let mut target = None;
    if let Some(distance) = contact {
        block.insert(ACTOR_CONTACT_AT.into(), Tag::Long(now));
        if docked {
            let start = time(block, ACTOR_STALL_AT).unwrap_or(now);
            block.insert(ACTOR_STALL_AT.into(), Tag::Long(start));
            // The original actor gets the stall and targets the receiver on its following updates.
            if now - start >= 2 {
                target = Some(distance / 2.0);
            }
        } else {
            block.remove(&ACTOR_STALL_AT.into());
        }
    } else {
        block.remove(&ACTOR_STALL_AT.into());
        // The client still sees the previous active cell while motion resumes.
        if time(block, ACTOR_CONTACT_AT).is_none_or(|last| now - last >= 3) {
            target = Some(0.0);
            block.remove(&ACTOR_CONTACT_AT.into());
        }
    }
    super::create_train_portable_visuals::chase_bearing_port(block, target, now);
}

fn bearing_distance(
    anchor: [i32; 3],
    station: [i32; 3],
    mut offset: [f64; 3],
    axis: usize,
    angle: f64,
    normal: [i32; 3],
) -> f32 {
    // Create 1.21 rotates this actor with float-indexed Mth.sin and Mth.cos.
    let phase = angle as f32 * 10430.378_f32;
    let table = horizon_core::geometry::trig::sine_table();
    let sin = f64::from(table[(phase as i32 & 65535) as usize]);
    let cos = f64::from(table[((phase + 16384.0) as i32 & 65535) as usize]);
    let a = (axis + 1) % 3;
    let b = (axis + 2) % 3;
    (offset[a], offset[b]) = (
        offset[a] * cos - offset[b] * sin,
        offset[a] * sin + offset[b] * cos,
    );
    let gap = (0..3)
        .map(|i| (f64::from(station[i] - anchor[i]) - offset[i]) * f64::from(normal[i]))
        .sum::<f64>()
        .abs();
    (gap + f64::from(1.85_f32) - 1.0).min(2.0) as f32
}

fn leave_port(game: &mut Game<'_>, bearing: [i32; 3], station: [i32; 3]) {
    let now = game.world.game_time;
    game.native_with_mod_block_entity(station, |entity| {
        if !matches!(entity.nbt.get(&"Bearing".into()), Some(Tag::IntArray(owner)) if owner.as_slice() == bearing)
            || time(&entity.nbt, "LastContact") != Some(now - 1)
        {
            return;
        }
        let timer = int(&entity.nbt, "Timer").unwrap_or_default();
        if timer > ANIMATION {
            entity.nbt.insert("Timer".into(), Tag::Int(timer - 1));
        }
    });
}

pub(super) fn bearing_stopped(game: &mut Game<'_>, bearing: [i32; 3], blocks: &[Compound]) {
    for block in blocks {
        if let Some(Tag::IntArray(station)) = block.get(&"WorkingPos".into())
            && let Ok(pos) = <[i32; 3]>::try_from(station.as_slice())
        {
            leave_port(game, bearing, pos);
        }
    }
}

pub(super) fn tick_bearing_port(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
) -> bool {
    if !entity.nbt.contains_key(&"Bearing".into()) {
        return false;
    }
    let now = game.world.game_time;
    let timer = int(&entity.nbt, "Timer").unwrap_or_default();
    if time(&entity.nbt, CONNECTED_AT) == Some(now) {
        if timer > 0 {
            entity.nbt.insert("Timer".into(), Tag::Int(timer - 1));
        }
        return true;
    }
    if time(&entity.nbt, "LastContact").is_some_and(|last| now - last < 2) {
        return true;
    }
    let retraction = super::create_train_portable_items::RETRACTION_TICK;
    if !entity.nbt.contains_key(&retraction.into()) {
        entity.nbt.insert(retraction.into(), Tag::Long(now));
        entity.nbt.insert("Timer".into(), Tag::Int(ANIMATION - 1));
        return true;
    }
    let next = (timer - 1).max(0);
    entity.nbt.insert("Timer".into(), Tag::Int(next));
    if next == 0 || int(&entity.nbt, "Powered") == Some(1) {
        game.container_changed((pos[0], pos[1], pos[2]));
    }
    if next == 0 {
        entity.nbt.remove(&"Bearing".into());
        entity.nbt.remove(&CONNECTED_AT.into());
        entity.nbt.remove(&"LastContact".into());
        entity.nbt.remove(&retraction.into());
    }
    true
}

pub(super) fn bearing_at(
    world: &horizon_client::world::World,
    station: [i32; 3],
    kind: &str,
) -> Option<[i32; 3]> {
    let crate::containers::BlockEntity::Mod(entity) = world
        .block_entities
        .get(&(station[0], station[1], station[2]))?
    else {
        return None;
    };
    let last_contact = match entity.nbt.get(&"LastContact".into()) {
        Some(Tag::Long(tick)) => *tick,
        _ => return None,
    };
    let start = time(&entity.nbt, CONNECTED_AT)?;
    if start >= world.game_time
        || entity.id != kind
        || (world.game_time != start + 1 && int(&entity.nbt, "Timer").unwrap_or(0) < ANIMATION)
        || !(0..=1).contains(&(world.game_time - last_contact))
    {
        return None;
    }
    let Tag::IntArray(pos) = entity.nbt.get(&"Bearing".into())? else {
        return None;
    };
    let &[x, y, z] = pos.as_slice() else {
        return None;
    };
    let crate::containers::BlockEntity::Mod(moving) = world.block_entities.get(&(x, y, z))? else {
        return None;
    };
    (moving.id == "create:mechanical_bearing" && int(&moving.nbt, "Running") == Some(1))
        .then_some([x, y, z])
}

fn drive_by_awarded(game: &mut Game<'_>) -> bool {
    let tree = game.advancement_tree();
    tree.by_id
        .get(DRIVE_BY)
        .is_some_and(|&index| game.adv.progress.done(&tree.list[index]))
}

pub(super) fn remember_placer(game: &mut Game<'_>, station: [i32; 3]) {
    if drive_by_awarded(game) {
        return;
    }
    let owner = horizon_client::lan::playerdata::uuid_ints(game.native_acting_id());
    game.native_with_mod_block_entity(station, |entity| {
        entity
            .nbt
            .insert("Owner".into(), Tag::IntArray(owner.to_vec()));
    });
}

pub(super) fn renew(game: &mut Game<'_>, station: [i32; 3]) {
    let now = game.world.game_time;
    let owner = game
        .native_with_mod_block_entity(station, |entity| {
            if !is_port(&entity.id) {
                return None;
            }
            entity.nbt.insert("Timer".into(), Tag::Int(60 + ANIMATION));
            if entity.nbt.contains_key(&"Bearing".into())
                && time(&entity.nbt, CONNECTED_AT) == Some(now - 1)
            {
                entity.nbt.insert(FIRST_EXCHANGE.into(), Tag::Byte(1));
            }
            advancement_owner(&entity.nbt)
        })
        .flatten();
    let Some(owner) = owner else { return };
    let dimension = game.native_dimension().to_owned();
    let mut awarded = false;
    game.native_as_player(owner, |player_game| {
        if player_game.native_dimension() != dimension {
            return;
        }
        player_game.native_trigger_criterion(owner, DRIVE_BY_TRIGGER, |_| true);
        awarded = drive_by_awarded(player_game);
    });
    if awarded {
        game.native_with_mod_block_entity(station, |entity| {
            entity.nbt.remove(&"Owner".into());
        });
    }
}

fn compound_list<'a>(data: &'a Compound, key: &str) -> Option<&'a [Tag]> {
    match data.get(&key.into()) {
        Some(Tag::List(blocks)) => Some(blocks),
        _ => None,
    }
}

pub(super) fn tanks<'a>(
    game: &'a Game<'_>,
    station: [i32; 3],
) -> impl Iterator<Item = (usize, i32, Option<super::create_fluids::Fluid>)> + 'a {
    let blocks = bearing_at(&game.world, station, FLUID)
        .and_then(|bearing| mod_entity(game, bearing))
        .and_then(|bearing| compound_list(&bearing.nbt, "MovedBlocks"))
        .or_else(|| {
            let id = super::create_train_portable_items::fluid_train_at(&game.world, station)?;
            compound_list(super::create_train::carriage(game, id)?, "Blocks")
        })
        .unwrap_or_default();
    blocks.iter().enumerate().filter_map(|(i, block)| {
        let Tag::Compound(block) = block else {
            return None;
        };
        let state = compound(block, "BlockState")?;
        if super::create_machines::string(state, "Name").as_deref()
            != Some(super::create_fluid_tank::TANK)
        {
            return None;
        }
        let entity = compound(block, "Entity")?;
        if entity.contains_key(&"Controller".into()) {
            return None;
        }
        let width = int(entity, "Size").unwrap_or(1).clamp(1, 3);
        let height = int(entity, "Height").unwrap_or(1).clamp(1, 32);
        let fluid = compound(entity, "TankContent")
            .and_then(|tank| super::create_fluids::read_fluid(compound(tank, "Fluid")?));
        Some((i, 8_000 * width * width * height, fluid))
    })
}

pub(super) fn write_tank(
    game: &mut Game<'_>,
    station: [i32; 3],
    index: usize,
    fluid: super::create_fluids::Fluid,
) {
    let Some(bearing) = bearing_at(&game.world, station, FLUID) else {
        if let Some(id) = super::create_train_portable_items::fluid_train_at(&game.world, station)
            && write_train_tank(game, id, index, fluid)
        {
            renew(game, station);
        }
        return;
    };
    let changed = game.native_with_mod_block_entity(bearing, |bearing| {
        let Some(Tag::List(blocks)) = bearing.nbt.get_mut(&"MovedBlocks".into()) else {
            return false;
        };
        let Some(Tag::Compound(block)) = blocks.get_mut(index) else {
            return false;
        };
        let Some(Tag::Compound(entity)) = block.get_mut(&"Entity".into()) else {
            return false;
        };
        let mut tank = Compound::new();
        if fluid.amount > 0 {
            tank.insert("Fluid".into(), fluid.nbt());
        }
        entity.insert("TankContent".into(), Tag::Compound(tank));
        true
    });
    if changed == Some(true) {
        renew(game, station);
    }
}

fn write_train_tank(
    game: &mut Game<'_>,
    id: u32,
    index: usize,
    fluid: super::create_fluids::Fluid,
) -> bool {
    let Some(carriage) = super::create_train::carriage_mut(game, id) else {
        return false;
    };
    let Some(Tag::List(blocks)) = carriage.get_mut(&"Blocks".into()) else {
        return false;
    };
    let Some(Tag::Compound(block)) = blocks.get_mut(index) else {
        return false;
    };
    let Some(Tag::Compound(entity)) = block.get_mut(&"Entity".into()) else {
        return false;
    };
    let mut tank = Compound::new();
    if fluid.amount > 0 {
        tank.insert("Fluid".into(), fluid.nbt());
    }
    let old = entity.insert("TankContent".into(), Tag::Compound(tank));
    if old.as_ref() == entity.get(&"TankContent".into()) {
        return false;
    }
    carriage.insert("CargoIdleTicks".into(), Tag::Int(0));
    true
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
) -> Option<BlockStateId> {
    let name = level.registry.state(state)?.name.as_str();
    if !matches!(name, ITEM | FLUID) {
        return None;
    }
    let look = super::view_vector(context.yaw, context.pitch);
    let direction = Direction::ALL.into_iter().max_by(|a, b| {
        let dot = |direction: Direction| {
            direction
                .normal()
                .into_iter()
                .zip(look)
                .map(|(step, component)| f64::from(step) * component)
                .sum::<f64>()
        };
        dot(*a).total_cmp(&dot(*b))
    })?;
    let face = if context.sneaking {
        direction
    } else {
        direction.opposite()
    };
    level.native_state_with_property(state, "facing", super::create_fluids::name(face))
}
