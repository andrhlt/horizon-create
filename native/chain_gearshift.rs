use horizon_core::geometry::{Direction, Vec3};
use horizon_core::position::BlockPos;
use horizon_world::nbt::Tag;
use horizon_world::registry::BlockStateId;

use crate::containers::ModBlockEntity;

use super::create_machines::{axis_index, chain_gearshift_overspeed, int, mod_entity};
use super::{Game, GameLevel};

pub(super) const ADJUSTABLE: &str = "create:adjustable_chain_gearshift";
const DRIVE: &str = "create:encased_chain_drive";
const AXES: [&str; 3] = ["x", "y", "z"];
const PENDING: usize = 3;
const TIMESTAMP_LO: usize = 4;
const TIMESTAMP_HI: usize = 5;
const LAZY_TICKS: usize = 6;

pub(super) fn modifier(entity: &ModBlockEntity) -> f32 {
    match int(&entity.nbt, "Signal").unwrap_or(0).clamp(0, 15) {
        0 => 1.0,
        signal => 1.0 + (signal + 1) as f32 / 16.0,
    }
}

pub(super) fn observe_signal(game: &mut Game<'_>, pos: [i32; 3]) {
    let power = game.native_neighbor_signal(game.native_dimension(), pos);
    let was_powered = game.native_block_property(pos, "powered").as_deref() == Some("true");
    let powered = power > 0;
    if powered != was_powered {
        game.native_set_block_property_with(
            pos,
            "powered",
            if powered { "true" } else { "false" },
            18,
        );
    }

    let tick = game.world.game_time.saturating_add(1);
    game.native_with_mod_block_entity(pos, |entity| {
        entity.data.resize(LAZY_TICKS + 1, 0);
        if entity.data[PENDING] == 0 && int(&entity.nbt, "Signal").unwrap_or(0) != power {
            entity.data[PENDING] = 1;
            entity.data[TIMESTAMP_LO] = tick as i32;
            entity.data[TIMESTAMP_HI] = (tick >> 32) as i32;
        }
    });
}

fn pending_due(entity: &ModBlockEntity, time: i64) -> bool {
    if entity.data.get(PENDING).copied() != Some(1) {
        return false;
    }
    let lo = entity.data[TIMESTAMP_LO] as u32;
    let hi = entity.data[TIMESTAMP_HI];
    let tick = (i64::from(hi) << 32) | i64::from(lo);
    time >= tick
}

pub(super) fn prepare(game: &mut Game<'_>) {
    let ticking = game.block_ticking_area();
    let now = game.world.game_time;
    let positions: Vec<_> = game
        .world
        .block_entity_tickers()
        .iter()
        .filter_map(|entry| {
            let (x, y, z) = entry.0;
            let pos = [x, y, z];
            let entity = mod_entity(game, pos).filter(|entity| entity.id == ADJUSTABLE)?;
            if !ticking(x, z) {
                return None;
            }
            let initial = int(&entity.nbt, "Signal").is_none();
            let age = entity.data.get(LAZY_TICKS).copied().unwrap_or(0);
            let lazy = age == 0 || age == 40;
            Some((pos, age % 41 + 1, pending_due(entity, now), lazy, initial))
        })
        .collect();
    for (pos, age, pending, lazy, initial) in positions {
        let signal =
            (pending || lazy).then(|| game.native_neighbor_signal(game.native_dimension(), pos));
        let mut changed = false;
        game.native_with_mod_block_entity(pos, |entity| {
            entity.data.resize(LAZY_TICKS + 1, 0);
            entity.data[LAZY_TICKS] = age;
            if let Some(signal) = signal {
                changed = int(&entity.nbt, "Signal").unwrap_or(0) != signal;
                entity.nbt.insert("Signal".into(), Tag::Int(signal));
                if pending {
                    entity.data[PENDING] = 0;
                }
            }
        });
        if changed && chain_gearshift_overspeed(game, pos) {
            game.native_machine_destroy_block(pos, None, false);
            continue;
        }
        if initial && let Some(signal) = signal {
            let powered = if signal > 0 { "true" } else { "false" };
            if game.native_block_property(pos, "powered").as_deref() != Some(powered) {
                game.native_set_block_property_with(pos, "powered", powered, 18);
            }
        }
    }
}

