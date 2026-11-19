use horizon_world::nbt::{Compound, Tag};

use crate::items::ItemStack;

use super::Game;
use super::create_depot::compound;
use super::create_machines::int;

const RUNTIME: &str = "ScheduleRuntime";
const CARGO_IDLE: &str = "CargoIdleTicks";
const TRANSIT: i32 = 1;
const AT_DESTINATION: i32 = 2;

pub(super) enum Instruction {
    Destination(String),
    InTransit,
}

fn list<'a>(data: &'a Compound, key: &str) -> Option<&'a [Tag]> {
    match data.get(&key.into())? {
        Tag::List(list) => Some(list),
        _ => None,
    }
}

fn text<'a>(data: &'a Compound, key: &str) -> Option<&'a horizon_world::nbt::JavaString> {
    match data.get(&key.into())? {
        Tag::String(value) => Some(value),
        _ => None,
    }
}

fn runtime(data: &mut Compound) -> &mut Compound {
    if !matches!(data.get(&RUNTIME.into()), Some(Tag::Compound(_))) {
        data.insert(RUNTIME.into(), Tag::Compound(Compound::new()));
    }
    match data.get_mut(&RUNTIME.into()) {
        Some(Tag::Compound(state)) => state,
        _ => unreachable!(),
    }
}

pub(super) fn depart(data: &mut Compound) {
    runtime(data).insert("Stage".into(), Tag::Int(TRANSIT));
}

pub(super) fn arrive(data: &mut Compound) {
    let state = runtime(data);
    state.insert("Stage".into(), Tag::Int(AT_DESTINATION));
    state.remove(&"Wait".into());
    data.remove(&CARGO_IDLE.into());
}

pub(super) fn retry(data: &mut Compound) {
    let state = runtime(data);
    state.remove(&"Stage".into());
    state.insert("Cooldown".into(), Tag::Int(40));
}

pub(super) fn pause_for_controls(data: &mut Compound) {
    if !data.contains_key(&"Schedule".into()) {
        return;
    }
    data.insert("SchedulePaused".into(), Tag::Byte(1));
    if compound(data, RUNTIME).and_then(|state| int(state, "Stage")) == Some(TRANSIT) {
        runtime(data).remove(&"Stage".into());
        data.remove(&"ApproachStation".into());
        data.remove(&"ApproachDistance".into());
        data.remove(&"ApproachBackwards".into());
    }
}

fn mounted_blocks<'a>(game: &'a Game<'_>, train: u32) -> Option<&'a [Tag]> {
    let Tag::List(blocks) = game.persist.raw.get(&train)?.get("CreateTrain")?.get("Blocks")? else {
        return None;
    };
    Some(blocks)
}

fn mounted_item_count(game: &Game<'_>, train: u32, data: &Compound) -> Option<i32> {
    let blocks = mounted_blocks(game, train)?;
    let filter = compound(data, "Item");
    let stacks = int(data, "Measure") == Some(1);
    let items = game.items();
    let mut total = 0_i32;
    for block in blocks {
        let Tag::Compound(block) = block else { continue; };
        let Some((storage, _)) = super::create_train_portable_items::cargo_storage(block) else {
            continue;
        };
        let stored = list(storage, "Items").unwrap_or_default();
        for item in stored {
            let Tag::Compound(item) = item else { continue; };
            let Some(stack) = ItemStack::from_nbt(item) else { continue; };
            if filter.is_some_and(|filter| !super::create_item_filters::matches(items, filter, &stack, false)) {
                continue;
            }
            let stack_count = stack.count as i32;
            let quantity = if stacks {
                let max = stack.data().and_then(|data| data.other("minecraft:max_stack_size"))
                    .and_then(|tag| match tag { Tag::Int(value) => Some(*value), _ => None })
                    .unwrap_or_else(|| game.native_max_stack_size(&stack.item).unwrap_or(64) as i32);
                i32::from(stack_count == max)
            } else {
                stack_count
            };
            total = total.saturating_add(quantity);
        }
    }
    Some(total)
}

