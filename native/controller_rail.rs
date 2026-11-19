use std::cell::RefCell;
use std::collections::{BTreeMap, BTreeSet};

use horizon_core::position::BlockPos;
use horizon_world::fluid::{FluidKind, FluidState};
use horizon_world::level::{PlacementContext, flags};
use horizon_world::registry::BlockStateId;

use super::create_machines::offset;
use super::{Game, GameLevel};

pub(super) const RAIL: &str = "create:controller_rail";

thread_local! {
    static UPDATES: RefCell<Vec<(usize, [i32; 3], bool)>> = const { RefCell::new(Vec::new()) };
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
    fluid: FluidState,
) -> Option<Option<BlockStateId>> {
    if level.native_state_block(state) != Some(RAIL) {
        return None;
    }
    let direction = ((f64::from(context.yaw) / 90.0 + 0.5).floor() as i32).rem_euclid(4);
    let shape = if direction % 2 == 0 {
        "north_south"
    } else {
        "east_west"
    };
    let backwards = matches!(direction, 0 | 3);
    Some((|| {
        let state = level.native_state_with_property(state, "shape", shape)?;
        let state = level.native_state_with_property(state, "backwards", boolean(backwards))?;
        level.native_state_with_property(
            state,
            "waterlogged",
            boolean(fluid.kind() == FluidKind::Water),
        )
    })())
}

fn boolean(value: bool) -> &'static str {
    if value { "true" } else { "false" }
}

fn x_axis(shape: &str) -> bool {
    matches!(shape, "east_west" | "ascending_east" | "ascending_west")
}

pub(super) fn observe(level: &GameLevel<'_>, pos: BlockPos, state: BlockStateId) {
    if level.native_state_block(state) == Some(RAIL) {
        enqueue(level, pos, false);
    }
}

pub(super) fn placed(level: &GameLevel<'_>, pos: BlockPos, old: BlockStateId, new: BlockStateId) {
    let Some(now) = level.registry.state(new).filter(|state| state.name == RAIL) else {
        return;
    };
    let Some(prior) = level.registry.state(old).filter(|state| state.name == RAIL) else {
        enqueue(level, pos, false);
        return;
    };
    let prior = prior
        .properties
        .get("shape")
        .map(String::as_str)
        .unwrap_or_default();
    let now = now
        .properties
        .get("shape")
        .map(String::as_str)
        .unwrap_or_default();
    if x_axis(prior) != x_axis(now) {
        enqueue(level, pos, true);
    }
}

fn enqueue(level: &GameLevel<'_>, pos: BlockPos, axis_changed: bool) {
    let world = std::ptr::from_ref(&*level.world) as usize;
    UPDATES.with_borrow_mut(|updates| updates.push((world, [pos.x, pos.y, pos.z], axis_changed)));
}

#[derive(Clone, Copy)]
struct Rail {
    along_x: bool,
    ascending: bool,
    backwards: bool,
}

impl Rail {
    fn at(game: &Game<'_>, pos: [i32; 3]) -> Option<Self> {
        if game.native_block(pos) != RAIL {
            return None;
        }
        let shape = game.native_block_property(pos, "shape")?;
        Some(Self {
            along_x: x_axis(&shape),
            ascending: shape.starts_with("ascending_"),
            backwards: game.native_block_property(pos, "backwards").as_deref() == Some("true"),
        })
    }

    fn direction(self) -> [i32; 3] {
        direction(self.along_x, self.backwards)
    }
}

pub(super) fn direction(along_x: bool, backwards: bool) -> [i32; 3] {
    let sign = if backwards { 1 } else { -1 };
    if along_x { [sign, 0, 0] } else { [0, 0, sign] }
}

