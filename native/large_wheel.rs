use horizon_core::position::BlockPos;
use horizon_world::level::{PlacementContext, Ticks, flags};
use horizon_world::nbt::Tag;
use horizon_world::registry::BlockStateId;

use crate::containers::{BlockEntity, ModBlockEntity};

use super::create_machines::{
    DIRECTIONS, LARGE_WHEEL, award_wheel, axis_index, int, mod_entity, offset, water_flow_score,
    advancement_owner,
};
use super::{Game, GameLevel};

const RIM: &str = "create:water_wheel_structure";
const AXES: [&str; 3] = ["x", "y", "z"];
const FACINGS: [&str; 6] = ["east", "west", "up", "down", "south", "north"];
const SAMPLED_FLOW: usize = 3;
const LAZY_TICKS: usize = 4;
const FLOW_REFRESHED: usize = 5;
const LAZY_RATE: i32 = 60;

fn block_id(game: &Game<'_>, [x, y, z]: [i32; 3]) -> BlockStateId {
    game.world.block(x, y, z)
}

fn rim_parts(axis: usize) -> impl Iterator<Item = ([i32; 3], &'static str)> {
    DIRECTIONS
        .into_iter()
        .filter(move |arm| arm[axis] == 0)
        .flat_map(move |arm| {
            let a = (axis + 1) % 3;
            let b = (axis + 2) % 3;
            let mut clockwise = [0; 3];
            clockwise[a] = arm[b];
            clockwise[b] = -arm[a];
            [([0; 3], arm), (arm, clockwise)].map(|(start, step)| {
                let reverse = step.map(|value| -value);
                let direction = DIRECTIONS.iter().position(|dir| *dir == reverse).unwrap();
                (offset(start, step), FACINGS[direction])
            })
        })
}

fn fluid_arms(axis: usize) -> impl Iterator<Item = [i32; 3]> {
    DIRECTIONS
        .into_iter()
        .filter(move |arm| arm[axis] == 0)
        .flat_map(move |arm| {
            let mut side = [0; 3];
            side[(axis + 1) % 3] = arm[(axis + 2) % 3];
            side[(axis + 2) % 3] = -arm[(axis + 1) % 3];
            let middle = arm.map(|component| component * 2);
            [
                middle,
                offset(middle, side),
                offset(middle, side.map(|value| -value)),
            ]
        })
}

fn write_flow(world: &mut super::World, pos: [i32; 3], score: i32) {
    let [x, y, z] = pos;
    if let Some(BlockEntity::Mod(wheel)) = world.block_entities.get_mut(&(x, y, z)) {
        wheel.data.resize(FLOW_REFRESHED + 1, 0);
        wheel.data[FLOW_REFRESHED] = 1;
        if int(&wheel.nbt, "FlowScore") != Some(score) {
            wheel.nbt.insert("FlowScore".into(), Tag::Int(score));
            world.modified.insert((x >> 4, z >> 4));
        }
    }
}

// Capture the current before the scheduled block pass. A neighbouring rim
// update requests a turnover using this sample on the next game tick.
pub(super) fn prepare_tick(game: &mut Game<'_>) {
    let ticking = game.block_ticking_area();
    let wheels: Vec<_> = game
        .world
        .block_entity_tickers()
        .iter()
        .filter_map(|entry| {
            let (x, y, z) = entry.0;
            let pos = [x, y, z];
            if !ticking(x, z) || mod_entity(game, pos)?.id != LARGE_WHEEL {
                return None;
            }
            let axis = axis_index(&game.native_block_property(pos, "axis")?)?;
            let remaining = mod_entity(game, pos)?.data.get(LAZY_TICKS).copied();
            Some((pos, axis, remaining))
        })
        .collect();
    let registry = game.pack.assets.registry;
    let dimension = game.dim.id();
    for (pos, axis, remaining) in wheels {
        let parts: Vec<_> = rim_parts(axis)
            .filter_map(|(arm, facing)| {
                let at = offset(pos, arm);
                let state = block_id(game, at);
                let mut desired = registry.state(registry.default_state(RIM)?)?.clone();
                desired.properties.insert("facing".into(), facing.into());
                Some((at, state, registry.id(&desired)?))
            })
            .collect();
        if parts.iter().any(|&(_, existing, needed)| {
            existing != needed
                && (remaining.is_some() || !game.res.behaviours().is_replaceable(existing))
        }) {
            if let Some(air) = registry.default_state("minecraft:air") {
                game.native_set_block(dimension, pos, air, flags::UPDATE_ALL);
            }
            continue;
        }
        if remaining.is_none() {
            for (at, existing, needed) in parts {
                if existing != needed {
                    game.native_set_block(dimension, at, needed, flags::UPDATE_ALL);
                }
            }
        }
        let mut negative = [0; 3];
        negative[axis] = -1;
        let extension = game.native_block(offset(pos, negative)) == LARGE_WHEEL;
        let extension = if extension { "true" } else { "false" };
        if game.native_block_property(pos, "extension").as_deref() != Some(extension) {
            game.native_set_block_property(pos, "extension", extension);
        }
        let score = water_flow_score(game, pos, axis, fluid_arms(axis));
        let [x, y, z] = pos;
        if let Some(BlockEntity::Mod(wheel)) = game.world.block_entities.get_mut(&(x, y, z)) {
            wheel.data.resize(LAZY_TICKS + 1, 0);
            wheel.data[SAMPLED_FLOW] = score;
            wheel.data[LAZY_TICKS] = match remaining {
                Some(ticks) if ticks > 0 => ticks - 1,
                Some(_) => LAZY_RATE,
                None => LAZY_RATE - 1,
            };
        }
        if remaining.is_none() {
            write_flow(&mut game.world, pos, score);
        }
    }
}

