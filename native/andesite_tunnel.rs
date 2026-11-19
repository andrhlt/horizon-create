use horizon_core::geometry::Direction;

use crate::items::ItemStack;

use super::Game;
use super::create_belt::segment;
use super::create_depot::{DEPOT, receive_stack};
use super::create_machines::offset;
use super::create_threshold_switch::delta;

pub(super) const TUNNEL: &str = "create:andesite_tunnel";

fn sides(direction: Direction) -> [Direction; 2] {
    if matches!(direction, Direction::East | Direction::West) {
        [Direction::South, Direction::North]
    } else {
        [Direction::West, Direction::East]
    }
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3]) {
    let under = offset(pos, [0, -1, 0]);
    let Some((direction, _)) = segment(game, under) else {
        return;
    };
    let [left, right] = sides(direction)
        .map(|direction| game.native_block(offset(under, delta(direction))) == DEPOT);
    let shape = match (left, right) {
        (true, true) => "cross",
        (true, false) => "t_left",
        (false, true) => "t_right",
        (false, false) => "straight",
    };
    let axis = if matches!(direction, Direction::East | Direction::West) {
        "x"
    } else {
        "z"
    };
    game.native_set_block_property_with(pos, "axis", axis, 2);
    game.native_set_block_property_with(pos, "shape", shape, 2);
}

/// Shed one item into each side output as the stack enters a junction.
/// An occupied side output keeps the belt stack waiting before that entrance.
pub(super) fn distribute(
    game: &mut Game<'_>,
    segment_pos: [i32; 3],
    movement: Direction,
    stack: &mut ItemStack,
) -> bool {
    let above = offset(segment_pos, [0, 1, 0]);
    if stack.count <= 1 || game.native_block(above) != TUNNEL {
        return true;
    }
    let axis = if matches!(movement, Direction::East | Direction::West) {
        "x"
    } else {
        "z"
    };
    if game.native_block_property(above, "axis").as_deref() != Some(axis) {
        return true;
    }
    let shape = game.native_block_property(above, "shape");
    let [left, right] = sides(movement);
    let outputs: &[Direction] = match shape.as_deref() {
        Some("cross") => &[right, left],
        Some("t_left") => &[left],
        Some("t_right") => &[right],
        _ => return true,
    };
    for &face in outputs {
        let out = offset(segment_pos, delta(face));
        if game.native_block(out) != DEPOT {
            continue;
        }
        let one = ItemStack {
            count: 1,
            ..stack.clone()
        };
        if receive_stack(game, out, one).is_some() {
            return false;
        }
        stack.count -= 1;
        if stack.count == 1 {
            break;
        }
    }
    true
}
