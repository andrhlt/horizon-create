use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use super::create_depot::compound;
use super::create_item_filters;
use super::create_station::{targeting_position, valid_track};
use super::create_train::CARRIAGE;
use super::create_train_portable_items::cargo_storage;
use super::{Game, GameLevel};
use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

pub(super) const OBSERVER: &str = "create:track_observer";

fn list<'a>(data: &'a Compound, key: &str) -> Option<&'a [Tag]> {
    match data.get(&key.into())? {
        Tag::List(values) => Some(values),
        _ => None,
    }
}

fn accepts_filter(game: &Game<'_>, train: u32, filter: &Compound) -> bool {
    let Some(Tag::Compound(carriage)) = game
        .persist
        .raw
        .get(&train)
        .and_then(|raw| raw.get(CARRIAGE))
    else {
        return false;
    };
    let Some(blocks) = list(carriage, "Blocks") else {
        return false;
    };
    blocks.iter().any(|tag| {
        let Tag::Compound(block) = tag else {
            return false;
        };
        let item_match = cargo_storage(block).is_some_and(|(storage, _)| {
            list(storage, "Items").is_some_and(|items| {
                items.iter().any(|item| {
                    let Tag::Compound(item) = item else {
                        return false;
                    };
                    ItemStack::from_nbt(item).is_some_and(|stack| {
                        create_item_filters::matches(game.items(), filter, &stack, false)
                    })
                })
            })
        });
        let fluid_match = super::create_depot::compound(block, "BlockState")
            .and_then(|state| super::create_machines::string(state, "Name"))
            .as_deref()
            == Some(super::create_fluid_tank::TANK)
            && super::create_depot::compound(block, "Entity")
                .and_then(|entity| compound(entity, "TankContent"))
                .and_then(|tank| compound(tank, "Fluid"))
                .and_then(super::create_fluids::read_fluid)
                .is_some_and(|fluid| create_item_filters::matches_fluid(filter, &fluid, true));
        item_match || fluid_match
    })
}

fn passes_filter(game: &Game<'_>, nbt: &Compound, train: u32) -> bool {
    let Some(filter) = compound(nbt, "Filter").filter(|filter| {
        ItemStack::from_nbt(filter).is_some_and(|stack| stack.item.as_ref() != "minecraft:air")
    }) else {
        return true;
    };
    accepts_filter(game, train, filter)
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let observed = targeting_position(&entity.nbt, pos).and_then(|(track, _)| {
        valid_track(game, track)?;
        super::create_train::wheel_positions_with_id(game, None).find_map(|(id, wheels)| {
            (wheels
                .into_iter()
                .any(|wheel| super::create_train_track::point_on_track(game, track, wheel))
                && passes_filter(game, &entity.nbt, id))
            .then_some(id)
        })
    });
    let now = game.world.game_time;
    if let Some(id) = observed {
        entity
            .nbt
            .insert("ObservedTrain".into(), Tag::Int(id as i32));
        entity
            .nbt
            .insert("ActivatedUntil".into(), Tag::Long(now + 8));
    }
    let active =
        matches!(entity.nbt.get(&"ActivatedUntil".into()), Some(Tag::Long(until)) if *until > now);
    if !active {
        entity.nbt.remove(&"ObservedTrain".into());
    }
    if (game.native_block_property(pos, "powered").as_deref() == Some("true")) != active {
        game.native_set_block_property_with(
            pos,
            "powered",
            if active { "true" } else { "false" },
            flags::UPDATE_ALL,
        );
        super::create_display_link::observed_train_changed(
            game,
            pos,
            active
                .then(|| {
                    observed.or_else(|| match entity.nbt.get(&"ObservedTrain".into()) {
                        Some(Tag::Int(id)) => Some(*id as u32),
                        _ => None,
                    })
                })
                .flatten(),
        );
    }
}

pub(super) fn signal(level: &GameLevel<'_>, state: BlockStateId, direct: bool, output: &mut i32) {
    if !direct && let Some(state) = level.registry.state(state).filter(|s| s.name == OBSERVER) {
        *output = if state
            .properties
            .get("powered")
            .is_some_and(|p| p.as_str() == "true")
        {
            15
        } else {
            0
        };
    }
}
