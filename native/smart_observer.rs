use horizon_core::geometry::Direction;
use horizon_world::nbt::{Compound, Tag};

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_fluid_tank::{self, CREATIVE, TANK};
use super::create_fluids;
use super::create_item_filters;
use super::create_machines::{float, int, mod_entity, offset};
use super::create_threshold_switch::{delta, target};

pub(super) const OBSERVER: &str = "create:content_observer";

pub(super) fn observed_pos(game: &Game<'_>, pos: [i32; 3]) -> [i32; 3] {
    let [x, y, z] = pos;
    let state = game.world.block(x, y, z);
    let attachment = game
        .native_block_state_property(state, "target")
        .unwrap_or("wall");
    let facing = game
        .native_block_state_property(state, "facing")
        .unwrap_or("north");
    offset(pos, delta(target(attachment, facing)))
}

fn is_chute(game: &Game<'_>, pos: [i32; 3]) -> bool {
    matches!(
        game.native_block(pos).as_str(),
        "create:chute" | "create:smart_chute"
    )
}

fn detects_fluid(game: &Game<'_>, at: [i32; 3], nbt: &Compound) -> bool {
    if create_fluids::fluid_block(game, at) {
        return create_fluids::incoming_matches(game, at, |fluid| {
            create_item_filters::accepts_fluid(nbt, fluid)
        });
    }
    if matches!(game.native_block(at).as_str(), TANK | CREATIVE)
        && let Some((_, _, Some(fluid))) = create_fluid_tank::storage(game, at)
    {
        return create_item_filters::accepts_fluid(nbt, &fluid);
    }
    false
}

fn detects_inventory(game: &Game<'_>, [x, y, z]: [i32; 3], nbt: &Compound) -> bool {
    let pos = (x, y, z);
    // Create observes the unsided inventory capability, which combines paired chests.
    std::iter::once(pos)
        .chain(game.chest_other_half(pos))
        .filter_map(|pos| game.world.block_entities.get(&pos))
        .flat_map(|storage| storage.slots().iter().flatten())
        .any(|stack| create_item_filters::accepts(game.items(), nbt, stack))
}

fn sampled_in_block_tick(game: &Game<'_>, pos: [i32; 3]) -> bool {
    is_chute(game, pos)
        || create_fluids::fluid_block(game, pos)
        || matches!(
            game.native_block(pos).as_str(),
            super::create_belt::BELT
                | super::create_depot::DEPOT
                | super::create_belt_funnel::ANDESITE
                | super::create_belt_funnel::BRASS
                | super::create_funnel::ANDESITE
                | super::create_funnel::BRASS
        )
}

fn sample(
    game: &Game<'_>,
    pos: [i32; 3],
    entity: &ModBlockEntity,
    at: [i32; 3],
) -> (i32, Option<bool>) {
    let filter = super::create_depot::compound(&entity.nbt, "Filter");
    let target = game.world.block(at[0], at[1], at[2]);
    let target_item = &game.res.facts().get(target).item;
    let active = game.native_block_property(pos, "powered").as_deref() == Some("true");
    let remaining = int(&entity.nbt, "TurnOff").unwrap_or(0);
    let delay = if target_item.as_ref() != "minecraft:air"
        && filter.is_some_and(|filter| {
            ItemStack::from_nbt(filter).is_some()
                && create_item_filters::matches(
                    game.items(),
                    filter,
                    &ItemStack::new(target_item, 1),
                    false,
                )
        }) {
        3
    } else if game.native_block(at) == super::create_belt::BELT {
        if super::create_belt::detect_centered(game, at, |stack| {
            create_item_filters::accepts(game.items(), &entity.nbt, stack)
        }) {
            6
        } else {
            (remaining - 1).max(0)
        }
    } else if game.native_block(at) == super::create_depot::DEPOT {
        let sees_held_item = mod_entity(game, at).is_some_and(|depot| {
            let position = float(&depot.nbt, "BeltPosition").unwrap_or(0.0);
            0.5 - position <= 0.45
                && depot
                    .items
                    .first()
                    .and_then(Option::as_ref)
                    .is_some_and(|stack| {
                        create_item_filters::accepts(game.items(), &entity.nbt, stack)
                    })
        });
        if sees_held_item {
            6
        } else {
            (remaining - 1).max(0)
        }
    } else if detects_fluid(game, at, &entity.nbt) || detects_inventory(game, at, &entity.nbt) {
        6
    } else {
        (remaining - 1).max(0)
    };
    let powered = delay > 0 || active && remaining > 0;
    (delay, (active != powered).then_some(powered))
}

fn update_power(game: &mut Game<'_>, pos: [i32; 3], changed: Option<bool>) {
    if let Some(powered) = changed {
        game.native_set_block_property(pos, "powered", if powered { "true" } else { "false" });
    }
}

pub(super) fn tick(game: &mut Game<'_>) {
    let ticking = game.block_ticking_area();
    let updates: Vec<_> = game
        .world
        .block_entity_tickers()
        .iter()
        .filter_map(|entry| {
            let (x, y, z) = entry.0;
            let pos = [x, y, z];
            let entity = mod_entity(game, pos)?;
            if entity.id != OBSERVER || !ticking(x, z) {
                return None;
            }
            let at = observed_pos(game, pos);
            if sampled_in_block_tick(game, at) {
                return None;
            }
            let (delay, changed) = sample(game, pos, entity, at);
            (changed.is_some() || int(&entity.nbt, "TurnOff") != Some(delay))
                .then_some((pos, delay, changed))
        })
        .collect();
    for (pos, delay, changed) in updates {
        game.native_with_mod_block_entity(pos, |entity| {
            entity.nbt.insert("TurnOff".into(), Tag::Int(delay));
        });
        update_power(game, pos, changed);
    }
}

pub(super) fn tick_live_target(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let at = observed_pos(game, pos);
    if !sampled_in_block_tick(game, at) {
        return;
    }
    let (delay, changed) = sample(game, pos, entity, at);
    entity.nbt.insert("TurnOff".into(), Tag::Int(delay));
    update_power(game, pos, changed);
}

pub(super) fn funnel_transfer(game: &mut Game<'_>, funnel: [i32; 3], item: &ItemStack) {
    for face in Direction::ALL {
        let pos = offset(funnel, delta(face));
        if game.native_block(pos) != OBSERVER || observed_pos(game, pos) != funnel {
            continue;
        }
        if !mod_entity(game, pos).is_some_and(|entity| {
            super::create_item_filters::accepts(game.items(), &entity.nbt, item)
        }) {
            continue;
        }
        game.native_with_mod_block_entity(pos, |entity| {
            entity.nbt.insert("TurnOff".into(), Tag::Int(4));
        });
        update_power(game, pos, Some(true));
    }
}
