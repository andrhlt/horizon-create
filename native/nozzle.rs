use horizon_core::{geometry::Direction, position::BlockPos};
use horizon_world::{level::PlacementContext, registry::BlockStateId};
use std::cell::RefCell;

use crate::containers::{BlockEntity, ModBlockEntity};

use super::create_fan::{facing, FAN};
use super::create_fluids::name as direction_name;
use super::create_machines::{mod_entity, offset, reading};
use super::{Game, GameLevel};

pub(super) const NOZZLE: &str = "create:nozzle";
const SCAN_DELAY: i32 = 5;
const STATE_LENGTH: usize = 3;
const MOB_ID_OFFSET: i64 = 1;

thread_local! {
    static LOCAL_PLAYER_AIR: RefCell<std::collections::HashMap<(String, [i32; 3]), LocalPlayerAirState>> = RefCell::default();
    static ACTIVE_PLAYER_NOZZLES: RefCell<std::collections::HashMap<(String, [i32; 3]), (f64, bool)>> = RefCell::default();
}

#[derive(Clone, Copy)]
struct LocalPlayerAirState {
    ticks_until_scan: i32,
    caught: bool,
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
) -> Option<BlockStateId> {
    if level.native_state_block(state) != Some(NOZZLE) {
        return None;
    }
    level.native_state_with_property(state, "facing", direction_name(context.face))
}

fn nozzle_facing(level: &GameLevel<'_>, state: BlockStateId) -> Option<Direction> {
    let state = level
        .registry
        .state(state)
        .filter(|state| state.name == NOZZLE)?;
    let value = state.properties.get("facing")?;
    Direction::ALL
        .into_iter()
        .find(|&side| direction_name(side) == value.as_str())
}

fn supports(level: &GameLevel<'_>, state: BlockStateId, facing: Direction) -> bool {
    level.registry.state(state).is_some_and(|state| {
        state.name == FAN
            && state.properties.get("facing").map(String::as_str) == Some(direction_name(facing))
    })
}

pub(super) fn survive(level: &GameLevel<'_>, at: BlockPos, state: BlockStateId) -> Option<bool> {
    let direction = nozzle_facing(level, state)?;
    let [x, y, z] = offset([at.x, at.y, at.z], direction.opposite().normal());
    Some(supports(level, level.world.block(x, y, z), direction))
}

pub(super) fn update_shape(
    level: &GameLevel<'_>,
    state: BlockStateId,
    changed_side: Direction,
    neighbour: BlockStateId,
) -> Option<BlockStateId> {
    let direction = nozzle_facing(level, state)?;
    if changed_side == direction.opposite() && !supports(level, neighbour, direction) {
        return level.registry.default_state("minecraft:air");
    }
    None
}

fn distance_and_offset(center: [f64; 3], position: [f64; 3]) -> (f64, [f64; 3]) {
    let diff: [f64; 3] = std::array::from_fn(|i| position[i] - center[i]);
    let distance = diff.iter().map(|d| d * d).sum::<f64>().sqrt();
    (distance, diff)
}

fn can_see(game: &Game<'_>, center: [f64; 3], position: [f64; 3], diff: [f64; 3]) -> bool {
    // The Java ray accepts a hit on the Nozzle itself. End this ray before
    // entering its block so it checks just the intervening collision shapes.
    let largest = diff.iter().map(|d| d.abs()).fold(0.0, f64::max);
    if largest <= 0.5 {
        return true;
    }
    let scale = (0.5 + 1e-7) / largest;
    let edge = std::array::from_fn(|axis| center[axis] + diff[axis] * scale.min(1.0));
    game.native_clear_between(game.native_dimension(), position, edge)
}

fn encode_mob_id(id: u32) -> i32 {
    -((i64::from(id) + MOB_ID_OFFSET) as i32)
}

fn decode_mob_id(id: i32) -> Option<u32> {
    (id < 0).then(|| (-i64::from(id) - MOB_ID_OFFSET) as u32)
}

