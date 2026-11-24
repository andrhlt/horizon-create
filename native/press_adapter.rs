//! Typed Mechanical Press endpoint for dropped-item processing.
//!
//! The cycle transition is shared with the legacy adapter. Recipe lookup and
//! entity inventory changes stay on the typed Horizon boundary.

use std::collections::VecDeque;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Mutex, OnceLock};

use mod_api::{
    BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent, BlockPart, Compound, Host,
    ItemEntityRef, ItemStack, LevelRef, Registrar, ServerHost, Tag, Text,
};

use crate::press_processing::{self, CYCLE};

const SCAN_TICKS: i32 = 10;
const INPUT_MIN_Y: f64 = -1.125;
const INPUT_MAX_Y: f64 = 0.125;
const PRESS_OUTPUT_TASK_PREFIX: u64 = 0x5052_4553_5300_0000;
static NEXT_OUTPUT_TASK: AtomicU64 = AtomicU64::new(PRESS_OUTPUT_TASK_PREFIX);

struct PendingOutput {
    token: u64,
    dimension: String,
    position: [f64; 3],
    item: ItemEntityRef,
    expected: ItemStack,
    output: ItemStack,
}
static PENDING_OUTPUTS: OnceLock<Mutex<VecDeque<PendingOutput>>> = OnceLock::new();
fn pending_outputs() -> &'static Mutex<VecDeque<PendingOutput>> {
    PENDING_OUTPUTS.get_or_init(|| Mutex::new(VecDeque::new()))
}

#[derive(Clone, Copy, Default)]
pub struct PressPart;

