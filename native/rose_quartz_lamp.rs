use std::collections::{HashSet, VecDeque};

use horizon_core::{geometry::Direction, position::BlockPos};
use horizon_world::{
    level::{LevelAccess, Ticks, flags},
    registry::BlockStateId,
};

use super::{Game, GameLevel};

pub(super) const LAMP: &str = "create:rose_quartz_lamp";

pub(super) fn is_lamp(level: &GameLevel<'_>, state: BlockStateId) -> bool {
    level.native_state_block(state) == Some(LAMP)
}

fn property(level: &GameLevel<'_>, state: BlockStateId, key: &str) -> bool {
    level
        .registry
        .state(state)
        .and_then(|block| block.properties.get(key))
        .is_some_and(|value| value == "true")
}

fn with(level: &GameLevel<'_>, state: BlockStateId, key: &str, value: bool) -> BlockStateId {
    level
        .native_state_with_property(state, key, if value { "true" } else { "false" })
        .unwrap_or(state)
}

fn relative(pos: BlockPos, dir: Direction) -> BlockPos {
    let [x, y, z] = dir.normal();
    pos.offset(x, y, z)
}

fn notify(level: &mut GameLevel<'_>, ticks: &mut Ticks, pos: BlockPos, state: BlockStateId) {
    let blocks = level.behaviours;
    blocks.update_neighbors_at(level, ticks, pos, blocks.block(state));
}

fn cluster(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    origin: BlockPos,
    mut visit: impl FnMut(&mut GameLevel<'_>, &mut Ticks, BlockPos, BlockStateId),
) {
    let mut seen = HashSet::from([origin]);
    let mut frontier = VecDeque::from([origin]);
    while let Some(at) = frontier.pop_front() {
        for dir in Direction::ALL {
            let pos = relative(at, dir);
            let distance =
                pos.x.abs_diff(origin.x) + pos.y.abs_diff(origin.y) + pos.z.abs_diff(origin.z);
            if distance > 16 || !seen.insert(pos) {
                continue;
            }
            let state = level.block_state(pos);
            if is_lamp(level, state) {
                visit(level, ticks, pos, state);
                frontier.push_back(pos);
            }
        }
    }
}

fn schedule(level: &GameLevel<'_>, ticks: &mut Ticks, pos: BlockPos) {
    level.native_schedule_block_tick(ticks, [pos.x, pos.y, pos.z], LAMP, 1);
}

pub(super) fn neighbor(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    state: BlockStateId,
) {
    let prior = property(level, state, "powered");
    let blocks = level.behaviours;
    let powered = blocks.has_neighbor_signal(level, ticks, pos);
    if prior == powered {
        return;
    }
    if !powered {
        let next = with(level, state, "powered", false);
        blocks.set_block(level, ticks, pos, next, flags::UPDATE_CLIENTS);
        return;
    }
    cluster(level, ticks, pos, |level, ticks, neighbor, state| {
        let next = with(level, state, "powering", false);
        blocks.set_block(level, ticks, neighbor, next, flags::UPDATE_CLIENTS);
        schedule(level, ticks, neighbor);
    });
    let next = with(level, state, "powered", true);
    let next = with(level, next, "powering", true);
    let next = with(level, next, "activate", true);
    blocks.set_block(level, ticks, pos, next, flags::UPDATE_CLIENTS);
    notify(level, ticks, pos, next);
    schedule(level, ticks, pos);
}

pub(super) fn tick(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    state: BlockStateId,
) {
    if !is_lamp(level, state) {
        return;
    }
    let activate = property(level, state, "activate");
    let mut next = state;
    if activate || property(level, state, "powering") {
        next = with(level, state, "activate", false);
        next = with(level, next, "powering", activate);
        level
            .behaviours
            .set_block(level, ticks, pos, next, flags::UPDATE_CLIENTS);
    }
    notify(level, ticks, pos, next);
}

pub(super) fn signal(
    level: &GameLevel<'_>,
    pos: BlockPos,
    state: BlockStateId,
    direction: Direction,
    direct: bool,
    out: &mut i32,
) {
    if direct || !is_lamp(level, state) {
        return;
    }
    // Horizon supplies the face toward the receiving block.
    let to = level.block_state(relative(pos, direction));
    if is_lamp(level, to) {
        *out = 0;
    } else if level.native_state_block(to) == Some("minecraft:comparator") {
        let mut at = pos;
        *out = 0;
        for strength in (1..=15).rev() {
            let candidate = level.block_state(at);
            if !is_lamp(level, candidate) {
                break;
            }
            if property(level, candidate, "powering") {
                *out = strength;
                break;
            }
            at = relative(at, direction.opposite());
        }
    } else {
        *out = if property(level, state, "powering") {
            15
        } else {
            0
        };
    }
}

pub(super) fn wrench(game: &mut Game<'_>, at: [i32; 3]) -> bool {
    game.with_level(|blocks, level, ticks| {
        let pos = BlockPos::new(at[0], at[1], at[2]);
        let current = level.block_state(pos);
        let next = with(
            level,
            current,
            "powering",
            !property(level, current, "powering"),
        );
        if !blocks.set_block(level, ticks, pos, next, flags::UPDATE_ALL) {
            return false;
        }
        cluster(level, ticks, pos, notify);
        true
    })
}