fn mounted_tank_amount(game: &Game<'_>, train: u32, data: &Compound) -> Option<i32> {
    let blocks = mounted_blocks(game, train)?;
    let filter = compound(data, "Bucket").filter(|filter| !filter.is_empty());
    let requested = filter.and_then(ItemStack::from_nbt)
        .and_then(|stack| super::create_fluids::liquid_from_stack(&stack, 1000));
    let mut total = None;
    for block in blocks {
        let Tag::Compound(block) = block else { continue; };
        let Some(name) = compound(block, "BlockState").and_then(|state| text(state, "Name")) else {
            continue;
        };
        if name.to_string_lossy() != super::create_fluid_tank::TANK {
            continue;
        }
        let Some(tank) = compound(block, "Entity") else { continue; };
        if tank.contains_key(&"Controller".into()) {
            continue;
        }
        let amount: &mut i32 = total.get_or_insert(0);
        let fluid = compound(tank, "TankContent").and_then(|storage| compound(storage, "Fluid"))
            .and_then(super::create_fluids::read_fluid);
        if let Some(fluid) = fluid
            && (filter.is_none() || requested.as_ref().is_some_and(|sample| sample.same_variant(&fluid)))
        {
            *amount = amount.saturating_add(fluid.amount);
        }
    }
    total
}

fn wait_duration(data: &Compound) -> i32 {
    let unit = [1, 20, 1200][int(data, "TimeUnit").unwrap_or(0).clamp(0, 2) as usize];
    int(data, "Value").unwrap_or(0).saturating_mul(unit)
}

fn condition_complete(
    game: &mut Game<'_>,
    train: u32,
    condition: &Tag,
    station: Option<[i32; 3]>,
    elapsed: &mut i32,
    cargo_idle_ticks: i32,
) -> bool {
    let Tag::Compound(condition) = condition else {
        return false;
    };
    let Some(id) = text(condition, "Id") else {
        return false;
    };
    match id.to_string_lossy().as_str() {
        "create:delay" => {
            let Some(data) = compound(condition, "Data") else {
                return false;
            };
            let duration = wait_duration(data);
            if *elapsed >= duration {
                return true;
            }
            *elapsed += 1;
            false
        }
        "create:idle" => compound(condition, "Data")
            .is_some_and(|data| cargo_idle_ticks > wait_duration(data)),
        kind @ ("create:item_threshold" | "create:fluid_threshold") => {
            let Some(data) = compound(condition, "Data") else {
                return false;
            };
            let target = text(data, "Threshold")
                .and_then(|threshold| threshold.to_string_lossy().parse::<i32>().ok())
                .unwrap_or(0);
            let (current, target) = if kind == "create:fluid_threshold" {
                (mounted_tank_amount(game, train, data), target.wrapping_mul(1000))
            } else {
                (mounted_item_count(game, train, data), target)
            };
            let Some(current) = current else {
                return false;
            };
            match int(data, "Operator").unwrap_or(0) {
                0 => current > target,
                1 => current < target,
                2 => current == target,
                _ => false,
            }
        }
        "create:player_count" => {
            let Some(data) = compound(condition, "Data") else {
                return false;
            };
            let target = int(data, "Count").unwrap_or_default();
            let present = super::create_elevator_seats::train_player_count(game, train);
            if int(data, "Exact").unwrap_or_default() != 0 {
                present >= target
            } else {
                present == target
            }
        }
        "create:unloaded" => station.is_some_and(|[x, _, z]| !game.entity_ticking_area()(x, z)),
        "create:powered" => station.is_some_and(|pos| {
            game.native_block(pos) == super::create_station::STATION
                && game.native_neighbor_signal(game.native_dimension(), pos) > 0
        }),
        "create:redstone_link" => {
            let data = compound(condition, "Data");
            let Some(frequency) = data.and_then(|data| list(data, "Frequency"))
                .or_else(|| list(condition, "Frequency"))
            else {
                return false;
            };
            let inverted = data.and_then(|data| int(data, "Inverted")) == Some(1);
            super::create_redstone_link::schedule_powered(game, frequency) != inverted
        }
        "create:time_of_day" => {
            let Some(data) = compound(condition, "Data") else {
                return false;
            };
            let hour = int(data, "Hour").unwrap_or(0);
            let minute = int(data, "Minute").unwrap_or(0);
            let rotation = [24000, 12000, 6000, 4000, 3000, 2000, 1000, 750, 500, 250]
                .get(int(data, "Rotation").unwrap_or(0) as usize)
                .copied()
                .unwrap_or(24000);
            let target = (i64::from((hour + 18) % 24) * 1000
                + (minute as f32 / 60.0 * 1000.0).ceil() as i64)
                % rotation;
            let difference = game.native_day_time() % rotation - target;
            (0..=40).contains(&difference)
        }
        _ => false,
    }
}

