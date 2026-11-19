use horizon_world::nbt::{Compound, Tag};

use super::create_depot::compound;
use super::create_machines::mod_entity;
use super::{Game, Hit};
use crate::{items::ItemStack, save::item_to_nbt};

fn special_filter(stack: &ItemStack) -> bool {
    matches!(
        stack.item.as_ref(),
        "create:filter" | "create:attribute_filter" | "create:package_filter"
    )
}

pub(super) fn targets(game: &Game<'_>, hit: &Hit) -> bool {
    if game.native_sneaking() || game.native_block(hit.pos) != "create:creative_crate" {
        return false;
    }
    let center = [0.5, 13.5 / 16.0, 0.5];
    let distance: f64 = (0..3)
        .map(|axis| (hit.point[axis] - f64::from(hit.pos[axis]) - center[axis]).powi(2))
        .sum();
    if distance >= 0.25_f64.powi(2) {
        return false;
    }
    let held = game.held();
    if held.is_some_and(|stack| {
        matches!(
            stack.item.as_ref(),
            "create:wrench" | "create:mechanical_arm"
        )
    }) {
        return false;
    }
    true
}

pub(super) fn interact(game: &mut Game<'_>, hit: &Hit) -> bool {
    if !game.native_authoritative() || !targets(game, hit) {
        return false;
    }
    let held = game.held().cloned();
    let previous = mod_entity(game, hit.pos)
        .and_then(|entity| ItemStack::from_nbt(compound(&entity.nbt, "Filter")?))
        .filter(special_filter);
    let mut sample = held.clone();
    if let Some(stack) = sample.as_mut().filter(|stack| special_filter(stack)) {
        stack.count = 1;
        if stack.data().is_some() {
            let data = stack.data_mut();
            data.enchantments.clear();
            data.set_other("minecraft:attribute_modifiers", None);
            for key in ["!minecraft:enchantments", "!minecraft:attribute_modifiers"] {
                data.set_other(key, Some(Tag::Compound(Compound::new())));
            }
        }
    }
    let value = sample
        .as_ref()
        .map_or_else(|| Tag::Compound(Compound::new()), item_to_nbt);
    if game
        .native_with_mod_block_entity(hit.pos, |entity| {
            entity.nbt.insert("Filter".into(), value);
            entity
                .nbt
                .entry("FilterAmount".into())
                .or_insert(Tag::Int(64));
            entity.nbt.entry("UpTo".into()).or_insert(Tag::Byte(1));
        })
        .is_none()
    {
        return false;
    }
    if let Some(previous) = previous
        && (!game.creative
            || !game
                .inventory
                .iter()
                .flatten()
                .any(|stack| stack.same_item_same_components(&previous)))
    {
        game.give_or_drop(previous);
    }
    if !game.creative && held.as_ref().is_some_and(special_filter) {
        game.consume_held();
    }
    game.guest_inventory_resend |= game.lan_acting.is_some();
    game.native_block_entity_sync(hit.pos);
    let center = hit.pos.map(|coord| f64::from(coord) + 0.5);
    game.native_play_sound_in_place("minecraft:entity.item_frame.add_item", center, 4, 0.25, 0.1);
    true
}


pub(super) fn sample(game: &Game<'_>, pos: [i32; 3]) -> Option<ItemStack> {
    let entity = mod_entity(game, pos)?;
    ItemStack::from_nbt(compound(&entity.nbt, "Filter")?)
}

/// The bottomless handler accepts every input stack while keeping its filter.
pub(super) fn accepts_items(game: &Game<'_>, pos: [i32; 3]) -> bool {
    game.native_block(pos) == "create:creative_crate" && mod_entity(game, pos).is_some()
}

pub(super) fn insert(
    game: &mut Game<'_>,
    pos: [i32; 3],
    face: horizon_core::geometry::Direction,
    stack: ItemStack,
) -> Option<ItemStack> {
    if accepts_items(game, pos) {
        None
    } else {
        game.native_insert_item(pos, face, stack)
    }
}
