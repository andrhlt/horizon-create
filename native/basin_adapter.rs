//! Typed Basin item processing for dry mixing and compacting recipes.
//!
//! Fluid ingredients and fluid results remain guarded out until the typed fluid
//! storage contract is wired. Inputs are only consumed after every item result
//! has a destination in the Basin's output inventory.

use mod_api::{
    BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent, BlockPart, Compound, Host,
    BlockMetadata, HostBlockStates, ItemStack, LevelRef, ModContainer, RandomSource, Registrar,
    ServerHost, Tag,
};

const BASIN: &str = "create:basin";
const MIXER: &str = "create:mechanical_mixer";
const INPUTS: std::ops::Range<usize> = 0..9;
const OUTPUTS: std::ops::Range<usize> = 9..18;
const SLOTS: usize = 18;

#[derive(Clone, Copy, Default)]
pub struct BasinPart;

pub fn register(registrar: &mut dyn Registrar) {
    let kind = registrar.block_entity_type(BASIN).blocks(&[BASIN]).build();
    registrar.block_entity_part(&kind, BasinPart).unwrap();
    let key = registrar.block_key(BASIN);
    registrar.block_container(&key, container());
}

fn container() -> ModContainer {
    ModContainer {
        slots: SLOTS,
        faces: std::array::from_fn(|_| (0..SLOTS).collect()),
        inputs: INPUTS.collect(),
        outputs: OUTPUTS.collect(),
        menu: None,
    }
}

fn float(nbt: &Compound, key: &str) -> f32 {
    match nbt.get(&key.into()) {
        Some(Tag::Float(value)) => f32::from_bits(*value),
        Some(Tag::Double(value)) => f64::from_bits(*value) as f32,
        _ => 0.0,
    }
}

fn mixer_speed(host: &dyn ServerHost, level: LevelRef, pos: [i32; 3]) -> f32 {
    let above = [pos[0], pos[1] + 1, pos[2]];
    if level.block(host, above).is_none_or(|block| host.block_states().name(block).ok() != Some(MIXER)) {
        return 0.0;
    }
    let Some(entity) = host.block_entity_identity(level, above) else { return 0.0 };
    let Some(nbt) = entity.data(host) else { return 0.0 };
    let speed = float(&nbt, "Speed");
    let Some(Tag::Compound(network)) = nbt.get(&"Network".into()) else { return speed };
    let capacity = float(network, "Capacity");
    let stress = float(network, "Stress");
    if stress > capacity { 0.0 } else { speed }
}

fn basin_level(host: &dyn ServerHost, pos: [i32; 3]) -> Option<LevelRef> {
    host.levels().list_levels().into_iter().find(|level| level.block(host, pos).is_some())
}

fn heat_level(host: &dyn ServerHost, level: LevelRef, pos: [i32; 3]) -> i32 {
    let below = [pos[0], pos[1] - 1, pos[2]];
    if level.block(host, below).is_none_or(|block| host.block_states().name(block).ok() != Some("create:blaze_burner")) {
        return 0;
    }
    match level.block_property(host, below, "blaze").as_deref() {
        Some("seething") => 2,
        Some("kindled" | "fading") => 1,
        _ => 0,
    }
}

fn matched_inputs(host: &dyn Host, recipe: &mod_api::Recipe, slots: &[Option<ItemStack>]) -> Option<Vec<u32>> {
    let ingredients = recipe.json["ingredients"].as_array()?;
    let mut used = vec![0_u32; INPUTS.len()];
    for json in ingredients {
        if json.get("type").is_some() && json.get("item").is_none() && json.get("tag").is_none() { return None; }
        let encoded = if let Some(item) = json.get("item").and_then(|v| v.as_str()) {
            format!("{item:?}")
        } else if let Some(tag) = json.get("tag").and_then(|v| v.as_str()) {
            format!("{:?}", format!("#{tag}"))
        } else if json.is_string() { json.to_string() } else { return None; };
        let required = host.recipe_ingredient(&encoded).ok().flatten()?;
        let found = slots.iter().take(INPUTS.len()).enumerate().find_map(|(index, stack)| {
            let stack = stack.as_ref()?;
            (stack.count() > used[index] && required.test(host, stack)).then_some(index)
        })?;
        used[found] += 1;
    }
    Some(used)
}