fn next(game: &Game<'_>, pos: [i32; 3], reverse: bool) -> Option<[i32; 3]> {
    let rail = Rail::at(game, pos)?;
    let direction = rail.direction();
    let base = offset(
        pos,
        if reverse {
            direction.map(|axis| -axis)
        } else {
            direction
        },
    );
    [0, -1, 1].into_iter().find_map(|height| {
        if height == 1 && !rail.ascending {
            return None;
        }
        let candidate = offset(base, [0, height, 0]);
        let peer = Rail::at(game, candidate)?;
        (peer.direction() == direction).then_some(candidate)
    })
}

fn align(game: &mut Game<'_>, pos: [i32; 3]) {
    let Some(rail) = Rail::at(game, pos) else {
        return;
    };
    let direction = if rail.along_x { [-1, 0, 0] } else { [0, 0, -1] };
    let mut backwards = rail.backwards;
    for direction in [direction, direction.map(|axis| -axis)] {
        let adjacent = offset(pos, direction);
        for height in [0, -1, 1] {
            if let Some(peer) = Rail::at(game, offset(adjacent, [0, height, 0]))
                && peer.along_x == rail.along_x
            {
                backwards = peer.backwards;
            }
        }
    }
    if backwards != rail.backwards {
        game.native_set_block_property_with(
            pos,
            "backwards",
            boolean(backwards),
            flags::UPDATE_CLIENTS,
        );
    }
}

fn signal(game: &mut Game<'_>, pos: [i32; 3]) -> i32 {
    game.native_neighbor_signal(game.native_dimension(), pos)
}

fn find_power(game: &mut Game<'_>, pos: [i32; 3], reverse: bool) -> (i32, i32) {
    let mut at = pos;
    let mut distance = 0;
    for _ in 0..15 {
        let Some(peer) = next(game, at, reverse) else {
            break;
        };
        at = peer;
        distance += 1;
        let power = signal(game, at);
        if power > 0 {
            return (distance, power);
        }
    }
    (distance, 0)
}

fn power(game: &mut Game<'_>, pos: [i32; 3]) -> i32 {
    let direct = signal(game, pos);
    if direct > 0 {
        return direct;
    }
    let (forward_distance, forward) = find_power(game, pos, false);
    let (reverse_distance, reverse) = find_power(game, pos, true);
    if forward_distance > 8 && reverse_distance > 8 {
        0
    } else if reverse == 0 && forward_distance <= 8 {
        forward
    } else if forward == 0 && reverse_distance <= 8 {
        reverse
    } else if forward > 0 && reverse > 0 {
        let distance = forward_distance + reverse_distance;
        (reverse * forward_distance + forward * reverse_distance + distance - 1) / distance
    } else {
        0
    }
}

pub(super) fn flush(game: &mut Game<'_>) {
    let world = std::ptr::from_ref(&game.world) as usize;
    let dirty = UPDATES.with_borrow_mut(|updates| {
        let mut dirty = BTreeMap::new();
        updates.retain(|&(owner, pos, align)| {
            if owner != world {
                return true;
            }
            *dirty.entry(pos).or_insert(false) |= align;
            false
        });
        dirty
    });
    for (&pos, &needs_alignment) in &dirty {
        if needs_alignment {
            align(game, pos);
        }
    }
    let mut affected = BTreeSet::new();
    for pos in dirty
        .into_keys()
        .filter(|&pos| Rail::at(game, pos).is_some())
    {
        affected.insert(pos);
        for reverse in [false, true] {
            let mut at = pos;
            for _ in 0..15 {
                let Some(peer) = next(game, at, reverse) else {
                    break;
                };
                affected.insert(peer);
                at = peer;
            }
        }
    }
    for pos in affected {
        let value = power(game, pos).to_string();
        if game.native_set_block_property_with(pos, "power", &value, flags::UPDATE_CLIENTS) {
            game.native_update_output_neighbors(game.native_dimension(), pos);
        }
    }
}

pub(super) fn output(level: &GameLevel<'_>, state: BlockStateId) -> Option<i32> {
    let state = level
        .registry
        .state(state)
        .filter(|state| state.name == RAIL)?;
    state.properties.get("power")?.parse().ok()
}