// Create's periodic refresh is part of the block-entity tick, after water
// flows. The scheduled rim notification uses the earlier block-tick sample.
pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], wheel: &mut ModBlockEntity) {
    let lazy_refresh = wheel.data.get(LAZY_TICKS) == Some(&LAZY_RATE);
    let scheduled_refresh = wheel
        .data
        .get_mut(FLOW_REFRESHED)
        .is_some_and(|refreshed| std::mem::take(refreshed) != 0);
    if !lazy_refresh && !scheduled_refresh {
        return;
    }
    let Some(axis) = game
        .native_block_property(pos, "axis")
        .as_deref()
        .and_then(axis_index)
    else {
        return;
    };
    if lazy_refresh {
        let score = water_flow_score(game, pos, axis, fluid_arms(axis));
        wheel.nbt.insert("FlowScore".into(), Tag::Int(score));
    }
    if int(&wheel.nbt, "FlowScore").unwrap_or(0) != 0
        && let Some(owner) = advancement_owner(&wheel.nbt)
    {
        let lava =
            fluid_arms(axis).any(|arm| game.native_block(offset(pos, arm)) == "minecraft:lava");
        award_wheel(game, owner, lava);
    }
}

pub(super) fn rim_master(level: &GameLevel<'_>, mut pos: [i32; 3]) -> Option<([i32; 3], usize)> {
    for _ in 0..2 {
        let [x, y, z] = pos;
        let rim = level.registry.state(level.world.block(x, y, z))?;
        if rim.name != RIM {
            return None;
        }
        let i = FACINGS
            .iter()
            .position(|facing| Some(*facing) == rim.properties.get("facing").map(String::as_str))?;
        let step = DIRECTIONS[i];
        pos = offset(pos, step);
        let [x, y, z] = pos;
        let next = level.registry.state(level.world.block(x, y, z))?;
        if next.name == LARGE_WHEEL {
            let axis = axis_index(next.properties.get("axis")?)?;
            return (step[axis] == 0).then_some((pos, axis));
        }
    }
    None
}

pub(super) fn update_shape(
    level: &GameLevel<'_>,
    ticks: &mut Ticks,
    pos: [i32; 3],
    state: BlockStateId,
) {
    if level
        .registry
        .state(state)
        .is_none_or(|state| state.name != RIM)
    {
        return;
    }
    if let Some((master, _)) = rim_master(level, pos) {
        level.native_schedule_block_tick(ticks, master, LARGE_WHEEL, 1);
    } else {
        level.native_schedule_block_tick(ticks, pos, RIM, 1);
    }
}

pub(super) fn tick_block(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    state: BlockStateId,
) {
    let Some(block) = level.registry.state(state) else {
        return;
    };
    let at = [pos.x, pos.y, pos.z];
    if block.name == LARGE_WHEEL {
        let saved = match level.world.block_entities.get(&(pos.x, pos.y, pos.z)) {
            Some(BlockEntity::Mod(wheel)) => wheel.data.get(SAMPLED_FLOW).copied(),
            _ => None,
        };
        if let Some(score) = saved {
            write_flow(level.world, at, score);
        }
    } else if block.name == RIM
        && rim_master(level, at).is_none()
        && let Some(air) = level.registry.default_state("minecraft:air")
    {
        level
            .behaviours
            .set_block(level, ticks, pos, air, flags::UPDATE_ALL);
    }
}

pub(super) fn placement(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
    answer: &mut Option<Option<BlockStateId>>,
) {
    let Some(block) = level
        .registry
        .state(state)
        .filter(|state| state.name == LARGE_WHEEL)
    else {
        return;
    };
    let normal = context.face.normal();
    let axis = normal.iter().position(|&component| component != 0).unwrap();
    let pos = [context.pos.x, context.pos.y, context.pos.z];
    let space = rim_parts(axis).all(|(arm, _)| {
        let [x, y, z] = offset(pos, arm);
        level.behaviours.is_replaceable(level.world.block(x, y, z))
    });
    if !space {
        *answer = Some(None);
        return;
    }
    let mut placed = block.clone();
    placed.properties.insert("axis".into(), AXES[axis].into());
    *answer = Some(level.registry.id(&placed));
}
