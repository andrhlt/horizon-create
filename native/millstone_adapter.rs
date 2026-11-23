//! Typed-Part Millstone server adapter.
//!
//! APP-2136 supplies the kinetic `Speed` field. This module owns the stationary
//! machine boundary: ten item slots, recipe matching, timer persistence and
//! output insertion. It intentionally does not walk a kinetic graph.

use std::sync::Arc;

use mod_api::{
    BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent, Compound, Host, ItemStack,
    ModContainer, Registrar, ServerHost, Tag,
};

use super::create_millstone_processing::{self, Tick};

pub const BLOCK: &str = "create:millstone";
const RECIPE_KIND: &str = "create:milling";
const SLOTS: usize = 10;
const INPUT: usize = 0;
const OUTPUTS: std::ops::Range<usize> = 1..SLOTS;

#[derive(Clone, Copy, Default)]
pub struct MillstonePart;

pub fn register(registrar: &mut dyn Registrar) {
    let kind = registrar
        .block_entity_type("create:millstone")
        .blocks(&[BLOCK])
        .build();
    registrar.block_entity_part(&kind, MillstonePart).unwrap();
}

pub fn container(block: &str) -> Option<ModContainer> {
    (block == BLOCK).then(|| ModContainer {
        slots: SLOTS,
        faces: std::array::from_fn(|_| (0..SLOTS).collect()),
        inputs: vec![INPUT],
        outputs: OUTPUTS.collect(),
        menu: None,
    })
}

fn int(nbt: &Compound, key: &str) -> i32 {
    match nbt.get(&key.into()) {
        Some(Tag::Int(value)) => *value,
        Some(Tag::Byte(value)) => i32::from(*value),
        _ => 0,
    }
}

fn float(nbt: &Compound, key: &str) -> f32 {
    match nbt.get(&key.into()) {
        Some(Tag::Float(value)) => f32::from_bits(*value),
        _ => 0.0,
    }
}

fn set_timer(nbt: &mut Compound, timer: i32) {
    nbt.insert("Timer".into(), Tag::Int(timer));
}

fn recipe_for(host: &dyn Host, input: &ItemStack) -> Option<(i32, Arc<serde_json::Value>)> {
    host.recipes_of_type(RECIPE_KIND).iter().find_map(|recipe| {
        let ingredients = recipe.json["ingredients"].as_array()?;
        let ingredient = ingredients.first()?;
        let json = serde_json::to_string(ingredient).ok()?;
        let ingredient = host.recipe_ingredient(&json).ok().flatten()?;
        ingredient.test(host, input).then(|| {
            let time = recipe.json["processing_time"]
                .as_i64()
                .map_or(millstone_processing::DEFAULT_PROCESSING_TIME, |value| {
                    value as i32
                });
            (time, recipe.json.clone())
        })
    })
}

fn insert_output(host: &dyn Host, slots: &mut [Option<ItemStack>], mut output: ItemStack) {
    let limit = host.max_stack_size(output.item()).unwrap_or(64);
    for slot in slots.iter_mut().flatten() {
        if slot.item() == output.item() {
            let room = limit.saturating_sub(slot.count());
            let moved = room.min(output.count());
            if moved > 0 {
                let _ = slot.grow(moved);
                output = output.shrink(moved).expect("moved output was nonzero");
                if output.count() == 0 {
                    return;
                }
            }
        }
    }
    for slot in slots.iter_mut() {
        if slot.is_none() {
            *slot = Some(output);
            return;
        }
    }
}

fn finish(host: &dyn Host, slots: &mut [Option<ItemStack>], recipe: &serde_json::Value) {
    let Some(results) = recipe["results"].as_array() else {
        return;
    };
    for result in results {
        let Ok(json) = serde_json::to_string(result) else {
            continue;
        };
        let Some(output) = host.recipe_result(&json).ok().flatten() else {
            continue;
        };
        insert_output(host, slots, output);
    }
}

#[mod_api::horizon_part]
impl BlockEntityPart for MillstonePart {
    fn block_entity_ticks(&self, _: &dyn Host, event: &mut BlockEntityTicksEvent<'_>) {
        event.ticks = true;
    }

    fn block_entity_tick(&self, host: &mut dyn ServerHost, event: &mut BlockEntityTickEvent<'_>) {
        if event.entity.items.len() < SLOTS {
            event.entity.items.resize(SLOTS, None);
        }
        let input = event.entity.items[INPUT].as_ref();
        let Some((recipe_time, recipe)) = input.and_then(|stack| recipe_for(host, stack)) else {
            return;
        };
        let speed = float(&event.entity.nbt, "Speed");
        let timer = int(&event.entity.nbt, "Timer");
        let outputs_full = event.entity.items[OUTPUTS.clone()]
            .iter()
            .flatten()
            .any(|stack| stack.count() >= host.max_stack_size(stack.item()).unwrap_or(64));
        if outputs_full {
            return;
        }
        match millstone_processing::tick(timer, speed, Some(recipe_time), input.is_some()) {
            Tick::Idle => {}
            Tick::Started { timer }
            | Tick::Progressed {
                timer,
                finished: false,
            } => {
                set_timer(&mut event.entity.nbt, timer);
            }
            Tick::Progressed {
                timer,
                finished: true,
            } => {
                set_timer(&mut event.entity.nbt, timer);
                if let Some(stack) = event.entity.items[INPUT].take() {
                    event.entity.items[INPUT] = stack.shrink(1);
                    let (left, right) = event.entity.items.split_at_mut(INPUT + 1);
                    finish(host, &mut right[..], &recipe);
                    let _ = left;
                }
            }
        }
    }
}

/// Hook adapter for the central Hooks implementation. Kept separate so the
/// integration owner can attach it without changing the kinetic registry.
pub fn block_entity_container_hook(
    _: &dyn Host,
    event: &mut mod_api::BlockEntityContainerEvent<'_>,
) -> Option<ModContainer> {
    container(event.block)
}
