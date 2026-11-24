//! Typed-Part Millstone server adapter.
//!
//! APP-2136 supplies the kinetic `Speed` field. This module owns the stationary
//! machine boundary: ten item slots, recipe matching, timer persistence and
//! output insertion. It intentionally does not walk a kinetic graph.

use std::sync::Arc;

use mod_api::{
    BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent, BlockPart, Compound, Host,
    ItemStack, LevelRef, ModContainer, RandomSource, Registrar, ServerHost, Tag,
};

use super::create_millstone_processing as millstone_processing;
use super::create_millstone_processing::Tick;

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

fn effective_speed(nbt: &Compound) -> f32 {
    let speed = float(nbt, "Speed");
    let Some(Tag::Compound(network)) = nbt.get(&"Network".into()) else {
        return speed;
    };
    super::kinetic_slice::effective_speed(
        speed,
        float(network, "Capacity"),
        float(network, "Stress"),
    )
}

fn set_timer(nbt: &mut Compound, timer: i32) {
    nbt.insert("Timer".into(), Tag::Int(timer));
}

fn recipe_for(host: &dyn ServerHost, input: &ItemStack) -> Option<(i32, Arc<mod_api::Recipe>)> {
    host.recipes_of_type(RECIPE_KIND).iter().find_map(|recipe| {
        let ingredients = recipe.json["ingredients"].as_array()?;
        let ingredient = ingredients.first()?;
        // Create recipes serialize Ingredient as `{item: id}` / `{tag: id}`;
        // the pinned Host recipe helper accepts a bare id or `#tag` string.
        let direct_item = ingredient
            .get("item")
            .and_then(|value| value.as_str())
            .map(str::to_owned);
        let ingredient_json = if ingredient.is_string() {
            ingredient.to_string()
        } else if let Some(item) = direct_item.as_deref() {
            format!("{item:?}")
        } else if let Some(tag) = ingredient.get("tag").and_then(|value| value.as_str()) {
            format!("{:?}", format!("#{tag}"))
        } else if let Some(items) = ingredient.get("items").and_then(|value| value.as_array()) {
            let alternatives = items
                .iter()
                .filter_map(|value| {
                    value
                        .as_str()
                        .map(str::to_owned)
                        .or_else(|| value.get("item")?.as_str().map(str::to_owned))
                        .or_else(|| value.get("tag")?.as_str().map(|tag| format!("#{tag}")))
                })
                .map(|value| format!("{value:?}"))
                .collect::<Vec<_>>();
            (!alternatives.is_empty()).then(|| format!("[{}]", alternatives.join(",")))?
        } else {
            return None;
        };
        let matches = if let Some(item) = direct_item {
            mod_api::Identifier::parse(&item)
                .ok()
                .and_then(|id| host.item_key(&id))
                == Some(input.item())
        } else {
            host.recipe_ingredient(&ingredient_json)
                .ok()
                .flatten()
                .is_some_and(|ingredient| ingredient.test(host, input))
        };
        matches.then(|| {
            let time = recipe.json["processing_time"]
                .as_i64()
                .map_or(millstone_processing::DEFAULT_PROCESSING_TIME, |value| {
                    value as i32
                });
            (time, Arc::new(recipe.clone()))
        })
    })
}

fn insert_output(host: &dyn Host, slots: &mut [Option<ItemStack>], mut output: ItemStack) -> bool {
    let limit = host.max_stack_size(output.item()).unwrap_or(64);
    for slot in slots.iter_mut().flatten() {
        if slot.item() == output.item() {
            let room = limit.saturating_sub(slot.count());
            let moved = room.min(output.count());
            if moved > 0 {
                let _ = slot.grow(moved);
                if moved == output.count() {
                    return true;
                }
                output = output
                    .shrink(moved)
                    .expect("partial output move leaves a remainder");
            }
        }
    }
    for slot in slots.iter_mut() {
        if slot.is_none() {
            *slot = Some(output);
            return true;
        }
    }
    false
}

fn finish(
    host: &mut dyn ServerHost,
    slots: &mut [Option<ItemStack>],
    recipe: &mod_api::Recipe,
    level: Option<LevelRef>,
) -> bool {
    let Some(results) = recipe.json["results"].as_array() else {
        return false;
    };
    let mut pending = Vec::new();
    for result in results {
        let Some(output) = host.recipe_result(&result.to_string()).ok().flatten() else {
            continue;
        };
        let chance = result["chance"].as_f64().unwrap_or(1.0) as f32;
        let count = output.count();
        let kept = if chance >= 1.0 {
            count
        } else {
            let Some(level) = level else {
                return false;
            };
            (0..count)
                .filter(|_| {
                    level
                        .with_random(host, |random| random.next_float() <= chance)
                        .unwrap_or(false)
                })
                .count() as u32
        };
        if kept == 0 {
            continue;
        }
        if kept < count {
            let Some(output) = output.shrink(count - kept) else {
                continue;
            };
            pending.push(output);
        } else {
            pending.push(output);
        }
    }

    let mut shadow = slots.to_vec();
    for output in pending {
        if !insert_output(host, &mut shadow, output) {
            return false;
        }
    }
    slots.clone_from_slice(&shadow);
    true
}

#[mod_api::horizon_part]
impl BlockPart for MillstonePart {}

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
        let speed = effective_speed(&event.entity.nbt);
        let timer = int(&event.entity.nbt, "Timer");
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
                let dimension = match event.entity.nbt.get(&"KineticDimension".into()) {
                    Some(Tag::String(value)) => value.to_string_lossy(),
                    _ => String::new(),
                };
                let level = (!dimension.is_empty())
                    .then(|| host.level(&dimension))
                    .flatten()
                    .or_else(|| {
                        host.levels()
                            .list_levels()
                            .into_iter()
                            .find(|level| level.block(host, event.pos).is_some())
                    });
                let completed = {
                    let (left, right) = event.entity.items.split_at_mut(INPUT + 1);
                    if !finish(host, right, &recipe, level) {
                        false
                    } else {
                        if let Some(stack) = left[INPUT].take() {
                            left[INPUT] = stack.shrink(1);
                        }
                        true
                    }
                };
                if completed {
                    set_timer(&mut event.entity.nbt, timer);
                } else {
                    // Keep the input and retry without dropping any result when
                    // the complete result set cannot fit in the output slots.
                    set_timer(&mut event.entity.nbt, 1);
                }
            }
        }
    }
}