fn mob_airflow(
    game: &mut Game<'_>,
    ids: &[u32],
    center: [f64; 3],
    range: f64,
    pushing: bool,
) -> Vec<u32> {
    let mut remaining = Vec::with_capacity(ids.len());
    for mob in game.mobs.iter_mut().filter(|mob| ids.contains(&mob.id)) {
        if mob.removed || !mob.alive() || mob.extra.crouching {
            continue;
        }
        let position = mob.position.components();
        let (distance, diff) = distance_and_offset(center, position);
        if distance > range {
            continue;
        }
        remaining.push(mob.id);
        if !pushing && distance < 1.5 {
            continue;
        }
        if distance >= 1e-4 {
            let sign = if pushing { 1.0 } else { -1.0 };
            let scale = sign * (range - distance) / 32.0 / distance;
            mob.velocity.x += diff[0] * scale;
            mob.velocity.y += diff[1] * scale;
            mob.velocity.z += diff[2] * scale;
        }
        mob.fall_distance = 0.0;
        mob.needs_sync = true;
    }
    remaining
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], nozzle: &mut ModBlockEntity) {
    let dimension = game.native_dimension().to_owned();
    let state = game.world.block(pos[0], pos[1], pos[2]);
    let Some(direction) = facing(game, state) else {
        ACTIVE_PLAYER_NOZZLES.with_borrow_mut(|active| active.remove(&(dimension.clone(), pos)));
        return;
    };
    if nozzle.data.len() < STATE_LENGTH {
        nozzle.data = vec![0, 0, SCAN_DELAY];
    }

    let previous_range = f32::from_bits(nozzle.data[0] as u32);
    let scan = nozzle.data[2] == 0;
    nozzle.data[2] = if scan { SCAN_DELAY } else { nozzle.data[2] - 1 };
    let mut caught: Vec<_> = nozzle.data[STATE_LENGTH..]
        .iter()
        .filter(|&&id| id >= 0)
        .map(|&id| id as u32)
        .collect();
    let mut caught_mobs: Vec<_> = nozzle.data[STATE_LENGTH..]
        .iter()
        .filter_map(|&id| decode_mob_id(id))
        .collect();
    let center = pos.map(|coordinate| f64::from(coordinate) + 0.5);
    if scan && previous_range > 0.0 {
        let half_range = f64::from(previous_range / 2.0);
        for item in game.native_item_entities(
            game.native_dimension(),
            center.map(|coordinate| coordinate - half_range),
            center.map(|coordinate| coordinate + half_range),
        ) {
            let (distance, diff) = distance_and_offset(center, item.position);
            if distance > f64::from(previous_range) {
                continue;
            }
            if !can_see(game, center, item.position, diff) {
                caught.retain(|&id| id != item.id);
            } else if !caught.contains(&item.id) {
                caught.push(item.id);
            }
        }
        for mob in &game.mobs {
            if mob.removed || !mob.alive() || mob.extra.crouching {
                caught_mobs.retain(|&id| id != mob.id);
                continue;
            }
            let position = mob.position.components();
            let (distance, diff) = distance_and_offset(center, position);
            if distance > f64::from(previous_range)
                || diff.iter().any(|value| value.abs() > half_range)
            {
                continue;
            }
            if can_see(game, center, position, diff) {
                if !caught_mobs.contains(&mob.id) {
                    caught_mobs.push(mob.id);
                }
            } else {
                caught_mobs.retain(|&id| id != mob.id);
            }
        }
    }

    let support = offset(pos, direction.opposite().normal());
    let rpm = mod_entity(game, support)
        .filter(|entity| entity.id == FAN)
        .map_or(0.0, |fan| reading(fan, 0));
    nozzle.data.truncate(STATE_LENGTH);
    if rpm == 0.0 {
        nozzle.data[0] = 0;
        ACTIVE_PLAYER_NOZZLES.with_borrow_mut(|active| active.remove(&(dimension, pos)));
        return;
    }

    let range = 3.0 + 17.0 * (rpm.abs() / 256.0).min(1.0);
    let pushing = (rpm > 0.0) == (direction.normal().iter().sum::<i32>() > 0);
    ACTIVE_PLAYER_NOZZLES.with_borrow_mut(|active| {
        active.insert((dimension, pos), (f64::from(range), pushing));
    });
    nozzle.data[0] = range.to_bits() as i32;
    nozzle.data[1] = i32::from(pushing);
    let range = f64::from(range);
    let mut active_items = Vec::with_capacity(caught.len());
    for id in caught {
        let Some(entity) = game
            .dropped
            .iter_mut()
            .find(|entity| entity.id == id && entity.stack.count > 0)
        else {
            continue;
        };
        let position = entity.position;
        let (distance, diff) = distance_and_offset(center, [position.x, position.y, position.z]);
        if distance > range {
            continue;
        }
        active_items.push(id);
        if !pushing && distance < 1.5 {
            continue;
        }
        if distance >= 1e-4 {
            let sign = if pushing { 1.0 } else { -1.0 };
            let scale = sign * (range - distance) / 128.0 / distance;
            entity.velocity.x += diff[0] * scale;
            entity.velocity.y += diff[1] * scale;
            entity.velocity.z += diff[2] * scale;
        }
        entity.fall_distance = 0.0;
        entity.needs_sync = true;
    }
    caught_mobs = mob_airflow(game, &caught_mobs, center, range, pushing);
    nozzle
        .data
        .extend(active_items.into_iter().map(|id| id as i32));
    nozzle
        .data
        .extend(caught_mobs.into_iter().map(encode_mob_id));
}

