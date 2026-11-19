use std::collections::{BTreeSet, VecDeque};

use horizon_core::geometry::{Direction, trig};
use horizon_world::level::{LevelAccess, PlacementContext, flags};
use horizon_world::registry::BlockStateId;

use super::create_bearing::rotate;
use super::create_machines::offset;
use super::{Game, GameLevel};

const CHASSIS: &str = "create:linear_chassis";
const SECONDARY_CHASSIS: &str = "create:secondary_linear_chassis";
pub(super) const RADIAL_CHASSIS: &str = "create:radial_chassis";

pub(super) fn linear(block: &str) -> bool {
    matches!(block, CHASSIS | SECONDARY_CHASSIS)
}

pub(super) fn is_chassis(block: &str) -> bool {
    linear(block) || block == RADIAL_CHASSIS
}

fn axis(side: Direction) -> &'static str {
    match side {
        Direction::West | Direction::East => "x",
        Direction::Down | Direction::Up => "y",
        Direction::North | Direction::South => "z",
    }
}

fn positive_axis(name: &str) -> Option<Direction> {
    match name {
        "x" => Some(Direction::East),
        "y" => Some(Direction::Up),
        "z" => Some(Direction::South),
        _ => None,
    }
}

fn sticky(side: Direction) -> &'static str {
    match side {
        Direction::East | Direction::Up | Direction::South => "sticky_top",
        _ => "sticky_bottom",
    }
}

fn glueable(radial: bool, along: &str, face: Direction) -> Option<&'static str> {
    if !radial {
        return (axis(face) == along).then(|| sticky(face));
    }
    match (along, face) {
        ("x", Direction::North) | ("y" | "z", Direction::West) => Some("sticky_west"),
        ("x", Direction::South) | ("y" | "z", Direction::East) => Some("sticky_east"),
        ("x" | "z", Direction::Up) | ("y", Direction::North) => Some("sticky_north"),
        ("x" | "z", Direction::Down) | ("y", Direction::South) => Some("sticky_south"),
        _ => None,
    }
}

pub(super) fn placement(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
) -> Option<BlockStateId> {
    let kind = level.native_state_block(state)?;
    if !linear(kind) && kind != RADIAL_CHASSIS {
        return None;
    }
    let place_axis = if context.sneaking || kind == RADIAL_CHASSIS {
        axis(context.face)
    } else {
        let [x, y, z] = context.face.opposite().normal();
        let support = level
            .registry
            .state(level.block_state(context.pos.offset(x, y, z)));
        if let Some(existing) = support.filter(|support| linear(&support.name)) {
            existing.properties.get("axis")?.as_str()
        } else {
            // Mirror the first direction in Direction.orderedByNearest.
            let pitch = f64::from(context.pitch * (std::f32::consts::PI / 180.0));
            let yaw = f64::from(-context.yaw * (std::f32::consts::PI / 180.0));
            let (sin_yaw, cos_yaw) = (trig::sin(yaw).abs(), trig::cos(yaw).abs());
            let horizontal = if sin_yaw > cos_yaw { "x" } else { "z" };
            let forward = sin_yaw.max(cos_yaw) * trig::cos(pitch);
            if trig::sin(pitch).abs() > forward {
                "y"
            } else {
                horizontal
            }
        }
    };
    level.native_state_with_property(state, "axis", place_axis)
}

pub(super) fn update_shape(
    level: &GameLevel<'_>,
    state: BlockStateId,
    face: Direction,
    neighbour: BlockStateId,
) -> Option<BlockStateId> {
    let kind = level
        .native_state_block(state)
        .filter(|block| linear(block))?;
    if level.native_state_block(neighbour) != Some(kind) {
        return None;
    }
    let along = axis(face);
    let axis_matches = |id| {
        level
            .registry
            .state(id)
            .and_then(|block| block.properties.get("axis"))
            .is_some_and(|value| value == along)
    };
    let property = sticky(face);
    if axis_matches(state)
        && axis_matches(neighbour)
        && level
            .registry
            .state(state)?
            .properties
            .get(property)?
            .as_str()
            == "true"
    {
        level.native_state_with_property(state, property, "false")
    } else {
        None
    }
}