pub(super) fn move_cart(
    game: &Game<'_>,
    cart: &mut super::minecarts::Minecart,
    pos: [i32; 3],
    max_speed: f64,
) {
    use super::minecarts::CartKind;
    use horizon_core::geometry::Vec3;
    let Some(rail) = Rail::at(game, pos) else {
        return;
    };
    let direction = rail.direction();
    let acceleration = Vec3::new(f64::from(direction[0]), 0.0, f64::from(direction[2]));
    let power = game
        .native_block_property(pos, "power")
        .and_then(|value| value.parse::<u8>().ok())
        .unwrap_or(0);
    let speed = f64::from(max_speed as f32 * f32::from(power) / 15.0);
    if cart.kind == CartKind::Furnace {
        cart.push = acceleration;
    }
    if (cart.velocity.dot(acceleration) >= 0.0 || cart.velocity.length_squared() < 0.0001)
        && speed > 0.0
    {
        cart.velocity = acceleration.scale(speed);
    } else {
        let x = f64::from(pos[0]) + 0.5 - cart.position.x;
        let z = f64::from(pos[2]) + 0.5 - cart.position.z;
        cart.velocity = Vec3::new(x / 16.0, 0.0, z / 16.0);
        if cart.kind == CartKind::Furnace {
            cart.push = Vec3::ZERO;
        }
    }
}

fn rigid(game: &Game<'_>, pos: [i32; 3]) -> bool {
    use horizon_core::geometry::Direction;
    let state = game.world.block(pos[0], pos[1], pos[2]);
    game.res
        .behaviours()
        .is_face_sturdy_rigid(state, Direction::Up)
}

fn stable(game: &Game<'_>, pos: [i32; 3], shape: &str) -> bool {
    let rise = match shape {
        "ascending_west" => [-1, 0, 0],
        "ascending_east" => [1, 0, 0],
        "ascending_north" => [0, 0, -1],
        "ascending_south" => [0, 0, 1],
        _ => return rigid(game, offset(pos, [0, -1, 0])),
    };
    rigid(game, offset(pos, [0, -1, 0])) && rigid(game, offset(pos, rise))
}

pub(super) fn wrench(game: &mut Game<'_>, pos: [i32; 3]) {
    let Some(shape) = game.native_block_property(pos, "shape") else {
        return;
    };
    let rotations = match shape.as_str() {
        "north_south" => ["east_west", "north_south", "east_west"],
        "east_west" => ["north_south", "east_west", "north_south"],
        "ascending_north" => ["ascending_east", "ascending_south", "ascending_west"],
        "ascending_east" => ["ascending_south", "ascending_west", "ascending_north"],
        "ascending_south" => ["ascending_west", "ascending_north", "ascending_east"],
        "ascending_west" => ["ascending_north", "ascending_east", "ascending_south"],
        _ => return,
    };
    let backwards = game.native_block_property(pos, "backwards").as_deref() == Some("true");
    let rotation = rotations
        .into_iter()
        .enumerate()
        .find(|(_, candidate)| stable(game, pos, candidate));
    let (shape, backwards) = if let Some((turn, shape)) = rotation {
        let flip = turn == 1 || (!x_axis(shape) == (turn == 2));
        (shape, backwards ^ flip)
    } else if stable(game, pos, &shape) {
        (shape.as_str(), !backwards)
    } else {
        return;
    };
    let old = game.world.block(pos[0], pos[1], pos[2]);
    if let Some(state) = game.with_level(|_, level, _| {
        let rotated = level.native_state_with_property(old, "shape", shape)?;
        level.native_state_with_property(rotated, "backwards", boolean(backwards))
    }) {
        game.native_set_block(game.native_dimension(), pos, state, flags::UPDATE_ALL);
        game.native_update_signal_neighbors(game.native_dimension(), offset(pos, [0, -1, 0]));
        if shape.starts_with("ascending_") {
            game.native_update_signal_neighbors(game.native_dimension(), offset(pos, [0, 1, 0]));
        }
    }
}
