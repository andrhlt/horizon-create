use horizon_core::{geometry::Direction, position::BlockPos, ticks::TickPriority};
use horizon_world::{
    level::{LevelAccess, PlacementContext, Ticks, flags},
    nbt::{Compound, Tag},
    registry::BlockStateId,
};

use super::create_contact::face_name;
use crate::containers::ModBlockEntity;

use super::{Game, GameLevel};

pub(super) const TOGGLE: &str = "create:powered_toggle_latch";
pub(super) const POWERED: &str = "create:powered_latch";
const EXTENDER: &str = "create:pulse_extender";
const REPEATER: &str = "create:pulse_repeater";
const TIMER: &str = "create:pulse_timer";

pub(super) fn is_pulse(block: &str) -> bool {
    matches!(block, EXTENDER | REPEATER | TIMER)
}

pub(super) fn pulse_nbt(block: &str) -> Compound {
    Compound::from([
        ("State".into(), Tag::Int(0)),
        ("ScrollValue".into(), Tag::Int(pulse_default(block))),
    ])
}

fn pulse_default(block: &str) -> i32 {
    if block == TIMER { 20 } else { 2 }
}

pub(super) fn is_latch(level: &GameLevel<'_>, state: BlockStateId) -> bool {
    matches!(level.native_state_block(state), Some(TOGGLE | POWERED))
}

pub(super) fn is_diode(level: &GameLevel<'_>, state: BlockStateId) -> bool {
    is_latch(level, state) || level.native_state_block(state).is_some_and(is_pulse)
}

fn output(level: &GameLevel<'_>, state: BlockStateId) -> bool {
    property(level, state, "powering") ^ property(level, state, "inverted")
}

fn property(level: &GameLevel<'_>, state: BlockStateId, key: &str) -> bool {
    level
        .registry
        .state(state)
        .and_then(|row| row.properties.get(key))
        .is_some_and(|value| value == "true")
}

fn facing(level: &GameLevel<'_>, state: BlockStateId) -> Direction {
    match level
        .registry
        .state(state)
        .and_then(|row| row.properties.get("facing"))
        .map(String::as_str)
    {
        Some("east") => Direction::East,
        Some("south") => Direction::South,
        Some("west") => Direction::West,
        _ => Direction::North,
    }
}

fn with(level: &GameLevel<'_>, state: BlockStateId, key: &str, value: bool) -> BlockStateId {
    level
        .native_state_with_property(state, key, if value { "true" } else { "false" })
        .unwrap_or(state)
}

fn relative(pos: BlockPos, direction: Direction) -> BlockPos {
    let [x, y, z] = direction.normal();
    pos.offset(x, y, z)
}

fn has_input(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    direction: Direction,
) -> bool {
    let input = relative(pos, direction);
    let behaviours = level.behaviours;
    if behaviours.signal_at(level, ticks, input, direction) > 0 {
        return true;
    }
    let state = level.block_state(input);
    level.registry.state(state).is_some_and(|block| {
        block.name == "minecraft:redstone_wire"
            && block
                .properties
                .get("power")
                .is_some_and(|power| power != "0")
    })
}

fn side_input(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    direction: Direction,
) -> bool {
    let axis = if matches!(direction, Direction::North | Direction::South) {
        Direction::East
    } else {
        Direction::North
    };
    has_input(level, ticks, pos, axis) || has_input(level, ticks, pos, axis.opposite())
}

fn schedule(
    level: &GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    state: BlockStateId,
    priority: TickPriority,
) {
    ticks.schedule_block(
        level.game_time(),
        pos,
        level.behaviours.block(state),
        if level.native_state_block(state).is_some_and(is_pulse) {
            2
        } else {
            1
        },
        priority,
    );
}

pub(super) fn neighbor(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    state: BlockStateId,
) {
    let direction = facing(level, state);
    let back = property(level, state, "powered");
    let side = property(level, state, "powered_side");
    let side_changed = level.native_state_block(state) == Some(POWERED)
        && side != side_input(level, ticks, pos, direction);
    if !(back != has_input(level, ticks, pos, direction) || side_changed)
        || ticks.will_block_tick_this_tick(pos, level.behaviours.block(state))
    {
        return;
    }
    let forward = level.block_state(relative(pos, direction.opposite()));
    let facing_chain = (matches!(
        level.native_state_block(forward),
        Some("minecraft:repeater" | "minecraft:comparator")
    ) || is_diode(level, forward))
        && facing(level, forward) != direction;
    let priority = if facing_chain {
        TickPriority::ExtremelyHigh
    } else if back || side {
        TickPriority::VeryHigh
    } else {
        TickPriority::High
    };
    schedule(level, ticks, pos, state, priority);
}

