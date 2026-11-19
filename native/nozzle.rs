use horizon_core::{geometry::Direction, position::BlockPos};
use horizon_world::{level::PlacementContext, registry::BlockStateId};

use crate::containers::ModBlockEntity;

use super::create_fan::{FAN, facing};
use super::create_fluids::name as direction_name;
use super::create_machines::{mod_entity, offset, reading};
use super::{Game, GameLevel};

pub(super) const NOZZLE: &str = "create:nozzle";
const SCAN_DELAY: i32 = 5;
const STATE_LENGTH: usize = 3;

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
    let diff = std::array::from_fn(|i| position[i] - center[i]);
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

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], nozzle: &mut ModBlockEntity) {
    let state = game.world.block(pos[0], pos[1], pos[2]);
    let Some(direction) = facing(game, state) else {
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
        .map(|&id| id as u32)
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
    }

    let support = offset(pos, direction.opposite().normal());
    let rpm = mod_entity(game, support)
        .filter(|entity| entity.id == FAN)
        .map_or(0.0, |fan| reading(fan, 0));
    nozzle.data.truncate(STATE_LENGTH);
    if rpm == 0.0 {
        nozzle.data[0] = 0;
        return;
    }

    let range = 3.0 + 17.0 * (rpm.abs() / 256.0).min(1.0);
    let pushing = (rpm > 0.0) == (direction.normal().iter().sum::<i32>() > 0);
    nozzle.data[0] = range.to_bits() as i32;
    nozzle.data[1] = i32::from(pushing);
    let range = f64::from(range);
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
        nozzle.data.push(id as i32);
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
}