pub fn register(registrar: &mut dyn Registrar) {
    for item in [
        "create:iron_sheet",
        "create:golden_sheet",
        "create:copper_sheet",
        "create:brass_sheet",
    ] {
        let _ = registrar.item_key(item);
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

fn pressing_result(host: &mut dyn ServerHost, input: &ItemStack) -> Option<ItemStack> {
    // These are the four Create pressing recipes used by the survival metal
    // progression. Their c:ingots tags are resolved against the actual input
    // keys here because the Horizon recipe view omits unregistered optional
    // tag providers in some prepared 26.3 packs.
    const RECIPES: [(&str, &str); 4] = [
        ("minecraft:iron_ingot", "create:iron_sheet"),
        ("minecraft:gold_ingot", "create:golden_sheet"),
        ("minecraft:copper_ingot", "create:copper_sheet"),
        ("create:brass_ingot", "create:brass_sheet"),
    ];
    RECIPES.iter().find_map(|(ingredient, result)| {
        let ingredient = mod_api::Identifier::parse(ingredient).ok()?;
        if host.item_key(&ingredient)? != input.item() { return None; }
        let result = mod_api::Identifier::parse(result).ok()?;
        ItemStack::new(host.item_key(&result)?, 1)
    })
}

fn level_for(host: &dyn ServerHost, pos: [i32; 3]) -> Option<LevelRef> {
    host.levels()
        .list_levels()
        .into_iter()
        .find(|level| level.block(host, pos).is_some())
}

fn candidate_items(
    host: &mut dyn ServerHost,
    level: LevelRef,
    press: [i32; 3],
) -> Vec<(ItemEntityRef, ItemStack, [f64; 3])> {
    let min = [
        f64::from(press[0]),
        f64::from(press[1]) + INPUT_MIN_Y,
        f64::from(press[2]),
    ];
    let max = [
        f64::from(press[0] + 1),
        f64::from(press[1]) + INPUT_MAX_Y,
        f64::from(press[2] + 1),
    ];
    let entities = level.entities_in(host, min, max).unwrap_or_default();
    if std::env::var_os("CREATE_PRESS_TRACE").is_some() {
        let _ = host.messages().broadcast(Text::literal(format!("PRESS_ENTITIES count={}", entities.len())));
    }
    entities
        .into_iter()
        .filter_map(|entity| {
            let item = host.item_entity(entity)?;
            let stack = item.stack(host)?;
            let matches = pressing_result(host, &stack);
            if std::env::var_os("CREATE_PRESS_TRACE").is_some() {
                let iron_key = mod_api::Identifier::parse("minecraft:iron_ingot")
                    .ok().and_then(|id| host.item_key(&id));
                let _ = host.messages().broadcast(Text::literal(format!(
                    "PRESS_ITEM stack={} iron_key={} equal={} recipe={}",
                    stack.count(), iron_key.is_some(), iron_key == Some(stack.item()), matches.is_some(),
                )));
            }
            matches?;
            let position = entity.position(host)?;
            Some((item, stack, position))
        })
        .collect()
}

fn has_input(host: &mut dyn ServerHost, level: LevelRef, press: [i32; 3]) -> bool {
    candidate_items(host, level, press).into_iter().next().is_some()
}

fn apply_press(host: &mut dyn ServerHost, level: LevelRef, press: [i32; 3]) -> bool {
    let Some((item, input, at)) = candidate_items(host, level, press).into_iter().next() else {
        return false;
    };
    let Some(output) = pressing_result(host, &input) else {
        return false;
    };
    let Some(dimension) = level.dimension().id(host) else { return false };
    let token = NEXT_OUTPUT_TASK.fetch_add(1, Ordering::Relaxed);
    pending_outputs().lock().expect("press output queue").push_back(PendingOutput {
        token, dimension: dimension.to_string(), position: at, item,
        expected: input, output,
    });
    if host.schedule_task(0, token).is_err() {
        pending_outputs().lock().expect("press output queue").retain(|item| item.token != token);
        return false;
    }
    true
}

pub fn scheduled_task(host: &mut dyn ServerHost, event: &mut mod_api::ScheduledTaskEvent<'_>) {
    if std::env::var_os("CREATE_PRESS_TRACE").is_some() {
        let _ = host.messages().broadcast(Text::literal(format!("PRESS_TASK token={}", event.token)));
    }
    if event.token & 0xffff_ffff_ffff_0000 != PRESS_OUTPUT_TASK_PREFIX { return; }
    let request = {
        let mut pending = pending_outputs().lock().expect("press output queue");
        pending.iter().position(|item| item.token == event.token).and_then(|i| pending.remove(i))
    };
    let Some(request) = request else { return };
    let Some(level) = host.level(&request.dimension) else {
        if std::env::var_os("CREATE_PRESS_TRACE").is_some() { let _ = host.messages().broadcast(Text::literal("PRESS_TASK no-level")); }
        return;
    };
    let Some(current) = request.item.stack(host) else { return };
    if std::env::var_os("CREATE_PRESS_TRACE").is_some() {
        let _ = host.messages().broadcast(Text::literal(format!("PRESS_TASK current={} expected={}", current.count(), request.expected.count())));
    }
    if current.item() != request.expected.item() || current.count() != request.expected.count() {
        return;
    }
    let spawn = level.spawn_item(
        host, request.position[0], request.position[1], request.position[2], request.output, 10,
    );
    if std::env::var_os("CREATE_PRESS_TRACE").is_some() {
        let spawned = matches!(spawn, Ok(Some(_)));
        let _ = host.messages().broadcast(Text::literal(format!("PRESS_TASK spawn={spawned}")));
    }
    let Ok(Some(spawned)) = spawn else { return };
    if std::env::var_os("CREATE_PRESS_TRACE").is_some() {
        let id = host.item_entity(spawned).and_then(|item| item.stack(host))
            .and_then(|stack| mod_api::__private::item_key_id(stack.item()));
        let _ = host.messages().broadcast(Text::literal(format!("PRESS_TASK output-id={id:?}")));
    }
    if current.count() == 1 {
        let removed = request.item.entity().discard(host);
        if std::env::var_os("CREATE_PRESS_TRACE").is_some() {
            let _ = host.messages().broadcast(Text::literal(format!("PRESS_TASK removed={removed}")));
        }
        if !removed {
            let _ = spawned.discard(host);
        }
        return;
    }
    let Some(remainder) = current.shrink(1) else {
        let _ = spawned.discard(host);
        return;
    };
    if !request.item.set_stack(host, remainder).is_ok_and(|changed| changed) {
        let _ = spawned.discard(host);
    }
}

#[mod_api::horizon_part]
impl BlockPart for PressPart {}

#[mod_api::horizon_part]
impl BlockEntityPart for PressPart {
    fn block_entity_ticks(&self, _: &dyn Host, event: &mut BlockEntityTicksEvent<'_>) {
        event.ticks = true;
    }

    fn block_entity_tick(&self, host: &mut dyn ServerHost, event: &mut BlockEntityTickEvent<'_>) {
        let level = level_for(host, event.pos);
        let rpm = float(&event.entity.nbt, "Speed");
        let mut ticks = int(&event.entity.nbt, "Ticks");
        let running = int(&event.entity.nbt, "Running") != 0;
        let mode = int(&event.entity.nbt, "Mode");
        if std::env::var_os("CREATE_PRESS_TRACE").is_some() {
            eprintln!("PRESS_TICK pos={:?} rpm={rpm} ticks={ticks} running={running} mode={mode} scan={}", event.pos, int(&event.entity.nbt, "PressScan"));
        }

        if !running {
            let scan = int(&event.entity.nbt, "PressScan");
            if scan > 0 {
                event.entity.nbt.insert("PressScan".into(), Tag::Int(scan - 1));
                return;
            }
            event.entity.nbt.insert("PressScan".into(), Tag::Int(SCAN_TICKS));
            let Some(level) = level else { return };
            let has_input = has_input(host, level, event.pos);
            if std::env::var_os("CREATE_PRESS_TRACE").is_some() {
                let _ = host.messages().broadcast(Text::literal(format!(
                    "PRESS_SCAN recipes={} input={has_input} rpm={rpm} mode={mode}",
                    host.recipes_of_type("create:pressing").len(),
                )));
            }
            if rpm == 0.0 || mode != 0 || !has_input {
                return;
            }
            event.entity.nbt.insert("Running".into(), Tag::Byte(1));
            event.entity.nbt.insert("Ticks".into(), Tag::Int(0));
            event.entity.nbt.insert("PrevTicks".into(), Tag::Int(0));
            ticks = 0;
        }

        let advance = press_processing::advance(ticks, rpm);
        if advance.impact {
            let applied = level.is_some_and(|level| apply_press(host, level, event.pos));
            if std::env::var_os("CREATE_PRESS_TRACE").is_some() {
                let _ = host.messages().broadcast(Text::literal(format!("PRESS_IMPACT applied={applied}")));
            }
        }
        event.entity.nbt.insert("PrevTicks".into(), Tag::Int(ticks));
        event.entity.nbt.insert("Ticks".into(), Tag::Int(advance.next));
        if advance.next > CYCLE {
            event.entity.nbt.insert("Running".into(), Tag::Byte(0));
            event.entity.nbt.insert("Ticks".into(), Tag::Int(0));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn input_window_covers_the_item_surface_below_the_press() {
        assert!(INPUT_MIN_Y < -1.0);
        assert!(INPUT_MAX_Y > 0.0);
    }
}
