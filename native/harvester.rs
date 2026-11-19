use horizon_core::geometry::Direction;
use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};

use super::Game;
use super::create_bearing::{deposit, relative};
use super::create_fan::facing;
use super::create_machines::offset;
use crate::items::ItemStack;

pub(super) const HARVESTER: &str = "create:mechanical_harvester";

pub(super) fn cut(game: &mut Game<'_>, pos: [i32; 3]) -> Vec<ItemStack> {
    let name = game.native_block(pos);
    let (mature, seed) = match name.as_str() {
        "minecraft:wheat" => ("7", "minecraft:wheat_seeds"),
        "minecraft:carrots" => ("7", "minecraft:carrot"),
        "minecraft:potatoes" => ("7", "minecraft:potato"),
        "minecraft:beetroots" => ("3", "minecraft:beetroot_seeds"),
        "minecraft:nether_wart" => ("3", "minecraft:nether_wart"),
        "minecraft:torchflower" => ("", "minecraft:torchflower_seeds"),
        _ => return Vec::new(),
    };
    if !mature.is_empty() && game.native_block_property(pos, "age").as_deref() != Some(mature) {
        return Vec::new();
    }
    let replant = if name == "minecraft:torchflower" {
        "minecraft:torchflower_crop"
    } else {
        &name
    };
    let new_state = game.native_default_state(replant);
    let Some(mut drops) = game.native_machine_destroy_block(pos, None, true) else {
        return Vec::new();
    };
    if let Some(new_state) = new_state {
        let soil = game.native_block(offset(pos, [0, -1, 0]));
        if soil == "minecraft:farmland"
            || name == "minecraft:nether_wart" && soil == "minecraft:soul_sand"
        {
            if let Some(drop) = drops.iter_mut().find(|drop| drop.item.as_ref() == seed) {
                drop.count -= 1;
            }
            game.native_set_block(game.native_dimension(), pos, new_state, flags::UPDATE_ALL);
        }
    }
    drops.retain(|stack| stack.count > 0);
    drops
}

pub(super) fn active_cell(anchor: [f64; 3], block: [i32; 3], face: Direction) -> [i32; 3] {
    let n = face.normal();
    std::array::from_fn(|i| {
        (anchor[i] + f64::from(block[i]) + 0.5 + f64::from(n[i]) * 0.45).floor() as i32
    })
}

pub(super) fn translate(
    game: &mut Game<'_>,
    blocks: &mut [Compound],
    previous: [f64; 3],
    current: [f64; 3],
    cart_items: &mut [Option<ItemStack>],
) {
    for index in 0..blocks.len() {
        let (before, actor_and_after) = blocks.split_at_mut(index);
        let Some((actor, after)) = actor_and_after.split_first_mut() else {
            continue;
        };
        let Some(state) = actor
            .get(&"BlockState".into())
            .and_then(|tag| game.state_from_nbt(tag))
        else {
            continue;
        };
        if game.res.facts().get(state).name.as_ref() != HARVESTER {
            continue;
        }
        let Some(face) = facing(game, state) else {
            continue;
        };
        let cell = active_cell(current, relative(actor), face);
        let prior = match actor.get(&"LastHarvestCell".into()) {
            Some(Tag::IntArray(pos)) => pos.as_slice().try_into().ok(),
            _ => None,
        };
        actor.insert("LastHarvestCell".into(), Tag::IntArray(cell.to_vec()));
        let direction = face.normal();
        let forward = (0..3)
            .map(|i| (current[i] - previous[i]) * f64::from(direction[i]))
            .sum::<f64>();
        if prior == Some(cell) || forward < 0.0 {
            continue;
        }
        for stack in cut(game, cell) {
            let max = game
                .items()
                .get(&stack.item)
                .map_or(64, |item| item.max_stack);
            if let Some(rest) =
                deposit(before, stack, max).and_then(|rest| deposit(after, rest, max))
            {
                if let Some(rest) = store(game, cart_items, rest) {
                    game.pop_resource(cell, rest);
                }
            }
        }
    }
}

pub(super) fn store(
    game: &Game<'_>,
    items: &mut [Option<ItemStack>],
    mut stack: ItemStack,
) -> Option<ItemStack> {
    let max = game
        .items()
        .get(&stack.item)
        .map_or(64, |item| item.max_stack);
    for slot in items.iter_mut() {
        if let Some(existing) = slot
            .as_mut()
            .filter(|item| item.same_item_same_components(&stack))
        {
            let amount = stack.count.min(max.saturating_sub(existing.count));
            existing.count += amount;
            stack.count -= amount;
        }
    }
    for slot in items.iter_mut().filter(|slot| slot.is_none()) {
        if stack.count == 0 {
            break;
        }
        let count = stack.count.min(max);
        *slot = Some(ItemStack {
            count,
            ..stack.clone()
        });
        stack.count -= count;
    }
    (stack.count > 0).then_some(stack)
}