#[derive(Clone, Copy)]
struct Chain {
    axis: usize,
    first: bool,
    part: &'static str,
}

impl Chain {
    fn from_state(level: &GameLevel<'_>, state: BlockStateId) -> Option<Self> {
        let state = level.registry.state(state)?;
        if !matches!(state.name.as_str(), DRIVE | ADJUSTABLE) {
            return None;
        }
        let axis = axis_index(state.properties.get("axis")?)?;
        Some(Self {
            axis,
            first: state.properties.get("axis_along_first")? == "true",
            part: match state.properties.get("part")?.as_str() {
                "start" => "start",
                "middle" => "middle",
                "end" => "end",
                _ => "none",
            },
        })
    }

    fn connection_axis(self) -> usize {
        match (self.axis, self.first) {
            (0, true) | (2, false) => 1,
            (0 | 1, false) => 2,
            _ => 0,
        }
    }

    fn update(self, other: Option<Self>, direction: Direction) -> Self {
        let axis = direction_axis(direction);
        if axis == self.axis {
            return self;
        }
        let positive = direction.normal()[axis] > 0;
        let face_part = if positive { "start" } else { "end" };
        let connected_to_axis = self.connection_axis() == axis;
        let Some(other) = other else {
            if !connected_to_axis || self.part == "none" {
                return self;
            }
            let part = match self.part {
                "middle" => {
                    if positive {
                        "end"
                    } else {
                        "start"
                    }
                }
                part if part == face_part => "none",
                part => part,
            };
            return Self { part, ..self };
        };
        if other.axis == axis || (other.part != "none" && other.connection_axis() != axis) {
            return self;
        }
        if self.part == "none" {
            let first = if self.axis == 0 { axis == 1 } else { axis == 0 };
            return Self {
                first,
                part: face_part,
                ..self
            };
        }
        if connected_to_axis && self.part != face_part {
            return Self {
                part: "middle",
                ..self
            };
        }
        self
    }

    fn state(self, level: &GameLevel<'_>, state: BlockStateId) -> Option<BlockStateId> {
        let first = if self.first { "true" } else { "false" };
        let state = level.native_state_with_property(state, "axis", AXES[self.axis])?;
        let state = level.native_state_with_property(state, "axis_along_first", first)?;
        level.native_state_with_property(state, "part", self.part)
    }
}

fn direction_axis(direction: Direction) -> usize {
    match direction {
        Direction::West | Direction::East => 0,
        Direction::Up | Direction::Down => 1,
        Direction::North | Direction::South => 2,
    }
}

pub(super) fn update_shape(
    level: &GameLevel<'_>,
    state: BlockStateId,
    direction: Direction,
    neighbour: BlockStateId,
) -> Option<BlockStateId> {
    let current = Chain::from_state(level, state)?;
    current
        .update(Chain::from_state(level, neighbour), direction)
        .state(level, state)
        .filter(|updated| *updated != state)
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &horizon_world::level::PlacementContext,
) -> Option<BlockStateId> {
    let mut chain = Chain::from_state(level, state)?;
    let (sin_yaw, cos_yaw) = f64::from(context.yaw).to_radians().sin_cos();
    let (sin_pitch, cos_pitch) = f64::from(context.pitch).to_radians().sin_cos();
    let sight = Direction::approximate_nearest(Vec3::new(
        -sin_yaw * cos_pitch,
        -sin_pitch,
        cos_yaw * cos_pitch,
    ));
    let preferred = if context.sneaking {
        None
    } else {
        super::create_hand_crank::preferred_direction(level, context.pos)
    };
    chain.axis = direction_axis(preferred.unwrap_or(sight));
    for direction in Direction::ALL {
        let [x, y, z] = direction.normal();
        let BlockPos { x, y, z } = context.pos.offset(x, y, z);
        let neighbour = level.world.block(x, y, z);
        chain = chain.update(Chain::from_state(level, neighbour), direction);
    }
    chain.state(level, state)
}
