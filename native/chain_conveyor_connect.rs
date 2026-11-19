use std::cell::RefCell;
use std::collections::HashMap;

use horizon_client::text::Text;
use horizon_world::nbt::{Compound, Tag};

use super::Game;
use super::create_chain_conveyor::chain_cost;
use super::create_machines::{CONVEYOR, mod_entity, offset, refresh_connected_network};
use crate::items::ItemStack;

pub(super) const CHAIN: &str = "minecraft:iron_chain";
const MAX_CONNECTIONS: usize = 4;
pub(super) const MAX_DISTANCE: f64 = 32.0;
type SelectionKey = ([i32; 4], String, String);

thread_local! {
    static SELECTIONS: RefCell<HashMap<SelectionKey, [i32; 3]>> = RefCell::new(HashMap::new());
}

pub(super) fn links(nbt: &Compound) -> impl Iterator<Item = [i32; 3]> + '_ {
    let tags = match nbt.get(&"Connections".into()) {
        Some(Tag::List(links)) => links.as_slice(),
        _ => &[],
    };
    tags.iter().filter_map(|tag| match tag {
        Tag::IntArray(delta) => delta.as_slice().try_into().ok(),
        _ => None,
    })
}

fn add_link(game: &mut Game<'_>, at: [i32; 3], delta: [i32; 3]) {
    game.native_with_mod_block_entity(at, |entity| {
        let mut updated: Vec<_> = links(&entity.nbt)
            .map(|link| Tag::IntArray(link.to_vec()))
            .collect();
        updated.push(Tag::IntArray(delta.to_vec()));
        entity.nbt.insert("Connections".into(), Tag::List(updated));
    });
    game.native_block_entity_sync(at);
}

pub(super) fn disconnect(game: &mut Game<'_>, origin: [i32; 3], edge: [i32; 3]) {
    let other = offset(origin, edge);
    for (at, removed) in [(origin, edge), (other, edge.map(|axis| -axis))] {
        super::create_chain_conveyor_packages::drop_span(game, at, removed);
        game.native_with_mod_block_entity(at, |entity| {
            let retained = links(&entity.nbt)
                .filter(|link| *link != removed)
                .map(|link| Tag::IntArray(link.to_vec()))
                .collect();
            entity.nbt.insert("Connections".into(), Tag::List(retained));
        });
        game.native_block_entity_sync(at);
    }
    refresh_connected_network(game, origin);
    refresh_connected_network(game, other);

    let player = game.native_acting_id();
    if !game.creative
        && let Some(excess) =
            game.native_give_stack(player, ItemStack::new(CHAIN, chain_cost(edge)))
        && let Some(eye) = game.eye_position()
    {
        game.throw_from_eyes(excess, eye, false);
    }
    if let Some(player) = game.native_acting_player() {
        game.native_play_sound_in_place(
            "minecraft:block.chain.break",
            player.position,
            4,
            1.0,
            1.0,
        );
    }
}

fn available(game: &Game<'_>) -> u32 {
    game.inventory
        .iter()
        .chain([&game.offhand])
        .flatten()
        .filter(|stack| stack.item.as_ref() == CHAIN)
        .map(|stack| stack.count)
        .sum()
}

fn pay(game: &mut Game<'_>, mut cost: u32) {
    let (before, rest) = game.inventory.split_at_mut(game.selected);
    let (selected, after) = rest.split_first_mut().expect("selected hotbar slot");
    for slot in before
        .iter_mut()
        .chain(after)
        .chain([selected, &mut game.offhand])
    {
        if let Some(stack) = slot.as_mut().filter(|stack| stack.item.as_ref() == CHAIN) {
            let used = cost.min(stack.count);
            stack.count -= used;
            cost -= used;
            if stack.count == 0 {
                *slot = None;
            }
        }
        if cost == 0 {
            break;
        }
    }
}

fn message(game: &mut Game<'_>, key: &str) {
    game.send_overlay_message(Text::translate(key, &[]));
}

fn connect(game: &mut Game<'_>, from: [i32; 3], to: [i32; 3]) -> Option<()> {
    let delta: [i32; 3] = std::array::from_fn(|axis| to[axis] - from[axis]);
    let [x, y, z] = delta.map(f64::from);
    let distance_squared = x * x + y * y + z * z;
    let horizontal = (x * x + z * z).sqrt() - 1.5;
    let inverse = delta.map(|axis| -axis);
    let first = mod_entity(game, from).filter(|entity| entity.id == CONVEYOR)?;
    let last = mod_entity(game, to).filter(|entity| entity.id == CONVEYOR)?;
    let cost = chain_cost(delta);
    let failure = if distance_squared >= MAX_DISTANCE * MAX_DISTANCE {
        "chain_conveyor.too_far"
    } else if distance_squared < 2.5 * 2.5 {
        "chain_conveyor.too_close"
    } else if horizontal <= 0.0 {
        "chain_conveyor.cannot_connect_vertically"
    } else if y.abs() / horizontal > 1.0 {
        "chain_conveyor.too_steep"
    } else if links(&first.nbt).count() >= MAX_CONNECTIONS
        || links(&last.nbt).count() >= MAX_CONNECTIONS
    {
        "chain_conveyor.cannot_add_more_connections"
    } else if links(&first.nbt).any(|link| link == delta)
        || links(&last.nbt).any(|link| link == inverse)
    {
        "chain_conveyor.already_connected"
    } else if !game.creative && available(game) < cost {
        "chain_conveyor.not_enough_chains"
    } else {
        add_link(game, from, delta);
        add_link(game, to, inverse);
        if !game.creative {
            pay(game, cost);
        }
        return Some(());
    };
    message(game, &format!("create.{failure}"));
    None
}

pub(super) fn click(game: &mut Game<'_>, at: [i32; 3]) -> bool {
    if !game.may_build() || game.held().is_none_or(|stack| stack.item.as_ref() != CHAIN) {
        return false;
    }
    let key = (
        game.acting_player_uuid(),
        game.level.name.clone(),
        game.native_dimension().to_owned(),
    );
    let selected = SELECTIONS.with_borrow_mut(|selections| selections.remove(&key));
    if game.native_sneaking() || game.native_block(at) != CONVEYOR {
        if selected.is_some() {
            message(game, "create.chain_conveyor.selection_cleared");
        }
        return selected.is_some();
    }
    if let Some(from) = selected {
        if from != at {
            connect(game, from, at);
        }
    } else {
        SELECTIONS.with_borrow_mut(|selections| selections.insert(key, at));
    }
    true
}
