use horizon_core::geometry::Direction;
use horizon_core::position::BlockPos;
use horizon_world::fluid::{FluidKind, FluidState};
use horizon_world::level::PlacementContext;
use horizon_world::registry::BlockStateId;

use super::GameLevel;
use super::create_machines::{COG, LARGE_COG};
use super::create_speed_controller::{CONTROLLER, cross_axis};

pub(super) const CASED_COG: &str = "create:brass_encased_cogwheel";
pub(super) const CASED_ANDESITE_COG: &str = "create:andesite_encased_cogwheel";
pub(super) const CASED_LARGE_COG: &str = "create:brass_encased_large_cogwheel";
pub(super) const CASED_ANDESITE_LARGE_COG: &str = "create:andesite_encased_large_cogwheel";
pub(super) const CASED_COG_ENTITY: &str = "create:encased_cogwheel";
pub(super) const CASED_LARGE_COG_ENTITY: &str = "create:encased_large_cogwheel";

pub(super) fn encased_size(name: &str) -> Option<bool> {
    match name {
        CASED_COG | CASED_ANDESITE_COG => Some(false),
        CASED_LARGE_COG | CASED_ANDESITE_LARGE_COG => Some(true),
        _ => None,
    }
}

pub(super) fn direction_axis(direction: Direction) -> &'static str {
    match direction {
        Direction::East | Direction::West => "x",
        Direction::Up | Direction::Down => "y",
        Direction::North | Direction::South => "z",
    }
}

fn small_cog(name: &str) -> bool {
    name == COG || encased_size(name) == Some(false)
}

pub(super) fn large_cog(name: &str) -> bool {
    name == LARGE_COG || encased_size(name) == Some(true)
}

pub(super) fn valid_position(
    level: &GameLevel<'_>,
    pos: BlockPos,
    axis: &str,
    large: bool,
) -> bool {
    Direction::ALL.into_iter().all(|direction| {
        let [dx, dy, dz] = direction.normal();
        let adjacent_axis = direction_axis(direction);
        if adjacent_axis == axis {
            return true;
        }
        let id = level.world.block(pos.x + dx, pos.y + dy, pos.z + dz);
        let Some(neighbor) = level.registry.state(id) else {
            return true;
        };
        neighbor
            .properties
            .get("axis")
            .is_some_and(|value| value == adjacent_axis)
            || !(large_cog(&neighbor.name) || large && small_cog(&neighbor.name))
    })
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
    fluid: FluidState,
) -> Option<Option<BlockStateId>> {
    let large = match level.native_state_block(state)? {
        COG => false,
        LARGE_COG => true,
        _ => return None,
    };
    let axis = placement_axis(level, context, large);
    if !valid_position(level, context.pos, axis, large) {
        return Some(None);
    }
    let wet = if fluid.kind() == FluidKind::Water {
        "true"
    } else {
        "false"
    };
    Some(
        level
            .native_state_with_property(state, "axis", axis)
            .and_then(|state| level.native_state_with_property(state, "waterlogged", wet)),
    )
}

fn placement_axis(level: &GameLevel<'_>, context: &PlacementContext, large: bool) -> &'static str {
    if context.sneaking {
        return direction_axis(context.face);
    }
    let pos = context.pos;
    let below = level.world.block(pos.x, pos.y - 1, pos.z);
    if large
        && let Some(block) = level.registry.state(below)
        && block.name == CONTROLLER
        && let Some(axis) = block.properties.get("axis")
    {
        return cross_axis(axis);
    }
    let [dx, dy, dz] = context.face.opposite().normal();
    let attached = level.world.block(pos.x + dx, pos.y + dy, pos.z + dz);
    if let Some(block) = level.registry.state(attached)
        && small_cog(&block.name)
        && let Some(axis) = block.properties.get("axis")
    {
        return match axis.as_str() {
            "x" => "x",
            "z" => "z",
            _ => "y",
        };
    }
    super::create_hand_crank::preferred_direction(level, pos)
        .map_or_else(|| direction_axis(context.face), direction_axis)
}

pub(super) fn redirect_placement(
    game: &mut super::Game<'_>,
    context: &mut horizon_world::level::PlaceContext,
) {
    if context.sneaking || !game.may_build() {
        return;
    }
    let origin = context.clicked_pos;
    let existing = game.native_block([origin.x, origin.y, origin.z]);
    let large = context.item == LARGE_COG;
    let large_base = large_cog(&existing);
    if !matches!(context.item.as_str(), COG | LARGE_COG) || !(large_base || small_cog(&existing)) {
        return;
    }
    let Some(axis) = game.native_block_property([origin.x, origin.y, origin.z], "axis") else {
        return;
    };
    let Some(axis_index) = super::create_machines::axis_index(&axis) else {
        return;
    };
    let hit = context.hit.components();
    if hit.into_iter().enumerate().all(|(index, point)| {
        index == axis_index || (0.3115..0.6885).contains(&(point - point.floor()))
    }) {
        return;
    }

    let origin_coords = [
        f64::from(origin.x),
        f64::from(origin.y),
        f64::from(origin.z),
    ];
    let score = |direction: Direction| {
        direction
            .normal()
            .into_iter()
            .enumerate()
            .map(|(index, component)| {
                (hit[index] - origin_coords[index] - 0.5) * f64::from(component)
            })
            .sum::<f64>()
    };
    let mut directions = Direction::ALL;
    directions.sort_by(|a, b| score(*b).total_cmp(&score(*a)));
    let shift = |pos: BlockPos, direction: Direction| {
        let [dx, dy, dz] = direction.normal();
        pos.offset(dx, dy, dz)
    };
    let along = directions
        .iter()
        .copied()
        .find(|&direction| direction_axis(direction) == axis)
        .unwrap();
    let mut across = directions
        .into_iter()
        .filter(|&direction| direction_axis(direction) != axis);
    let candidates: Vec<_> = if large != large_base {
        let closest = across.next().unwrap();
        let closest_axis = direction_axis(closest);
        across
            .filter(|&direction| direction_axis(direction) != closest_axis)
            .map(|direction| (shift(shift(origin, closest), direction), axis.as_str()))
            .collect()
    } else if large {
        across
            .map(|direction| {
                (
                    shift(shift(origin, along), direction),
                    direction_axis(direction),
                )
            })
            .collect()
    } else {
        across
            .map(|direction| (shift(origin, direction), axis.as_str()))
            .collect()
    };

    let Some(default) = game.native_default_state(&context.item) else {
        return;
    };
    let assisted = game.with_level(|b, level, ticks| {
        candidates.into_iter().find_map(|(pos, axis)| {
            if !valid_position(level, pos, axis, large_base) {
                return None;
            }
            let checked = horizon_world::level::PlaceContext {
                clicked_pos: pos,
                ..context.clone()
            };
            if !b.directional_can_place(level, ticks, &checked) {
                return None;
            }
            let fluid = b.fluid(level.world.block(pos.x, pos.y, pos.z));
            let wet = if fluid.kind() == FluidKind::Water {
                "true"
            } else {
                "false"
            };
            let state = level.native_state_with_property(default, "axis", axis)?;
            let state = level.native_state_with_property(state, "waterlogged", wet)?;
            Some((pos, state))
        })
    });
    if let Some((pos, state)) = assisted {
        context.clicked_pos = pos;
        context.state_override = Some(state);
    }
}
