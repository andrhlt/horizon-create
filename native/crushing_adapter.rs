//! Crushing Wheel controller inventory and recipe endpoint.

use mod_api::{
    BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent, BlockPart, Compound, Host,
    ItemStack, ModContainer, RandomSource, Registrar, ServerHost, Tag,
};

const CONTROLLER: &str = "create:crushing_wheel_controller";
const SLOT_COUNT: usize = 16;
const INPUT: usize = 0;

#[derive(Clone, Copy, Default)]
pub struct CrushingPart;

pub fn register(registrar: &mut dyn Registrar) {
    let kind = registrar.block_entity_type(CONTROLLER).blocks(&[CONTROLLER]).build();
    registrar.block_entity_part(&kind, CrushingPart).unwrap();
    let key = registrar.block_key(CONTROLLER);
    registrar.block_container(&key, container());
}

fn container() -> ModContainer {
    ModContainer {
        slots: SLOT_COUNT,
        faces: std::array::from_fn(|_| (0..SLOT_COUNT).collect()),
        inputs: vec![INPUT],
        outputs: (INPUT + 1..SLOT_COUNT).collect(),
        menu: None,
    }
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
        Some(Tag::Double(value)) => f64::from_bits(*value) as f32,
        _ => 0.0,
    }
}

fn recipe_for(host: &dyn Host, input: &ItemStack) -> Option<(i32, mod_api::Recipe)> {
    host.recipes_of_type("create:crushing")
        .iter()
        .chain(host.recipes_of_type("create:milling").iter())
        .find_map(|recipe| {
            let ingredient = recipe.json["ingredients"].as_array()?.first()?;
            let encoded = if ingredient.is_string() {
                ingredient.to_string()
            } else if let Some(item) = ingredient.get("item").and_then(|v| v.as_str()) {
                format!("{item:?}")
            } else if let Some(tag) = ingredient.get("tag").and_then(|v| v.as_str()) {
                format!("{:?}", format!("#{tag}"))
            } else {
                return None;
            };
            let matches = host.recipe_ingredient(&encoded).ok().flatten()?.test(host, input);
            if !matches { return None; }
            let duration = recipe.json["processing_time"].as_i64().unwrap_or(100).max(1) as i32;
            Some((duration, recipe.clone()))
        })
}

fn insert(host: &dyn Host, slots: &mut [Option<ItemStack>], mut output: ItemStack) -> bool {
    let limit = host.max_stack_size(output.item()).unwrap_or(64);
    let item = output.item();
    for stack in slots.iter_mut().flatten() {
        if stack.item() != item { continue; }
        let moved = limit.saturating_sub(stack.count()).min(output.count());
        if moved > 0 {
            let _ = stack.grow(moved);
            if moved == output.count() { return true; }
            output = output.shrink(moved).expect("partial output leaves a remainder");
        }
    }
    for slot in slots {
        if slot.is_none() { *slot = Some(output); return true; }
    }
    false
}

fn output_plan(
    host: &mut dyn ServerHost,
    recipe: &mod_api::Recipe,
    slots: &[Option<ItemStack>],
) -> Option<Vec<Option<ItemStack>>> {
    let mut shadow = slots.to_vec();
    let results = recipe.json["results"].as_array()?;
    for result in results {
        let Some(output) = host.recipe_result(&result.to_string()).ok().flatten() else { continue };
        let chance = result["chance"].as_f64().unwrap_or(1.0) as f32;
        let mut kept = 0;
        for _ in 0..output.count() {
            if chance >= 1.0 || host.levels().list_levels().first().is_some_and(|level| {
                level.with_random(host, |random| random.next_float() <= chance).unwrap_or(false)
            }) { kept += 1; }
        }
        if kept == 0 { continue; }
        let count = output.count();
        let output = if kept == count { output } else { output.shrink(count - kept)? };
        if !insert(host, &mut shadow[INPUT + 1..], output) { return None; }
    }
    Some(shadow)
}

#[mod_api::horizon_part]
impl BlockPart for CrushingPart {}

#[mod_api::horizon_part]
impl BlockEntityPart for CrushingPart {
    fn block_entity_ticks(&self, _: &dyn Host, event: &mut BlockEntityTicksEvent<'_>) { event.ticks = true; }

    fn block_entity_tick(&self, host: &mut dyn ServerHost, event: &mut BlockEntityTickEvent<'_>) {
        if event.entity.items.len() < SLOT_COUNT { event.entity.items.resize(SLOT_COUNT, None); }
        let Some(input) = event.entity.items[INPUT].as_ref() else { return };
        let Some((duration, recipe)) = recipe_for(host, input) else {
            event.entity.nbt.insert("ProcessingTime".into(), Tag::Float(0.0f32.to_bits()));
            return;
        };
        let speed = float(&event.entity.nbt, "Speed");
        if speed == 0.0 { return; }
        let progress = float(&event.entity.nbt, "ProcessingTime");
        let next = progress + speed.abs().max(1.0);
        if next < duration as f32 {
            event.entity.nbt.insert("ProcessingTime".into(), Tag::Float(next.to_bits()));
            return;
        }
        let Some(mut planned) = output_plan(host, &recipe, &event.entity.items) else {
            event.entity.nbt.insert("ProcessingTime".into(), Tag::Float((duration as f32).to_bits()));
            return;
        };
        planned[INPUT] = input.clone().shrink(1);
        event.entity.items = planned;
        event.entity.nbt.insert("ProcessingTime".into(), Tag::Float(0.0f32.to_bits()));
    }
}

#[cfg(test)]
mod tests {
    use super::container;
    #[test]
    fn crusher_inventory_exposes_one_input_and_fifteen_output_slots() {
        let slots = container();
        assert_eq!(slots.slots, 16);
        assert_eq!(slots.inputs, vec![0]);
        assert_eq!(slots.outputs, (1..16).collect::<Vec<_>>());
    }
}
