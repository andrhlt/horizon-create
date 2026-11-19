use std::collections::{BTreeSet, VecDeque};

use horizon_core::geometry::Direction;
use horizon_world::level::{PlaceContext, flags};

use crate::items::ItemStack;

use super::Game;
use super::create_fan::facing;
use super::create_machines::offset;

const FRAME: &str = "create:sail_frame";
const WHITE: &str = "create:white_sail";

pub(super) fn is_sail(name: &str) -> bool {
    name == FRAME || (name.starts_with("create:") && name.ends_with("_sail"))
}

fn face_at(game: &Game<'_>, at: [i32; 3]) -> Option<Direction> {
    let state = game.world.block(at[0], at[1], at[2]);
    is_sail(game.pack.assets.registry.state(state)?.name.as_str())
        .then(|| facing(game, state))
        .flatten()
}

fn in_plane(first: Direction, second: Direction) -> bool {
    first
        .normal()
        .into_iter()
        .zip(second.normal())
        .all(|(a, b)| a * b == 0)
}

pub(super) fn attaches(game: &Game<'_>, at: [i32; 3], toward: Direction) -> bool {
    face_at(game, at).is_some_and(|face| in_plane(face, toward))
}

fn placement_edge(
    game: &mut Game<'_>,
    pos: [i32; 3],
    facing: Direction,
    hit: [f64; 3],
) -> Option<Direction> {
    game.with_level(|blocks, level, _| {
        Direction::ALL
            .into_iter()
            .filter(|&side| {
                let [x, y, z] = offset(pos, side.normal());
                in_plane(facing, side) && blocks.is_replaceable(level.world.block(x, y, z))
            })
            .min_by(|&a, &b| edge_distance(pos, hit, a).total_cmp(&edge_distance(pos, hit, b)))
    })
}

fn edge_distance(pos: [i32; 3], hit: [f64; 3], side: Direction) -> f64 {
    pos.into_iter()
        .zip(side.normal())
        .zip(hit)
        .map(|((at, normal), hit)| (f64::from(at) + 0.5 + f64::from(normal) * 0.5 - hit).powi(2))
        .sum()
}

pub(super) fn redirect_placement(game: &mut Game<'_>, context: &mut PlaceContext) {
    if context.sneaking || !game.may_build() || !matches!(context.item.as_str(), WHITE | FRAME) {
        return;
    }
    let origin = context.clicked_pos;
    let pos = [origin.x, origin.y, origin.z];
    let Some(facing) = face_at(game, pos) else {
        return;
    };
    let Some(side) = placement_edge(game, pos, facing, context.hit.components()) else {
        return;
    };
    context.face = side;
    (context.yaw, context.pitch) = match facing {
        Direction::Down => (0.0, 90.0),
        Direction::Up => (0.0, -90.0),
        Direction::North => (180.0, 0.0),
        Direction::South => (0.0, 0.0),
        Direction::West => (90.0, 0.0),
        Direction::East => (-90.0, 0.0),
    };
}

pub(super) fn use_item(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> bool {
    let Some(facing) = face_at(game, pos) else {
        return false;
    };
    let before = game.native_block(pos);
    let tool = stack.item.as_ref();
    if matches!(tool, WHITE | FRAME) {
        // The sail claims this click even when none of its four edges can be extended.
        let blocked = !game.native_sneaking()
            && game.may_build()
            && placement_edge(game, pos, facing, pos.map(f64::from)).is_none();
        if blocked {
            game.guest_inventory_resend |= game.lan_acting.is_some();
        }
        return blocked;
    }
    let shears = tool == "minecraft:shears";
    let replacement = if shears {
        FRAME.to_owned()
    } else {
        let Some(color) = tool
            .strip_prefix("minecraft:")
            .and_then(|item| item.strip_suffix("_dye"))
        else {
            return false;
        };
        if before == FRAME {
            return false;
        }
        format!("create:{color}_sail")
    };
    let Some(base) = game.native_default_state(&replacement) else {
        return false;
    };
    let name = super::create_fluids::name(facing);
    let Some(state) =
        game.with_level(|_, level, _| level.native_state_with_property(base, "facing", name))
    else {
        return false;
    };
    let center = pos.map(|p| f64::from(p) + 0.5);
    let point = game
        .pick()
        .filter(|hit| hit.pos == pos)
        .map_or(center, |hit| hit.point);
    let dimension = game.native_dimension();

    if before != replacement {
        game.native_set_block(dimension, pos, state, flags::UPDATE_ALL);
    } else {
        let mut sides: Vec<_> = Direction::ALL
            .into_iter()
            .filter(|side| in_plane(facing, *side))
            .collect();
        sides.sort_by(|&a, &b| {
            edge_distance(pos, point, a).total_cmp(&edge_distance(pos, point, b))
        });
        let near = sides
            .iter()
            .map(|side| offset(pos, side.normal()))
            .find(|&at| {
                face_at(game, at) == Some(facing)
                    && !matches!(game.native_block(at).as_str(), FRAME)
                    && game.native_block(at) != replacement
            });
        if let Some(near) = near {
            game.native_set_block(dimension, near, state, flags::UPDATE_ALL);
        } else {
            let mut pending = VecDeque::from([pos]);
            let mut seen = BTreeSet::from([pos]);
            for _ in 0..100 {
                let Some(current) = pending.pop_front() else {
                    break;
                };
                for side in &sides {
                    let at = offset(current, side.normal());
                    let block = game.native_block(at);
                    if (!shears && block == FRAME)
                        || face_at(game, at) != Some(facing)
                        || !seen.insert(at)
                    {
                        continue;
                    }
                    if block != replacement {
                        game.native_set_block(dimension, at, state, flags::UPDATE_ALL);
                    }
                    pending.push_back(at);
                }
            }
        }
    }
    let sound = if shears {
        "minecraft:entity.sheep.shear"
    } else {
        "minecraft:item.dye.use"
    };
    game.native_play_sound_in_place(sound, point, 4, 1.0, 1.0);
    true
}