fn recipe_for(host: &dyn Host, slots: &[Option<ItemStack>], heat: i32) -> Option<(mod_api::Recipe, Vec<u32>, i32)> {
    for kind in ["create:mixing", "create:compacting"] {
      for recipe in host.recipes_of_type(kind).iter() {
        let needed = match recipe.json["heat_requirement"].as_str() {
            Some("superheated") => 2,
            Some("heated") => 1,
            _ => 0,
        };
        if heat < needed { continue; }
        let Some(used) = matched_inputs(host, recipe, slots) else { continue };
        let duration = recipe.json["processing_time"].as_i64().unwrap_or(100).max(1) as i32;
        return Some((recipe.clone(), used, duration));
      }
    }
    None
}

fn insert(host: &dyn Host, slots: &mut [Option<ItemStack>], mut output: ItemStack) -> bool {
    let limit = host.max_stack_size(output.item()).unwrap_or(64);
    for stack in slots.iter_mut().flatten() {
        if stack.item() != output.item() { continue; }
        let moved = limit.saturating_sub(stack.count()).min(output.count());
        if moved == 0 { continue; }
        let count = output.count();
        let _ = stack.grow(moved);
        if moved == count { return true; }
        let Some(rest) = output.shrink(moved) else { return false };
        output = rest;
    }
    if let Some(slot) = slots.iter_mut().find(|slot| slot.is_none()) {
        *slot = Some(output);
        true
    } else {
        false
    }
}

fn output_plan(host: &mut dyn ServerHost, level: Option<LevelRef>, recipe: &mod_api::Recipe, slots: &[Option<ItemStack>]) -> Option<Vec<Option<ItemStack>>> {
    let results = recipe.json["results"].as_array()?;
    let mut shadow = slots.to_vec();
    for result in results {
        // Fluid output is intentionally rejected until the typed tank adapter lands.
        if result.get("amount").is_some() { return None; }
        let output = host.recipe_result(&result.to_string()).ok().flatten()?;
        let chance = result["chance"].as_f64().unwrap_or(1.0) as f32;
        let count = output.count();
        let kept = if chance >= 1.0 { count } else {
            let level = level?;
            (0..count).filter(|_| level.with_random(host, |random| random.next_float() <= chance).unwrap_or(false)).count() as u32
        };
        if kept == 0 { continue; }
        let output = if kept == count { output } else { output.shrink(count - kept)? };
        let inserted = insert(host, &mut shadow[OUTPUTS], output);
        if !inserted { return None; }
    }
    Some(shadow)
}

#[mod_api::horizon_part]
impl BlockPart for BasinPart {}

#[mod_api::horizon_part]
impl BlockEntityPart for BasinPart {
    fn block_entity_ticks(&self, _: &dyn Host, event: &mut BlockEntityTicksEvent<'_>) { event.ticks = true; }

    fn block_entity_tick(&self, host: &mut dyn ServerHost, event: &mut BlockEntityTickEvent<'_>) {
        if event.entity.items.len() < SLOTS { event.entity.items.resize(SLOTS, None); }
        let level = basin_level(host, event.pos);
        let heat = level.map_or(0, |level| heat_level(host, level, event.pos));
        let speed = level.map_or(0.0, |level| mixer_speed(host, level, event.pos));
        let Some((recipe, used, duration)) = (speed != 0.0).then(|| recipe_for(host, &event.entity.items, heat)).flatten() else {
            event.entity.nbt.insert("ProcessingTime".into(), Tag::Float(0.0f32.to_bits()));
            return;
        };
        let progress = float(&event.entity.nbt, "ProcessingTime");
        let next = progress + speed.abs().max(1.0);
        if next < duration as f32 {
            event.entity.nbt.insert("ProcessingTime".into(), Tag::Float(next.to_bits()));
            return;
        }
        let Some(mut planned) = output_plan(host, level, &recipe, &event.entity.items) else {
            event.entity.nbt.insert("ProcessingTime".into(), Tag::Float((duration as f32).to_bits()));
            return;
        };
        for (index, count) in used.into_iter().enumerate() {
            if count == 0 { continue; }
            planned[index] = event.entity.items[index].as_ref().and_then(|stack| stack.clone().shrink(count));
        }
        event.entity.items = planned;
        event.entity.nbt.insert("ProcessingTime".into(), Tag::Float(0.0f32.to_bits()));
    }
}