fn wait_for_entry(
    game: &mut Game<'_>,
    train: u32,
    entry: &Compound,
    state: &mut Compound,
    index: i32,
    station: Option<[i32; 3]>,
    cargo_idle_ticks: i32,
) -> bool {
    let Some(groups) = list(entry, "Conditions") else {
        return false;
    };
    let previous = match state.get(&"Wait".into()) {
        Some(Tag::IntArray(progress)) if progress.len() == groups.len() * 2 => progress.clone(),
        _ => vec![0; groups.len() * 2],
    };
    let mut progress = previous;
    for (group, pair) in groups.iter().zip(progress.chunks_exact_mut(2)) {
        let Tag::List(conditions) = group else {
            continue;
        };
        let Some(condition) = conditions.get(pair[0] as usize) else {
            state.insert("Entry".into(), Tag::Int(index + 1));
            state.remove(&"Stage".into());
            return false;
        };
        if condition_complete(game, train, condition, station, &mut pair[1], cargo_idle_ticks) {
            pair[0] += 1;
            pair[1] = 0;
        }
    }
    state.insert("Wait".into(), Tag::IntArray(progress));
    true
}

pub(super) fn tick(
    game: &mut Game<'_>,
    train: u32,
    data: &mut Compound,
    station: Option<[i32; 3]>,
) -> Option<Instruction> {
    if int(data, "SchedulePaused") == Some(1) {
        return None;
    }
    let schedule = compound(data, "Schedule")?;
    let entries = list(schedule, "Entries")?;
    let stored = int(schedule, "Progress").unwrap_or(0);
    let state = compound(data, RUNTIME);
    let index = state
        .and_then(|state| int(state, "Entry"))
        .unwrap_or_else(|| stored.clamp(0, entries.len().saturating_sub(1) as i32));
    let Some(Tag::Compound(entry)) = entries.get(index as usize) else {
        let cyclic = int(schedule, "Cyclic") == Some(1);
        runtime(data).insert("Entry".into(), Tag::Int(0));
        if !cyclic {
            data.insert("ScheduleCompleted".into(), Tag::Byte(1));
            data.insert("SchedulePaused".into(), Tag::Byte(1));
        }
        return None;
    };
    let stage = state.and_then(|state| int(state, "Stage")).unwrap_or(0);
    if stage == TRANSIT {
        return Some(Instruction::InTransit);
    }
    if let Some(ticks) = state
        .and_then(|state| int(state, "Cooldown"))
        .filter(|ticks| *ticks > 0)
    {
        runtime(data).insert("Cooldown".into(), Tag::Int(ticks - 1));
        return None;
    }
    if stage == AT_DESTINATION {
        let mut state = state.cloned().unwrap_or_default();
        let cargo_idle_ticks = int(data, CARGO_IDLE).unwrap_or(0);
        if wait_for_entry(game, train, entry, &mut state, index, station, cargo_idle_ticks) {
            data.insert(CARGO_IDLE.into(), Tag::Int(cargo_idle_ticks.wrapping_add(1)));
        }
        data.insert(RUNTIME.into(), Tag::Compound(state));
        return None;
    }
    let instruction = compound(entry, "Instruction")?;
    let action = text(instruction, "Id")?.to_string_lossy();
    let parameters = compound(instruction, "Data")?;
    match action.as_str() {
        "create:destination" => {
            let destination = text(parameters, "Text")?.to_string_lossy();
            runtime(data).insert("Entry".into(), Tag::Int(index));
            Some(Instruction::Destination(destination))
        }
        "create:rename" => {
            let title = text(parameters, "Text")
                .cloned()
                .unwrap_or_else(|| "".into());
            let state = runtime(data);
            state.insert("Title".into(), Tag::String(title));
            state.insert("Entry".into(), Tag::Int(index + 1));
            None
        }
        "create:throttle" => {
            let throttle = f64::from(int(parameters, "Value").unwrap_or(0) as f32 / 100.0);
            data.insert("Throttle".into(), Tag::Double(throttle.to_bits()));
            runtime(data).insert("Entry".into(), Tag::Int(index + 1));
            None
        }
        _ => None,
    }
}

pub(super) fn matching_name(filter: &str, name: &str) -> bool {
    let Some((first, rest)) = filter.split_once('*') else {
        return filter == name;
    };
    let Some(name) = name.strip_prefix(first) else {
        return false;
    };
    let (middle, last) = rest.rsplit_once('*').unwrap_or(("", rest));
    let Some(mut name) = name.strip_suffix(last) else {
        return false;
    };
    for part in middle.split('*') {
        let Some((_, rest)) = name.split_once(part) else {
            return false;
        };
        name = rest;
    }
    true
}