pub(super) fn click(game: &mut Game<'_>, pos: [i32; 3], normal: [i32; 3]) -> bool {
    let kind = game.native_block(pos);
    let radial = kind == RADIAL_CHASSIS;
    if !(linear(&kind) || radial) || !game.may_build() {
        return false;
    }
    let Some(face) = Direction::ALL
        .into_iter()
        .find(|side| side.normal() == normal)
    else {
        return false;
    };
    let Some(along) = game.native_block_property(pos, "axis") else {
        return false;
    };
    let Some(clicked_property) = glueable(radial, &along, face) else {
        return false;
    };
    let adhesive = game.held().is_some_and(|stack| {
        matches!(
            stack.item.as_ref(),
            "minecraft:slime_ball" | super::create_glue::ITEM
        ) || game
            .items()
            .item_tags
            .get("c:slimeballs")
            .is_some_and(|tag| tag.contains(stack.item.as_ref()))
    });
    if !adhesive && (!game.native_sneaking() || game.held().is_some()) {
        return false;
    }
    let applied = |game: &Game<'_>, property| {
        game.native_block_property(pos, property).as_deref() == Some("true")
    };
    let currently_applied = applied(game, clicked_property);
    let fill = adhesive && currently_applied;
    if !fill && currently_applied == adhesive {
        return false;
    }
    let may_coat = |game: &Game<'_>, change: Direction| {
        let other = offset(pos, change.normal());
        radial
            || game.native_block(other) != kind
            || game.native_block_property(other, "axis").as_deref() != Some(along.as_str())
    };
    if !fill && !may_coat(game, face) {
        return false;
    }
    let value = if adhesive { "true" } else { "false" };
    let mut changes = Vec::new();
    for side in Direction::ALL {
        if (!fill && side != face) || !may_coat(game, side) {
            continue;
        }
        let Some(property) = glueable(radial, &along, side) else {
            continue;
        };
        if adhesive != applied(game, property) {
            changes.push(property);
        }
    }
    if !changes.is_empty() {
        let state = game.world.block(pos[0], pos[1], pos[2]);
        let replacement = game.with_level(|_, level, _| {
            changes.iter().try_fold(state, |block, property| {
                level.native_state_with_property(block, property, value)
            })
        });
        if let Some(state) = replacement
            && game.native_set_block(game.native_dimension(), pos, state, flags::UPDATE_ALL)
        {
            let sound_pos = pos.map(|n| f64::from(n) + 0.5);
            for _ in changes {
                game.native_play_sound_in_place("create:slime_added", sound_pos, 4, 0.5, 1.0);
            }
        }
    }
    game.swing_arm();
    true
}

pub(super) fn collect(
    game: &Game<'_>,
    world: [i32; 3],
    controller: [i32; 3],
    next: &mut VecDeque<[i32; 3]>,
) {
    let kind = game.native_block(world);
    let radial = kind == RADIAL_CHASSIS;
    if !linear(&kind) && !radial {
        return;
    }
    let Some(along) = game.native_block_property(world, "axis") else {
        return;
    };
    next.extend(joined(game, world, &kind, &along, radial));
    let range = super::create_chassis_range::value(game, world);
    included(game, world, controller, &along, radial, range, next);
}

pub(super) fn preview(game: &Game<'_>, origin: [i32; 3], range: i32) -> VecDeque<[i32; 3]> {
    let mut cells = VecDeque::new();
    let kind = game.native_block(origin);
    if is_chassis(&kind)
        && let Some(along) = game.native_block_property(origin, "axis")
    {
        included(
            game,
            origin,
            origin,
            &along,
            kind == RADIAL_CHASSIS,
            range,
            &mut cells,
        );
    }
    cells
}

fn included(
    game: &Game<'_>,
    world: [i32; 3],
    controller: [i32; 3],
    along: &str,
    radial: bool,
    range: i32,
    next: &mut VecDeque<[i32; 3]>,
) {
    let Some(positive) = positive_axis(along) else {
        return;
    };
    if radial {
        collect_radial(game, world, controller, along, range, next);
        return;
    }
    for side in [positive, positive.opposite()] {
        if game.native_block_property(world, sticky(side)).as_deref() != Some("true") {
            continue;
        }
        for distance in 1..=range {
            let other = offset(world, side.normal().map(|coord| coord * distance));
            let Some(id) = supported_block(game, other, controller) else {
                break;
            };
            next.push_back(other);
            if !supports(game, id, side) {
                break;
            }
        }
    }
}

fn joined(game: &Game<'_>, at: [i32; 3], kind: &str, along: &str, radial: bool) -> Vec<[i32; 3]> {
    let mut joined = Vec::new();
    for side in Direction::ALL {
        if radial && axis(side) != along {
            continue;
        }
        let other = offset(at, side.normal());
        if game.native_block(other) == kind
            && game.native_block_property(other, "axis").as_deref() == Some(along)
        {
            joined.push(other);
        }
    }
    joined
}