fn set_state(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    old: BlockStateId,
    new: BlockStateId,
) -> bool {
    let blocks = level.behaviours;
    if old == new || !blocks.set_block(level, ticks, pos, new, flags::UPDATE_CLIENTS) {
        return false;
    }
    if output(level, old) != output(level, new) {
        let output = relative(pos, facing(level, new).opposite());
        let block = blocks.block(new);
        blocks.update_neighbors_at(level, ticks, pos, block);
        blocks.update_neighbors_at(level, ticks, output, block);
    }
    true
}

pub(super) fn tick(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    state: BlockStateId,
) {
    if !is_diode(level, state) {
        return;
    }
    let direction = facing(level, state);
    let back = property(level, state, "powered");
    let back_now = has_input(level, ticks, pos, direction);
    if level.native_state_block(state).is_some_and(is_pulse) {
        if back && !back_now {
            set_state(
                level,
                ticks,
                pos,
                state,
                with(level, state, "powered", false),
            );
        } else if !back {
            set_state(
                level,
                ticks,
                pos,
                state,
                with(level, state, "powered", true),
            );
            if !back_now {
                schedule(level, ticks, pos, state, TickPriority::VeryHigh);
            }
        }
        return;
    }
    let output = property(level, state, "powering");
    let mut next = state;
    if level.native_state_block(state) == Some(TOGGLE) {
        next = with(level, next, "powered", !back || back_now);
        if !back {
            next = with(level, next, "powering", !output);
            if !back_now {
                schedule(level, ticks, pos, state, TickPriority::VeryHigh);
            }
        }
    } else {
        let side = property(level, state, "powered_side");
        let side_now = side_input(level, ticks, pos, direction);
        if back != back_now {
            next = with(level, next, "powered", back_now);
            if back_now || side {
                next = with(level, next, "powering", back_now);
            }
        }
        if side != side_now {
            next = with(level, next, "powered_side", side_now);
            if side_now || back {
                next = with(level, next, "powering", !side_now);
            }
        }
    }
    set_state(level, ticks, pos, state, next);
}

pub(super) fn signal(
    level: &GameLevel<'_>,
    state: BlockStateId,
    out_face: Direction,
    signal: &mut i32,
) {
    if is_diode(level, state) {
        *signal = if facing(level, state).opposite() == out_face && output(level, state) {
            15
        } else {
            0
        };
    }
}

pub(super) fn wire_connection(
    level: &GameLevel<'_>,
    state: BlockStateId,
    direction: Option<Direction>,
) -> Option<bool> {
    if !is_diode(level, state) {
        return None;
    }
    Some(direction.is_some_and(|side| {
        matches!(
            side,
            Direction::North | Direction::South | Direction::East | Direction::West
        ) && (level.native_state_block(state) == Some(POWERED)
            || side == facing(level, state)
            || side == facing(level, state).opposite())
    }))
}

pub(super) fn placement(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
) -> Option<Option<BlockStateId>> {
    if !is_diode(level, state) {
        return None;
    }
    let support = level.block_state(context.pos.offset(0, -1, 0));
    if !level.behaviours.is_face_sturdy(support, Direction::Up) {
        return Some(None);
    }
    let quadrant = ((f64::from(context.yaw) / 90.0 + 0.5).floor() as i32).rem_euclid(4);
    let opposite = [
        Direction::North,
        Direction::East,
        Direction::South,
        Direction::West,
    ][quadrant as usize];
    Some(level.native_state_with_property(state, "facing", face_name(opposite)))
}

pub(super) fn support_change(
    level: &GameLevel<'_>,
    state: BlockStateId,
    direction: Direction,
    neighbor: BlockStateId,
    result: &mut Option<BlockStateId>,
) {
    if direction == Direction::Down
        && is_diode(level, state)
        && !level.behaviours.is_face_sturdy(neighbor, Direction::Up)
    {
        *result = level.registry.default_state("minecraft:air");
    }
}

pub(super) fn manual(game: &mut Game<'_>, at: [i32; 3], canceled: &mut bool) {
    if *canceled
        || !game.native_authoritative()
        || game.hand != super::Hand::Main
        || game.native_sneaking()
        || game
            .held()
            .is_some_and(|item| item.item.as_ref() == "create:wrench")
    {
        return;
    }
    let block = game.native_block(at);
    if !matches!(block.as_str(), TOGGLE | POWERED) && !is_pulse(&block) {
        return;
    }
    if is_pulse(&block) && !game.may_build() {
        return;
    }
    *canceled = toggle(game, at, &block);
}

