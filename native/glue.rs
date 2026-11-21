use std::collections::{BTreeSet, VecDeque};
use std::time::Instant;

use horizon_core::geometry::Direction;
use horizon_world::nbt::{Compound, Tag};

use crate::items::ItemStack;

use super::create_machines::offset;
use super::Game;
use horizon_client::first_person::Hand;

pub(super) const ITEM: &str = "create:super_glue";
pub(super) const SELECTION: &str = "create:super_glue_start";
pub(super) const MARKER: &str = "CreateSuperGlue";

fn clear(game: &mut Game<'_>) {
    if let Some(stack) = game.held_mut() {
        stack.data_mut().set_other(SELECTION, None);
        stack.tidy();
    }
}

fn consume_inventory_charge(game: &mut Game<'_>) -> bool {
    if game.creative {
        return true;
    }
    // The Java selection handler sends the packet from the main hand. Its
    // helper searches the selected slot first, then every inventory slot.
    if game.hand != Hand::Main {
        return false;
    }
    let selected = game.selected;
    for slot in std::iter::once(selected).chain(0..game.inventory.len()) {
        if !game
            .inventory
            .get(slot)
            .and_then(Option::as_ref)
            .is_some_and(|stack| stack.item.as_ref() == ITEM)
        {
            continue;
        }
        if slot != selected {
            // Route durability through the ordinary held-item path so wear,
            // break effects and the authoritative slot update stay intact.
            game.inventory.swap(selected, slot);
        }
        game.damage_held(1);
        if slot != selected {
            game.inventory.swap(selected, slot);
        }
        game.guest_inventory_resend |= game.lan_acting.is_some();
        return true;
    }
    false
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

fn glue_at(game: &Game<'_>, pos: [i32; 3]) -> Option<u32> {
    let held = game.held()?;
    if game.hand != Hand::Main || held.item.as_ref() != ITEM {
        return None;
    }
    let player_position = game
        .native_acting_player()
        .map(|player| player.position)
        .or_else(|| {
            game.player
                .as_ref()
                .map(|player| player.position.components())
        })?;
    game.others
        .iter()
        .filter_map(|entity| {
            if entity.kind != "minecraft:marker" {
                return None;
            }
            let Tag::Compound(data) = game.persist.raw.get(&entity.id)? else {
                return None;
            };
            if data.get(&MARKER.into()) != Some(&Tag::Byte(1)) {
                return None;
            }
            let [Tag::Double(fx), Tag::Double(fy), Tag::Double(fz)] =
                (match data.get(&"From".into()) {
                    Some(Tag::List(values)) => values.as_slice(),
                    _ => return None,
                })
            else {
                return None;
            };
            let [Tag::Double(tx), Tag::Double(ty), Tag::Double(tz)] = (match data.get(&"To".into())
            {
                Some(Tag::List(values)) => values.as_slice(),
                _ => return None,
            }) else {
                return None;
            };
            let from = [*fx, *fy, *fz].map(f64::from_bits);
            let to = [*tx, *ty, *tz].map(f64::from_bits);
            let origin = entity.position.components();
            let low = std::array::from_fn::<_, 3, _>(|i| origin[i] + from[i].min(to[i]));
            let high = std::array::from_fn::<_, 3, _>(|i| origin[i] + from[i].max(to[i]));
            let inside = (0..3).all(|i| {
                let center = f64::from(pos[i]) + 0.5;
                center >= low[i] && center < high[i]
            });
            let entity_position = entity.position.components();
            let distance_squared = (0..3)
                .map(|i| (player_position[i] - entity_position[i]).powi(2))
                .sum::<f64>();
            (inside && distance_squared <= 32.0 * 32.0).then_some((entity.id, distance_squared))
        })
        .min_by(|left, right| left.1.total_cmp(&right.1))
        .map(|(id, _)| id)
}

pub(super) fn attack_block(game: &mut Game<'_>, pos: [i32; 3], canceled: &mut bool) {
    let Some(id) = glue_at(game, pos) else {
        return;
    };
    game.native_remove_entity(game.native_dimension(), id);
    *canceled = true;
}

pub(super) fn use_item(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> bool {
    if stack.item.as_ref() != ITEM {
        return false;
    }
    // Create's client selection handler reads the main hand only.
    if game.hand != Hand::Main {
        return true;
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
        // Java's helper consumes one charge during both the availability
        // check and the actual collection, searching inventory after a break.
        consume_inventory_charge(game);
        consume_inventory_charge(game);
        game.message = Some(("Blocks glued together".into(), Instant::now()));
    }
    true
}