pub(super) fn group(game: &Game<'_>, start: [i32; 3]) -> Vec<[i32; 3]> {
    let kind = game.native_block(start);
    let radial = kind == RADIAL_CHASSIS;
    if !(linear(&kind) || radial) {
        return Vec::new();
    }
    let Some(along) = game.native_block_property(start, "axis") else {
        return Vec::new();
    };
    let mut pending = VecDeque::from([start]);
    let mut seen = BTreeSet::new();
    let mut group = Vec::new();
    while let Some(pos) = pending.pop_front() {
        if seen.insert(pos) {
            group.push(pos);
            pending.extend(joined(game, pos, &kind, &along, radial));
        }
    }
    group
}

fn supported_block(game: &Game<'_>, other: [i32; 3], controller: [i32; 3]) -> Option<BlockStateId> {
    let id = game.world.block(other[0], other[1], other[2]);
    let block = game.pack.assets.registry.state(id)?;
    if other == controller
        || game.res.behaviours().is_replaceable(id)
        || game.native_block_collision(other).is_empty()
        || matches!(
            block.name.as_str(),
            "minecraft:bedrock" | "minecraft:barrier"
        )
    {
        return None;
    }
    Some(id)
}

fn supports(game: &Game<'_>, id: BlockStateId, side: Direction) -> bool {
    !game.pack.assets.registry.state(id).is_some_and(|block| {
        matches!(
            block.name.as_str(),
            "create:mechanical_drill"
                | "create:mechanical_saw"
                | "create:mechanical_bearing"
                | "create:portable_storage_interface"
        ) && super::create_fan::facing(game, id) == Some(side)
    })
}

fn collect_radial(
    game: &Game<'_>,
    origin: [i32; 3],
    controller: [i32; 3],
    along: &str,
    range: i32,
    next: &mut VecDeque<[i32; 3]>,
) {
    let mut pending = VecDeque::new();
    for side in Direction::ALL {
        if let Some(property) = glueable(true, along, side)
            && game.native_block_property(origin, property).as_deref() == Some("true")
        {
            pending.push_back(offset(origin, side.normal()));
        }
    }
    let mut seen = BTreeSet::from([origin]);
    while let Some(block) = pending.pop_front() {
        let distance_squared: i32 = block
            .into_iter()
            .zip(origin)
            .map(|(value, start)| (value - start).pow(2))
            .sum();
        // Java's strict distance is range + 0.5. Compare integer
        // coordinates using twice that radius to avoid a square root.
        if distance_squared * 4 >= (range * 2 + 1).pow(2) || !seen.insert(block) {
            continue;
        }
        let Some(id) = supported_block(game, block, controller) else {
            continue;
        };
        next.push_back(block);
        for side in Direction::ALL {
            if axis(side) != along && supports(game, id, side) {
                pending.push_back(offset(block, side.normal()));
            }
        }
    }
}

pub(super) fn rotated(
    game: &mut Game<'_>,
    state: BlockStateId,
    around: usize,
    angle: f64,
) -> Option<BlockStateId> {
    let data = game.pack.assets.registry.state(state)?;
    let radial = data.name == RADIAL_CHASSIS;
    if !linear(&data.name) && !radial {
        return None;
    }
    let along = data.properties.get("axis")?;
    let transformed = |side: Direction| {
        let normal = rotate(side.normal().map(f64::from), around, angle)
            .map(|coordinate| coordinate.round() as i32);
        Direction::ALL
            .into_iter()
            .find(|direction| direction.normal() == normal)
    };
    let rotated_axis = axis(transformed(positive_axis(along)?)?);
    let mut properties = Vec::with_capacity(if radial { 4 } else { 2 });
    for side in Direction::ALL {
        let Some(original_key) = glueable(radial, along, side) else {
            continue;
        };
        let rotated_key = glueable(radial, rotated_axis, transformed(side)?)?;
        let value = if data
            .properties
            .get(original_key)
            .is_some_and(|value| value == "true")
        {
            "true"
        } else {
            "false"
        };
        properties.push((rotated_key, value));
    }
    game.with_level(|_, level, _| {
        let mut rotated = level.native_state_with_property(state, "axis", rotated_axis)?;
        for (property, value) in properties {
            rotated = level.native_state_with_property(rotated, property, value)?;
        }
        Some(rotated)
    })
}