fn apply_player_airflow(game: &mut Game<'_>) {
    let Some(player) = game.player.as_ref() else {
        LOCAL_PLAYER_AIR.with_borrow_mut(|states| states.clear());
        return;
    };
    let player_position = player.position.components();
    let skip_player = player.shift_key_down
        || player.spectator
        || player.invulnerable && player.flying
        || player.health.dead_or_dying();
    let dimension = game.native_dimension().to_owned();
    let positions: Vec<_> = ACTIVE_PLAYER_NOZZLES.with_borrow(|active| {
        active
            .iter()
            .filter_map(|((world, pos), _)| (world == &dimension).then_some(*pos))
            .collect()
    });
    let mut candidates = Vec::new();
    for pos in &positions {
        let Some((range, pushing)) = ACTIVE_PLAYER_NOZZLES
            .with_borrow(|active| active.get(&(dimension.clone(), *pos)).copied())
        else {
            continue;
        };
        let center = pos.map(|coordinate| f64::from(coordinate) + 0.5);
        let (distance, diff) = distance_and_offset(center, player_position);
        let half_range = range / 2.0;
        let in_scan_box = diff.iter().all(|value| value.abs() <= half_range);
        let mut acquired = false;
        LOCAL_PLAYER_AIR.with_borrow_mut(|states| {
            let key = (dimension.clone(), *pos);
            let state = states.entry(key.clone()).or_insert(LocalPlayerAirState {
                ticks_until_scan: SCAN_DELAY,
                caught: false,
            });
            let scan = state.ticks_until_scan == 0;
            state.ticks_until_scan = if scan {
                SCAN_DELAY
            } else {
                state.ticks_until_scan - 1
            };
            if skip_player || distance > range {
                state.caught = false;
            } else if scan && in_scan_box {
                state.caught = can_see(game, center, player_position, diff);
            }
            acquired = state.caught;
        });
        if acquired {
            candidates.push((center, range, pushing, distance));
        }
    }
    LOCAL_PLAYER_AIR.with_borrow_mut(|states| {
        states.retain(|(world, pos), _| world != &dimension || positions.contains(pos));
    });
    let Some(player) = game.player.as_mut() else {
        return;
    };
    let candidate_count = candidates.len();
    for (center, range, pushing, distance) in candidates {
        if !pushing && distance < 1.5 {
            continue;
        }
        if distance >= 1e-4 {
            let position = player.position.components();
            let diff: [f64; 3] = std::array::from_fn(|axis| position[axis] - center[axis]);
            let sign = if pushing { 1.0 } else { -1.0 };
            let scale = sign * (range - distance) / 32.0 / distance;
            player.velocity.x += diff[0] * scale;
            player.velocity.y += diff[1] * scale;
            player.velocity.z += diff[2] * scale;
            // Horizon rebuilds a guest's velocity from its client-known
            // movement at the next turn. Preserve the authoritative result
            // by advancing the server position by this tick's impulse too.
            player.position.x += diff[0] * scale;
            player.position.z += diff[2] * scale;
        }
        player.fall_distance = 0.0;
    }
}

pub(super) fn player_tick(game: &mut Game<'_>) {
    apply_player_airflow(game);
}
