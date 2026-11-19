use std::collections::{BTreeSet, VecDeque};
use std::time::Instant;

use horizon_core::geometry::Direction;
use horizon_world::nbt::{Compound, Tag};

use crate::items::ItemStack;

use super::Game;
use super::create_machines::offset;

pub(super) const ITEM: &str = "create:super_glue";
pub(super) const SELECTION: &str = "create:super_glue_start";
pub(super) const MARKER: &str = "CreateSuperGlue";

fn clear(game: &mut Game<'_>) {
    if let Some(stack) = game.held_mut() {
        stack.data_mut().set_other(SELECTION, None);
        stack.tidy();
    }
}

fn attached(game: &Game<'_>, first: [i32; 3], second: [i32; 3]) -> bool {
    let low = std::array::from_fn::<_, 3, _>(|i| first[i].min(second[i]));
    let high = std::array::from_fn::<_, 3, _>(|i| first[i].max(second[i]));
    let mut visited = BTreeSet::from([first]);
    let mut next = VecDeque::from([first]);
    while let Some(block) = next.pop_front() {
        for side in Direction::ALL {
            let other = offset(block, side.normal());
            if (0..3).any(|i| other[i] < low[i] || other[i] > high[i])
                || matches!(
                    game.native_block(other).as_str(),
                    "minecraft:air"
                        | "minecraft:cave_air"
                        | "minecraft:void_air"
                        | "minecraft:water"
                        | "minecraft:lava"
                        | "minecraft:bedrock"
                        | "minecraft:barrier"
                )
                || !visited.insert(other)
            {
                continue;
            }
            if other == second {
                return true;
            }
            next.push_back(other);
        }
    }
    false
}

fn vector(values: [f64; 3]) -> Tag {
    Tag::List(values.map(|value| Tag::Double(value.to_bits())).to_vec())
}

pub(super) fn use_item(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> bool {
    if stack.item.as_ref() != ITEM {
        return false;
    }
    let first = stack.data().and_then(|data| match data.other(SELECTION)? {
        Tag::IntArray(pos) => <[i32; 3]>::try_from(pos.as_slice()).ok(),
        _ => None,
    });
    if game.native_sneaking() {
        if first.is_some() {
            clear(game);
            game.message = Some(("Glue selection cancelled".into(), Instant::now()));
        }
        return true;
    }
    let Some(first) = first else {
        if let Some(held) = game.held_mut() {
            held.data_mut()
                .set_other(SELECTION, Some(Tag::IntArray(pos.to_vec())));
        }
        game.message = Some((
            "Select the other corner to glue these blocks".into(),
            Instant::now(),
        ));
        return true;
    };
    let distance = (0..3)
        .map(|i| (i64::from(pos[i]) - i64::from(first[i])).pow(2))
        .sum::<i64>();
    if distance == 0 || distance >= 24 * 24 || !attached(game, first, pos) {
        game.message = Some((
            "Select a connected block within 24 blocks".into(),
            Instant::now(),
        ));
        return true;
    }
    let low = std::array::from_fn::<_, 3, _>(|i| f64::from(pos[i].min(first[i])));
    let high = std::array::from_fn::<_, 3, _>(|i| f64::from(pos[i].max(first[i])) + 1.0);
    let center = [(low[0] + high[0]) / 2.0, low[1], (low[2] + high[2]) / 2.0];
    let from = std::array::from_fn(|i| low[i] - center[i]);
    let to = std::array::from_fn(|i| high[i] - center[i]);
    let data = Compound::from([
        (MARKER.into(), Tag::Byte(1)),
        ("From".into(), vector(from)),
        ("To".into(), vector(to)),
    ]);
    if game
        .native_summon(game.native_dimension(), "minecraft:marker", center, data)
        .is_some()
    {
        clear(game);
        // Java's server packet checks availability and then consumes it;
        // both calls wear the held glue, including the simulated check.
        game.damage_held(1);
        game.damage_held(1);
        game.message = Some(("Blocks glued together".into(), Instant::now()));
    }
    true
}
