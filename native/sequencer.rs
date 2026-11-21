use horizon_core::position::BlockPos;
use horizon_world::{
    level::{Ticks, flags},
    nbt::{Compound, Tag},
    registry::BlockStateId,
};
use serde::{Deserialize, Serialize};

use crate::containers::{BlockEntity, ModBlockEntity};

use super::create_machines::{float, int, mod_entity, set_float};
use super::{Game, GameLevel};

pub(super) const SEQUENCER: &str = "create:sequenced_gearshift";

pub(super) fn neighbor(level: &GameLevel<'_>, ticks: &mut Ticks, pos: BlockPos) {
    level.native_schedule_block_tick(ticks, [pos.x, pos.y, pos.z], SEQUENCER, 1);
}

pub(super) fn tick_block(level: &mut GameLevel<'_>, ticks: &mut Ticks, pos: BlockPos, state: BlockStateId) {
    if level.native_state_block(state) != Some(SEQUENCER) {
        return;
    }
    let idle = matches!(level.world.block_entities.get(&(pos.x, pos.y, pos.z)),
        Some(BlockEntity::Mod(entity)) if int(&entity.nbt, "InstructionIndex").unwrap_or(-1) < 0);
    let blocks = level.behaviours;
    if idle && !blocks.has_neighbor_signal(level, ticks, pos) {
        level.native_set_block_property(ticks, [pos.x, pos.y, pos.z], "state", "0", flags::UPDATE_ALL);
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub(super) enum Mode {
    TurnAngle,
    TurnDistance,
    Delay,
    Await,
    End,
}

#[derive(Clone, Copy, Serialize, Deserialize)]
pub(super) struct Instruction {
    pub(super) mode: Mode,
    pub(super) value: i32,
    pub(super) modifier: i32,
}

impl Instruction {
    fn read(data: &Compound) -> Option<Self> {
        let text = |key: &str| match data.get(&key.into()) {
            Some(Tag::String(text)) => Some(text.to_string_lossy()),
            _ => None,
        };
        let mode = match text("Type")?.as_str() {
            "TURN_ANGLE" => Mode::TurnAngle,
            "TURN_DISTANCE" => Mode::TurnDistance,
            "DELAY" => Mode::Delay,
            "AWAIT" => Mode::Await,
            "END" => Mode::End,
            _ => return None,
        };
        let modifier = match text("Modifier").as_deref() {
            Some("FORWARD_FAST") => 2,
            Some("BACK") => -1,
            Some("BACK_FAST") => -2,
            _ => 1,
        };
        Some(Self {
            mode,
            value: int(data, "Value").unwrap_or(1),
            modifier,
        })
    }

    fn tag(self) -> Tag {
        let kind = match self.mode {
            Mode::TurnAngle => "TURN_ANGLE",
            Mode::TurnDistance => "TURN_DISTANCE",
            Mode::Delay => "DELAY",
            Mode::Await => "AWAIT",
            Mode::End => "END",
        };
        let modifier = match self.modifier {
            2 => "FORWARD_FAST",
            -1 => "BACK",
            -2 => "BACK_FAST",
            _ => "FORWARD",
        };
        Tag::Compound(Compound::from([
            ("Type".into(), Tag::String(kind.into())),
            ("Modifier".into(), Tag::String(modifier.into())),
            ("Value".into(), Tag::Int(self.value)),
        ]))
    }

    fn speed_modifier(self) -> i32 {
        if matches!(self.mode, Mode::TurnAngle | Mode::TurnDistance) {
            self.modifier
        } else {
            0
        }
    }

    fn progress(self, rpm: f32) -> f32 {
        match self.mode {
            Mode::TurnAngle => rpm * 360.0 / 60.0 / 20.0,
            Mode::TurnDistance => rpm / 512.0,
            Mode::Delay => 1.0,
            _ => 0.0,
        }
    }

    fn duration(self, rpm: f32, progress: f32) -> i32 {
        let remaining = self.value as f32 - progress;
        match self.mode {
            Mode::TurnAngle | Mode::TurnDistance => {
                let speed = self.progress(rpm * self.modifier as f32).abs();
                (remaining / speed).ceil() as i32 + 2
            }
            Mode::Delay => remaining as i32,
            Mode::Await => -1,
            Mode::End => 0,
        }
    }
}

fn instruction(data: &Compound, index: i32) -> Option<Instruction> {
    let index = usize::try_from(index).ok()?;
    match data.get(&"Instructions".into()) {
        Some(Tag::List(items)) if !items.is_empty() => {
            let Tag::Compound(item) = items.get(index)? else {
                return None;
            };
            Instruction::read(item)
        }
        _ => (index == 0).then_some(Instruction {
            mode: Mode::TurnAngle,
            value: 90,
            modifier: 1,
        }),
    }
}

#[derive(Clone, Copy)]
pub(super) enum Motion {
    Angle(f64),
    Distance(f32),
}

pub(super) fn distance_limit(motion: Option<Motion>, rpm: f32) -> Option<f32> {
    match motion {
        Some(Motion::Distance(relative)) => Some(relative * rpm.abs()),
        _ => None,
    }
}

pub(super) fn output(entity: Option<&ModBlockEntity>) -> (i32, i32, Option<Motion>) {
    let Some(entity) = entity else {
        return (0, 0, None);
    };
    let side = int(&entity.nbt, "InputSide").unwrap_or(0);
    let active = int(&entity.nbt, "InstructionIndex").unwrap_or(-1);
    let Some(current) = instruction(&entity.nbt, active) else {
        return (0, side, None);
    };
    let input = entity
        .data
        .first()
        .map(|bits| f32::from_bits(*bits as u32))
        .unwrap_or_else(|| float(&entity.nbt, "Speed").unwrap_or(0.0));
    let rpm = input * current.speed_modifier() as f32;
    let sequence = if rpm == 0.0 {
        None
    } else {
        let value = (current.value as f32 / rpm).abs();
        match current.mode {
            Mode::TurnAngle => Some(Motion::Angle(
                (f64::from(current.value) / f64::from(rpm)).abs(),
            )),
            Mode::TurnDistance => Some(Motion::Distance(value)),
            _ => None,
        }
    };
    (current.speed_modifier(), side, sequence)
}

pub(super) fn default_program() -> Vec<Instruction> {
    vec![
        Instruction {
            mode: Mode::TurnAngle,
            value: 90,
            modifier: 1,
        },
        Instruction {
            mode: Mode::End,
            value: 1,
            modifier: 1,
        },
    ]
}

pub(super) fn program(entity: Option<&ModBlockEntity>) -> Vec<Instruction> {
    if let Some(entity) = entity
        && let Some(Tag::List(rows)) = entity.nbt.get(&"Instructions".into())
        && !rows.is_empty()
    {
        let instructions = rows
            .iter()
            .take(5)
            .filter_map(|row| {
                if let Tag::Compound(row) = row {
                    Instruction::read(row)
                } else {
                    None
                }
            })
            .collect::<Vec<_>>();
        if !instructions.is_empty() {
            return instructions;
        }
    }
    default_program()
}

fn program_tag(program: &[Instruction]) -> Tag {
    Tag::List(program.iter().map(|row| row.tag()).collect())
}

pub(super) fn new_tag() -> Compound {
    Compound::from([
        ("InstructionIndex".into(), Tag::Int(-1)),
        ("InstructionDuration".into(), Tag::Int(-1)),
        ("Instructions".into(), program_tag(&default_program())),
    ])
}

pub(super) fn set_program(game: &mut Game<'_>, pos: [i32; 3], program: &[Instruction]) {
    let powered = game.native_neighbor_signal(game.native_dimension(), pos) > 0;
    let written = game.native_with_mod_block_entity(pos, |entity| {
        if entity.id != SEQUENCER {
            return false;
        }
        entity.nbt.insert("InstructionIndex".into(), Tag::Int(-1));
        entity
            .nbt
            .insert("InstructionDuration".into(), Tag::Int(-1));
        entity.nbt.insert("Timer".into(), Tag::Int(0));
        entity
            .nbt
            .insert("Instructions".into(), program_tag(program));
        set_float(&mut entity.nbt, "InstructionProgress", 0.0);
        true
    });
    if written == Some(true) {
        if !powered {
            game.native_set_block_property(pos, "state", "0");
        }
        super::create_machines::refresh_connected_network(game, pos);
    }
}

pub(super) fn has_analog_output(level: &GameLevel<'_>, state: BlockStateId, output: &mut bool) {
    *output |= level.native_state_block(state) == Some(SEQUENCER);
}

pub(super) fn analog_output(level: &GameLevel<'_>, state: BlockStateId, output: &mut i32) {
    if level.native_state_block(state) == Some(SEQUENCER)
        && let Some(step) = level
            .registry
            .state(state)
            .and_then(|state| state.properties.get("state"))
            .and_then(|state| state.parse().ok())
    {
        *output = step;
    }
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &horizon_world::level::PlacementContext,
) -> Option<Option<BlockStateId>> {
    if level.native_state_block(state) != Some(SEQUENCER) {
        return None;
    }
    let aim = context.nearest_looking_direction();
    let direction = if context.sneaking {
        aim
    } else {
        super::create_hand_crank::preferred_direction(level, context.pos).unwrap_or(aim)
    };
    let [x, y, _] = direction.normal();
    let axis = if y != 0 {
        if ((f64::from(context.yaw) / 90.0 + 0.5).floor() as i32) & 1 == 0 {
            "z"
        } else {
            "x"
        }
    } else if x == 0 {
        "z"
    } else {
        "x"
    };
    let vertical = if y != 0 { "true" } else { "false" };
    Some(
        level
            .native_state_with_property(state, "axis", axis)
            .and_then(|state| level.native_state_with_property(state, "vertical", vertical)),
    )
}

/// Returns whether the original rotation sound is played.
pub(super) fn wrench_pose(
    game: &mut Game<'_>,
    pos: [i32; 3],
    face: horizon_core::geometry::Direction,
) -> bool {
    let Some(horizontal) = game.native_block_property(pos, "axis") else {
        return false;
    };
    let [x, y, _] = face.normal();
    if y != 0 {
        let axis = if horizontal == "x" { "z" } else { "x" };
        return game.native_set_block_property(pos, "axis", axis);
    }
    if horizontal != if x == 0 { "z" } else { "x" } {
        let vertical = game.native_block_property(pos, "vertical");
        game.native_set_block_property(
            pos,
            "vertical",
            if vertical.as_deref() == Some("true") {
                "false"
            } else {
                "true"
            },
        );
    }
    false
}

pub(super) fn prepare(game: &mut Game<'_>) {
    let ticking = game.block_ticking_area();
    // On the first block-entity pass after a world load, tickers have not yet
    // promoted the loaded chunk's pending entries: the tick-list table is
    // built later in tick_block_entities_inner. Include loaded sequencers for
    // this one prepass so their instruction clock resumes on the first tick.
    let positions: Vec<_> = if game.world.block_entities.has_states() {
        game.world
            .block_entity_tickers()
            .iter()
            .filter_map(|entry| {
                let (x, y, z) = entry.0;
                let pos = [x, y, z];
                (ticking(x, z)
                    && mod_entity(game, pos).is_some_and(|entity| entity.id == SEQUENCER))
                .then_some(pos)
            })
            .collect()
    } else {
        game.world
            .block_entities
            .iter()
            .filter_map(|(&(x, y, z), entity)| {
                let pos = [x, y, z];
                (ticking(x, z)
                    && matches!(entity, BlockEntity::Mod(entity) if entity.id == SEQUENCER))
                .then_some(pos)
            })
            .collect()
    };
    for pos in positions {
        let (rpm, from) = super::create_machines::sequencer_input(game, pos);
        let input_side = from.into_iter().sum();
        let powered = game.native_neighbor_signal(game.native_dimension(), pos) > 0;
        let block_step = game
            .native_block_property(pos, "state")
            .and_then(|step| step.parse().ok())
            .unwrap_or(0);
        let Some(entity) = mod_entity(game, pos) else {
            continue;
        };
        let mut active = int(&entity.nbt, "InstructionIndex").unwrap_or(-1);
        let mut duration = int(&entity.nbt, "InstructionDuration").unwrap_or(-1);
        let mut progress = float(&entity.nbt, "InstructionProgress").unwrap_or(0.0);
        let mut timer = int(&entity.nbt, "Timer").unwrap_or(0);
        let previously_powered = int(&entity.nbt, "PrevPowered") == Some(1);
        let previous_input_side = int(&entity.nbt, "InputSide").unwrap_or(0);
        let previous_reported_rpm = float(&entity.nbt, "Speed").unwrap_or(0.0);
        let previous_rpm = entity
            .data
            .first()
            .map(|bits| f32::from_bits(*bits as u32))
            .unwrap_or(previous_reported_rpm);
        let mut step = block_step;
        let mut start = None;
        let mut elapsed_transition = false;

        if rpm == 0.0 && active >= 0 {
            start = Some(-1);
        } else if powered
            && !previously_powered
            && instruction(&entity.nbt, active).is_some_and(|current| current.mode == Mode::Await)
        {
            start = Some(active + 1);
        } else if active < 0 && powered && block_step == 0 && rpm != 0.0 {
            start = Some(0);
        }
        if start.is_none()
            && let Some(current) = instruction(&entity.nbt, active)
        {
            if previous_rpm.abs() != rpm.abs() {
                duration = current.duration(rpm, progress);
                timer = 0;
            }
            if duration >= 0 {
                if timer < duration {
                    timer += 1;
                    progress += current.progress(rpm);
                } else {
                    start = Some(active + 1);
                    elapsed_transition = true;
                }
            }
        }

        if let Some(index) = start {
            if let Some(current) =
                instruction(&entity.nbt, index).filter(|item| item.mode != Mode::End)
            {
                active = index;
                step = index + 1;
                duration = current.duration(rpm, 0.0);
                let first_tick = !previously_powered && powered;
                timer = i32::from(first_tick && duration >= 0);
                progress = if timer > 0 {
                    current.progress(rpm)
                } else {
                    0.0
                };
            } else {
                active = -1;
                duration = -1;
                progress = 0.0;
                timer = 0;
                if !powered {
                    step = 0;
                }
            }
        }

        // A timed Java block-state change invalidates the input until the network reattaches.
        let reported_rpm = if elapsed_transition && step != block_step {
            0.0
        } else {
            rpm
        };
        game.native_with_mod_block_entity(pos, |entity| {
            entity.nbt.insert("InputSide".into(), Tag::Int(input_side));
            entity
                .nbt
                .insert("InstructionIndex".into(), Tag::Int(active));
            entity
                .nbt
                .insert("InstructionDuration".into(), Tag::Int(duration));
            entity.nbt.insert("Timer".into(), Tag::Int(timer));
            entity
                .nbt
                .insert("PrevPowered".into(), Tag::Byte(i8::from(powered)));
            set_float(&mut entity.nbt, "InstructionProgress", progress);
            set_float(&mut entity.nbt, "Speed", reported_rpm);
            entity.data.resize(1, 0);
            entity.data[0] = rpm.to_bits() as i32;
        });
        if step != block_step {
            game.native_set_block_property(pos, "state", &step.to_string());
        }
        if step != block_step
            || active >= 0
            || previous_reported_rpm != reported_rpm
            || previous_input_side != input_side
        {
            game.native_block_entity_sync(pos);
        }
    }
}