pub(super) fn pulse_short_action(game: &mut Game<'_>, at: [i32; 3]) {
    let block = game.native_block(at);
    if !is_pulse(&block)
        || !game.may_build()
        || game.native_sneaking()
        || game
            .stack_in(game.selected)
            .is_some_and(|item| item.item.as_ref() == "create:wrench")
    {
        return;
    }
    toggle(game, at, &block);
}

fn toggle(game: &mut Game<'_>, at: [i32; 3], block: &str) -> bool {
    let pos = BlockPos::new(at[0], at[1], at[2]);
    let changed = game.with_level(|_, level, ticks| {
        let state = level.block_state(pos);
        if level.native_state_block(state) == Some(POWERED)
            && property(level, state, "powered") != property(level, state, "powered_side")
        {
            return None;
        }
        let key = if is_pulse(block) {
            "inverted"
        } else {
            "powering"
        };
        let enabled = !property(level, state, key);
        let next = with(level, state, key, enabled);
        set_state(level, ticks, pos, state, next).then_some(enabled)
    });
    if let Some(output) = changed {
        game.native_play_sound_in_place(
            "minecraft:block.lever.click",
            at.map(|v| f64::from(v) + 0.5),
            4,
            0.3,
            if output { 0.6 } else { 0.5 },
        );
        true
    } else {
        false
    }
}

fn pulse_interval(entity: Option<&ModBlockEntity>, block: &str) -> i32 {
    entity
        .and_then(|entity| super::create_machines::int(&entity.nbt, "ScrollValue"))
        .unwrap_or_else(|| pulse_default(block))
        .clamp(2, 72_000)
}

pub(super) fn pulse_selection(entity: Option<&ModBlockEntity>, block: &str) -> (u8, i32) {
    let interval = pulse_interval(entity, block);
    if interval > 1_200 {
        (2, interval / 1_200)
    } else if interval > 60 {
        (1, interval / 20)
    } else {
        (0, interval)
    }
}

pub(super) fn set_pulse_interval(game: &mut Game<'_>, at: [i32; 3], row: u8, value: i32) {
    let multiplier = match row {
        0 => 1,
        1 => 20,
        _ => 1_200,
    };
    let interval = (value.clamp(1, 60) * multiplier).max(2);
    let changed = game.native_with_mod_block_entity(at, |entity| {
        if !is_pulse(&entity.id) || pulse_interval(Some(entity), &entity.id) == interval {
            return false;
        }
        let state = super::create_machines::int(&entity.nbt, "State").unwrap_or(0);
        entity
            .nbt
            .insert("State".into(), Tag::Int(state.clamp(0, interval)));
        entity.nbt.insert("ScrollValue".into(), Tag::Int(interval));
        true
    });
    if changed == Some(true) {
        super::create_speed_controller::setting_feedback(game, at);
        game.native_block_entity_sync(at);
    }
}

pub(super) fn pulse_tick(game: &mut Game<'_>, at: [i32; 3], entity: &mut ModBlockEntity) {
    let pos = BlockPos::new(at[0], at[1], at[2]);
    let read = |key: &str, default: i32| match entity.nbt.get(&key.into()) {
        Some(Tag::Int(value)) => *value,
        _ => default,
    };
    let value = read("State", 0);
    let interval = read("ScrollValue", pulse_default(&entity.id)).clamp(2, 72_000);
    let updated = game.with_level(|_, level, ticks| {
        let state = level.block_state(pos);
        let powered = property(level, state, "powered");
        let powering = property(level, state, "powering");
        let (next, output) = match entity.id.as_str() {
            EXTENDER if powered => (interval, true),
            EXTENDER if value <= 0 => (value, powering),
            EXTENDER if value == 1 => (0, false),
            EXTENDER => (value - 1, powering),
            REPEATER if value <= 0 && !powered => (value, powering),
            REPEATER if value > interval + 1 => {
                (if !powered && !powering { 0 } else { value }, powering)
            }
            REPEATER => {
                let next = value + 1;
                let output = if next == interval - 1 {
                    true
                } else if next == interval + 1 {
                    false
                } else {
                    powering
                };
                (next, output)
            }
            TIMER => {
                let next = if powered || value >= interval - 1 {
                    0
                } else {
                    value + 1
                };
                (
                    next,
                    !powered && if interval == 2 { next == 0 } else { next <= 1 },
                )
            }
            _ => return value,
        };
        let new_state = with(level, state, "powering", output);
        set_state(level, ticks, pos, state, new_state);
        next
    });
    entity.nbt.insert("State".into(), Tag::Int(updated));
}
