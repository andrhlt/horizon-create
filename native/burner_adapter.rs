//! Typed Blaze Burner fuel state, heat output and hand fueling.

use mod_api::{
    BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent, BlockPart,
    Compound, Host, HostTransaction, InteractionResult, ItemPlace,
    ItemResource, ItemStack, ModContainer, Registrar, ServerHost, Tag, UseItemOnEvent,
};

const BURNER: &str = "create:blaze_burner";
const LIT_BURNER: &str = "create:lit_blaze_burner";
const CAKE: &str = "create:blaze_cake";
const SLOTS: usize = 2;
const INPUT: usize = 0;
const OUTPUT: usize = 1;
const MAX_FUEL: i32 = 10_000;
const REFUEL_THRESHOLD: i32 = 500;

#[derive(Clone, Copy, Default)]
pub struct BurnerPart;

pub fn register(registrar: &mut dyn Registrar) {
    let kind = registrar.block_entity_type(BURNER).blocks(&[BURNER, LIT_BURNER]).build();
    registrar.block_entity_part(&kind, BurnerPart).unwrap();
    for block in [BURNER, LIT_BURNER] {
        let key = registrar.block_key(block);
        registrar.block_container(&key, container());
    }
    let _ = registrar.item_key(CAKE);
    let _ = registrar.item_key("minecraft:bucket");
}

fn container() -> ModContainer {
    ModContainer {
        slots: SLOTS,
        faces: std::array::from_fn(|_| vec![INPUT, OUTPUT]),
        inputs: vec![INPUT],
        outputs: vec![OUTPUT],
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

fn state(kind: i32, remaining: i32) -> &'static str {
    match kind {
        2 => "seething",
        1 if remaining >= 125 => "kindled",
        1 if remaining > 0 => "fading",
        _ => "smouldering",
    }
}

fn fuel(host: &dyn Host, stack: &ItemStack) -> Option<(i32, i32)> {
    let id = mod_api::Identifier::parse(CAKE).ok()?;
    if host.item_key(&id) == Some(stack.item()) {
        return Some((2, 3200));
    }
    let time = host.item_burn_time(stack.item())?.max(0);
    (time > 0).then_some((1, time.min(MAX_FUEL)))
}

fn offer(kind: i32, remaining: i32, offered: (i32, i32)) -> Option<(i32, i32)> {
    let (next_kind, mut time) = offered;
    if next_kind < kind { return None; }
    if next_kind == kind {
        if remaining > REFUEL_THRESHOLD { return None; }
        time = time.saturating_add(remaining);
    }
    Some((next_kind, time.min(MAX_FUEL)))
}

fn write_fuel(entity: &mut Compound, kind: i32, remaining: i32) {
    entity.insert("fuelLevel".into(), Tag::Int(kind));
    entity.insert("burnTimeRemaining".into(), Tag::Int(remaining));
}

fn consume_fuel_slot(host: &dyn Host, items: &mut Vec<Option<ItemStack>>, kind: i32, remaining: i32) -> Option<(i32, i32)> {
    let stack = items.get(INPUT)?.as_ref()?.clone();
    let offered = fuel(host, &stack)?;
    let (next_kind, next_remaining) = offer(kind, remaining, offered)?;
    let remainder = host.item_crafting_remainder(&stack);
    let next_input = stack.clone().shrink(1);
    if let Some(remainder) = remainder {
        if next_input.is_none() {
            items[INPUT] = Some(remainder);
        } else if let Some(output) = items.get(OUTPUT).and_then(Option::as_ref) {
            if output.item() != remainder.item() || output.count() >= host.max_stack_size(remainder.item()).unwrap_or(64) {
                return None;
            }
            let mut output = output.clone();
            let _ = output.grow(1);
            items[OUTPUT] = Some(output);
            items[INPUT] = next_input;
        } else {
            items[OUTPUT] = Some(remainder);
            items[INPUT] = next_input;
        }
    } else {
        items[INPUT] = next_input;
    }
    Some((next_kind, next_remaining))
}

#[mod_api::horizon_part]
impl BlockPart for BurnerPart {
    fn use_item_on(&self, host: &mut dyn ServerHost, event: &mut UseItemOnEvent<'_>) -> Option<InteractionResult> {
        let burner_key = host.block_key(BURNER)?;
        if event.state.block() != burner_key && host.block_key(LIT_BURNER) != Some(event.state.block()) {
            return None;
        }
        let click = event.click;
        let player = host.player(click.player)?;
        let level = player.level(host)?;
        let place = ItemPlace::PlayerHand { player: player.uuid(), hand: click.hand };
        let stack = place.stack(host)?;
        let offered = fuel(host, &stack)?;
        let entity = host.block_entity_identity(level, click.pos)?;
        let mut data = entity.data(host)?;
        let kind = int(&data, "fuelLevel");
        let remaining = int(&data, "burnTimeRemaining");
        let (kind, remaining) = offer(kind, remaining, offered)?;
        let mut updated = data.clone();
        write_fuel(&mut updated, kind, remaining);
        let accepted = host.transaction(|host, tx| {
            let remainder = host.item_crafting_remainder(&stack);
            let moved = if let Some(remainder) = remainder {
                place.exchange(host, tx, &ItemResource::of(&remainder), 1)
            } else {
                place.extract(host, tx, &ItemResource::of(&stack), 1)
            };
            if moved != 1 || !entity.merge_data(host, updated).is_ok_and(|changed| changed) { return Err(()); }
            Ok(())
        });
        if accepted.is_err() { return None; }
        let _ = host.set_block_property_with(click.pos, "blaze", state(kind, remaining), 2);
        Some(InteractionResult::Success)
    }
}

#[mod_api::horizon_part]
impl BlockEntityPart for BurnerPart {
    fn block_entity_ticks(&self, _: &dyn Host, event: &mut BlockEntityTicksEvent<'_>) { event.ticks = true; }

    fn block_entity_tick(&self, host: &mut dyn ServerHost, event: &mut BlockEntityTickEvent<'_>) {
        if event.entity.items.len() < SLOTS { event.entity.items.resize(SLOTS, None); }
        let mut kind = int(&event.entity.nbt, "fuelLevel");
        let current = int(&event.entity.nbt, "burnTimeRemaining");
        let mut remaining = current.saturating_sub(1).max(0);
        if remaining == 0 && kind == 2 {
            kind = 1;
            remaining = MAX_FUEL / 2;
        } else if remaining == 0 {
            kind = 0;
        }
        if remaining == 0 {
            if event.entity.items.get(INPUT).and_then(Option::as_ref).is_none() {
                if current != 0 || int(&event.entity.nbt, "fuelLevel") != 0 {
                    write_fuel(&mut event.entity.nbt, 0, 0);
                }
                let _ = host.set_block_property_with(event.pos, "blaze", state(0, 0), 2);
                return;
            }
            let Some((next_kind, next_time)) = consume_fuel_slot(host, &mut event.entity.items, kind, remaining) else { return };
            kind = next_kind;
            remaining = next_time;
        }
        write_fuel(&mut event.entity.nbt, kind, remaining);
        let _ = host.set_block_property_with(event.pos, "blaze", state(kind, remaining), 2);
    }
}
