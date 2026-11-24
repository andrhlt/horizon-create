//! Typed 0a Fan and Nozzle production adapter.
//!
//! APP-2173 owns the kinetic graph and calls `tick_fan` with its recomputed,
//! signed speed. This module owns the terminal airflow, recipe processing and
//! Nozzle entity effects. Fan scan/timer state is kept in the Fan block entity
//! compound so ordinary saves and client updates travel through the engine's
//! existing block-entity path.

use mod_api::{
    BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent, BlockPart, BlockShapeKind,
    BlockState, Compound, Host, HostTransaction, ItemStack, LevelHost, LevelRef, RandomSource,
    Registrar, ServerHost, Tag,
};

use super::fan_airflow_math as rules;

const FAN: &str = "create:encased_fan";
const NOZZLE: &str = "create:nozzle";
const DEPOT: &str = "create:depot";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Process {
    Splashing,
    Smoking,
    Haunting,
    Blasting,
}

impl Process {
    fn id(self) -> &'static str {
        match self {
            Self::Splashing => "create:splashing",
            Self::Smoking => "create:smoking",
            Self::Haunting => "create:haunting",
            Self::Blasting => "create:blasting",
        }
    }

    fn parse(value: &str) -> Option<Self> {
        Some(match value {
            "create:splashing" => Self::Splashing,
            "create:smoking" => Self::Smoking,
            "create:haunting" => Self::Haunting,
            "create:blasting" => Self::Blasting,
            _ => return None,
        })
    }
}

#[derive(Clone, Copy)]
pub struct NozzlePart;

pub fn register(registrar: &mut dyn Registrar) {
    let nozzle = registrar
        .block_entity_type("create:nozzle")
        .blocks(&[NOZZLE])
        .build();
    registrar.block_entity_part(&nozzle, NozzlePart).unwrap();
}

fn property(host: &dyn Host, level: LevelRef, pos: [i32; 3], key: &str) -> Option<String> {
    level.block_property(host, pos, key)
}

fn facing(host: &dyn Host, level: LevelRef, pos: [i32; 3]) -> Option<[i32; 3]> {
    Some(match property(host, level, pos, "facing")?.as_str() {
        "east" => [1, 0, 0],
        "west" => [-1, 0, 0],
        "up" => [0, 1, 0],
        "down" => [0, -1, 0],
        "south" => [0, 0, 1],
        "north" => [0, 0, -1],
        _ => return None,
    })
}

fn offset(pos: [i32; 3], direction: [i32; 3], distance: i32) -> [i32; 3] {
    std::array::from_fn(|axis| pos[axis] + direction[axis] * distance)
}

fn block_id(host: &dyn Host, level: LevelRef, pos: [i32; 3]) -> Option<String> {
    level.block(host, pos).map(|key| key.id(host))
}

fn process_at(host: &dyn Host, level: LevelRef, pos: [i32; 3]) -> Option<Process> {
    match block_id(host, level, pos)?.as_str() {
        "minecraft:water" | "minecraft:bubble_column" => Some(Process::Splashing),
        "minecraft:lava" => Some(Process::Blasting),
        "minecraft:fire" => Some(Process::Smoking),
        "minecraft:soul_fire" => Some(Process::Haunting),
        "minecraft:campfire" if property(host, level, pos, "lit").as_deref() == Some("true") => {
            Some(Process::Smoking)
        }
        "minecraft:soul_campfire"
            if property(host, level, pos, "lit").as_deref() == Some("true") =>
        {
            Some(Process::Haunting)
        }
        _ if property(host, level, pos, "waterlogged").as_deref() == Some("true") => {
            Some(Process::Splashing)
        }
        _ => None,
    }
}

fn blocked(host: &dyn Host, level: LevelRef, source: [i32; 3], along: [i32; 3], max: f32) -> f32 {
    let steps = max.ceil() as i32;
    for distance in 0..steps {
        let pos = offset(source, along, distance + 1);
        let Some(state) = level.block_state(host, pos) else {
            return distance as f32;
        };
        let block = state.block();
        let id = block.id(host);
        if id == "create:copycat_panel"
            || host.block_in_tag(block, "create:fan_transparent") == Some(true)
        {
            continue;
        }
        let boxes = level
            .block_shape(host, state, pos, BlockShapeKind::Collision)
            .unwrap_or_default();
        if boxes.iter().any(|bounds| {
            bounds[0] <= 0.0
                && bounds[1] <= 0.0
                && bounds[2] <= 0.0
                && bounds[3] >= 1.0
                && bounds[4] >= 1.0
                && bounds[5] >= 1.0
        }) {
            return distance as f32;
        }
        let axis = along.iter().position(|step| *step != 0).unwrap_or(1);
        let cross_a = (axis + 1) % 3;
        let cross_b = (axis + 2) % 3;
        let forward = along[axis] > 0;
        let mut depth = 0.0_f64;
        let mut open_ray = false;
        for (a, b) in [
            (0.25, 0.25),
            (0.25, 0.75),
            (0.5, 0.5),
            (0.75, 0.25),
            (0.75, 0.75),
        ] {
            let nearest = boxes
                .iter()
                .filter(|bounds| {
                    a >= bounds[cross_a]
                        && a < bounds[cross_a + 3]
                        && b >= bounds[cross_b]
                        && b < bounds[cross_b + 3]
                })
                .map(|bounds| {
                    if forward {
                        bounds[axis]
                    } else {
                        1.0 - bounds[axis + 3]
                    }
                })
                .fold(f64::INFINITY, f64::min);
            if nearest.is_infinite() {
                open_ray = true;
                break;
            }
            depth = depth.max(nearest);
        }
        if !open_ray {
            return (distance as f32 + depth as f32 + 1.0 / 32.0).min(max);
        }
    }
    max
}

fn recipe_outputs(
    host: &dyn ServerHost,
    level: LevelRef,
    process: Process,
    input: &ItemStack,
) -> Option<Vec<(ItemStack, f32)>> {
    let mut outputs = Vec::new();
    match process {
        Process::Smoking => {
            let recipe_type_id = mod_api::Identifier::parse("minecraft:smoking").ok()?;
            let matched = level
                .recipe_for(
                    host,
                    &recipe_type_id,
                    &mod_api::RecipeInput::Single(input.clone()),
                )
                .ok()??;
            return Some(vec![(matched.output, 1.0)]);
        }
        Process::Blasting => {
            let lookup = |recipe_type: &str| {
                let id = mod_api::Identifier::parse(recipe_type).ok()?;
                level
                    .recipe_for(host, &id, &mod_api::RecipeInput::Single(input.clone()))
                    .ok()?
            };
            let smelt = lookup("minecraft:smelting").or_else(|| lookup("minecraft:blasting"));
            let smoke = lookup("minecraft:smoking");
            if let Some(smelt) = smelt.filter(|smelt| {
                smoke
                    .as_ref()
                    .is_none_or(|smoke| smoke.output.item() != smelt.output.item())
            }) {
                return Some(vec![(smelt.output, 1.0)]);
            }
            let fire_resistant = mod_api::Identifier::parse("minecraft:fire_resistant")
                .ok()
                .and_then(|id| host.tags().key(&id))
                .and_then(|tag| host.tags().is_in_tag(input.item(), tag))
                == Some(true);
            return (!fire_resistant).then_some(Vec::new());
        }
        Process::Splashing | Process::Haunting => {
            let recipes = host.recipes_of_type(process.id());
            let recipe = recipes
                .iter()
                .find(|recipe| recipe_ingredient_matches(host, recipe, input))?;
            let results = recipe.json["results"].as_array()?;
            for result in results {
                let output = host.recipe_result(&result.to_string()).ok().flatten()?;
                outputs.push((output, result["chance"].as_f64().unwrap_or(1.0) as f32));
            }
        }
    }
    (!outputs.is_empty()).then_some(outputs)
}

fn recipe_ingredient_matches(host: &dyn Host, recipe: &mod_api::Recipe, input: &ItemStack) -> bool {
    // Create's custom recipe types publish vanilla ingredient objects in their
    // JSON (`{"item":"..."}` / `{"tag":"..."}`). The typed SDK helper
    // accepts the engine's normalized string/array form instead.
    let Some(json) = recipe.json["ingredients"].as_array().and_then(|v| v.first()) else {
        return false;
    };
    let normalized = if let Some(item) = json["item"].as_str() {
        format!("{item:?}")
    } else if let Some(tag) = json["tag"].as_str() {
        format!("{:?}", format!("#{tag}"))
    } else {
        json.to_string()
    };
    host.recipe_ingredient(&normalized)
        .ok()
        .flatten()
        .is_some_and(|ingredient| ingredient.test(host, input))
}

fn outputs_for_kind(
    host: &mut dyn ServerHost,
    level: LevelRef,
    process: Process,
    input: &ItemStack,
) -> Option<Vec<(ItemStack, f32)>> {
    if matches!(process, Process::Splashing | Process::Haunting) {
        return recipe_outputs(host, level, process, input);
    }
    let kind = mod_api::Identifier::parse(match process {
        Process::Smoking => "minecraft:smoking",
        Process::Blasting => "minecraft:blasting",
        _ => unreachable!(),
    })
    .ok()?;
    let result = level
        .recipe_for(host, &kind, &mod_api::RecipeInput::Single(input.clone()))
        .ok()??;
    Some(vec![(result.output, 1.0)])
}

fn insert_output(host: &dyn Host, slots: &mut [Option<ItemStack>], mut output: ItemStack) -> bool {
    let max = host.max_stack_size(output.item()).unwrap_or(64);
    for stack in slots.iter_mut().flatten() {
        if stack.item() == output.item() {
            let count = stack.count();
            let moved = max.saturating_sub(count).min(output.count());
            if moved != 0 {
                let _ = stack.grow(moved);
                if moved == output.count() {
                    return true;
                }
                output = output.shrink(moved).expect("remainder is nonempty");
            }
        }
    }
    if let Some(slot) = slots.iter_mut().find(|slot| slot.is_none()) {
        *slot = Some(output);
        true
    } else {
        false
    }
}

fn process_depot(host: &mut dyn ServerHost, level: LevelRef, pos: [i32; 3], process: Process) {
    let depot_pos = pos;
    if block_id(host, level, depot_pos).as_deref() != Some(DEPOT) {
        return;
    }
    let Some(entity) = host.block_entity_identity(level, depot_pos) else {
        return;
    };
    let Some(mut depot_data) = entity.data(host) else {
        return;
    };
    let Ok(Some(input)) = entity.item_slot(host, 0) else {
        clear_processing(&mut depot_data);
        let _ = entity.merge_data(host, depot_data);
        return;
    };
    let input_id = input.item().id(host);
    let same = string(&depot_data, "FanProcessingItem").as_deref() == Some(input_id.as_str())
        && string(&depot_data, "FanProcessingType").as_deref() == Some(process.id());
    let timer = int(&depot_data, "FanProcessingTime").unwrap_or(-1);
    if !same {
        if outputs_for_kind(host, level, process, &input).is_some() {
            depot_data.insert(
                "FanProcessingItem".into(),
                Tag::String(input_id.as_str().into()),
            );
            depot_data.insert("FanProcessingType".into(), Tag::String(process.id().into()));
            depot_data.insert(
                "FanProcessingTime".into(),
                Tag::Int(rules::processing_duration(input.count())),
            );
        } else {
            clear_processing(&mut depot_data);
        }
        let _ = entity.merge_data(host, depot_data);
        return;
    }
    if timer < 0 {
        return;
    }
    if timer > 0 {
        depot_data.insert("FanProcessingTime".into(), Tag::Int(timer - 1));
        let _ = entity.merge_data(host, depot_data);
        return;
    }
    let Some(mut results) = outputs_for_kind(host, level, process, &input) else {
        clear_processing(&mut depot_data);
        let _ = entity.merge_data(host, depot_data);
        return;
    };
    let level_ref = level;
    let mut produced = Vec::new();
    for (one, chance) in results.drain(..) {
        let mut count = 0;
        for _ in 0..input.count() {
            for _ in 0..one.count() {
                let roll = level_ref
                    .with_random(host, |random| random.next_float())
                    .unwrap_or(0.0);
                if roll <= chance {
                    count += 1;
                }
            }
        }
        let max = host.max_stack_size(one.item()).unwrap_or(64).max(1);
        let mut remaining = count;
        while remaining > 0 {
            let moved = remaining.min(max);
            if let Some(stack) = ItemStack::new(one.item(), moved) {
                produced.push(stack);
            }
            remaining -= moved;
        }
    }
    host.transaction(|host, tx| {
        let mut outputs = vec![None];
        outputs.extend((1..9).map(|slot| entity.item_slot(host, slot).ok().flatten()));
        if !produced
            .iter()
            .all(|stack| insert_output(host, &mut outputs, stack.clone()))
        {
            depot_data.insert("FanProcessingTime".into(), Tag::Int(1));
            entity.merge_data(host, depot_data.clone()).ok();
            return Ok::<_, ()>(());
        }
        for (index, stack) in outputs.into_iter().enumerate() {
            entity.set_item_slot(host, tx, index as u32, stack).ok();
        }
        clear_processing(&mut depot_data);
        entity.merge_data(host, depot_data.clone()).ok();
        Ok(())
    })
    .ok();
}

fn int(data: &Compound, key: &str) -> Option<i32> {
    match data.get(&key.into()) {
        Some(Tag::Int(value)) => Some(*value),
        Some(Tag::Short(value)) => Some(i32::from(*value)),
        Some(Tag::Byte(value)) => Some(i32::from(*value)),
        _ => None,
    }
}

fn string(data: &Compound, key: &str) -> Option<String> {
    match data.get(&key.into()) {
        Some(Tag::String(value)) => Some(value.to_string_lossy()),
        _ => None,
    }
}

fn clear_processing(data: &mut Compound) {
    for key in [
        "FanProcessingType",
        "FanProcessingTime",
        "FanProcessingItem",
    ] {
        data.remove(&key.into());
    }
}

fn fan_records(data: &Compound) -> Vec<(u128, i32, i32)> {
    let Some(Tag::LongArray(values)) = data.get(&"CreateFanAirItems".into()) else {
        return Vec::new();
    };
    values
        .chunks_exact(4)
        .map(|record| {
            (
                join_uuid(record[0], record[1]),
                record[2] as i32,
                record[3] as i32,
            )
        })
        .collect()
}

fn split_uuid(value: u128) -> (i64, i64) {
    ((value >> 64) as u64 as i64, value as u64 as i64)
}

fn join_uuid(high: i64, low: i64) -> u128 {
    (u128::from(high as u64) << 64) | u128::from(low as u64)
}

/// Called by APP-2173 after graph recompute with the node's signed effective RPM.
pub(super) fn tick_fan(
    host: &mut dyn ServerHost,
    level: LevelRef,
    pos: [i32; 3],
    data: &mut Compound,
    speed: f32,
) {
    data.insert("Speed".into(), Tag::Float(speed.to_bits()));
    let Some(along) = facing(host, level, pos) else {
        return;
    };
    if speed == 0.0 {
        data.insert("CreateFanAirItems".into(), Tag::LongArray(Vec::new()));
        return;
    }
    let direction = if rules::pushing(speed, along) {
        along
    } else {
        along.map(|n| -n)
    };
    let max_reach = rules::reach(speed);
    let distance = blocked(host, level, pos, direction, max_reach);
    if distance >= 0.25 {
        let mut min = pos.map(|n| f64::from(n) + 0.5);
        let mut max = min;
        for axis in 0..3 {
            if direction[axis] == 0 {
                min[axis] -= 0.5;
                max[axis] += 0.5;
            } else {
                min[axis] += f64::from(direction[axis]) * 0.5;
                // The collision distance ends at a block face. Entity
                // positions in the final intersected cell remain in the
                // windbox, including a centered item a fraction past that
                // face due to its own width or the preceding tick's impulse.
                max[axis] += f64::from(direction[axis]) * (f64::from(distance) + 0.5);
                if min[axis] > max[axis] {
                    std::mem::swap(&mut min[axis], &mut max[axis]);
                }
            }
        }
        let center = pos.map(|n| f64::from(n) + 0.5);
        let entities = level.entities_in(host, min, max).unwrap_or_default();
        let old = fan_records(data);
        let mut next_records = Vec::new();
        for reference in entities {
            let Some(item) = host.item_entity(reference) else {
                continue;
            };
            let Some(at) = reference.position(host) else {
                continue;
            };
            let Some(uuid) = reference.uuid(host) else {
                continue;
            };
            let radial = (0..3)
                .map(|axis| (at[axis] - center[axis]).powi(2))
                .sum::<f64>()
                .sqrt();
            let old_timer = old.iter().find(|entry| entry.0 == uuid).copied();
            let mut next_timer = old_timer.map_or(-1, |entry| entry.2);
            let mut kind_code = old_timer.map_or(0, |entry| entry.1);
            if let Some(kind) = process_at(host, level, at.map(|v| v.floor() as i32)) {
                let stack = item.stack(host);
                if let Some(stack) = stack {
                    let kind_index = process_code(kind);
                    if kind_code != kind_index {
                        if outputs_for_kind(host, level, kind, &stack).is_some() {
                            kind_code = kind_index;
                            next_timer = rules::processing_duration(stack.count());
                        }
                    } else if next_timer >= 0 {
                        next_timer -= 1;
                        if next_timer == 0 {
                            if let Some(outputs) = outputs_for_kind(host, level, kind, &stack) {
                                let mut spawned = Vec::new();
                                for (output, chance) in outputs {
                                    let count = (0..output.count() * stack.count())
                                        .filter(|_| {
                                            level
                                                .with_random(host, |rng| rng.next_float() <= chance)
                                                .unwrap_or(false)
                                        })
                                        .count()
                                        as u32;
                                    let max =
                                        host.max_stack_size(output.item()).unwrap_or(64).max(1);
                                    let mut remaining = count;
                                    while remaining > 0 {
                                        let moved = remaining.min(max);
                                        if let Some(out) = ItemStack::new(output.item(), moved) {
                                            spawned.push(out);
                                        }
                                        remaining -= moved;
                                    }
                                }
                                if let Some(first) = spawned.first().cloned() {
                                    let _ = item.set_stack(host, first);
                                    for extra in spawned.into_iter().skip(1) {
                                        let _ = level.spawn_item_with_motion(
                                            host, at[0], at[1], at[2], extra, [0.0; 3], 10,
                                        );
                                    }
                                } else {
                                    let _ = reference.discard(host);
                                }
                            }
                            next_timer = -1;
                        }
                    }
                }
            }
            if let Some(velocity) = reference.velocity(host) {
                let flow = if rules::pushing(speed, along) {
                    along
                } else {
                    along.map(|n| -n)
                };
                let new_velocity =
                    rules::fan_item_velocity(velocity, flow, speed, radial, distance);
                let _ = reference.set_velocity(host, new_velocity);
                let _ = reference.reset_fall_distance(host);
            }
            next_records.push((uuid, kind_code, next_timer));
        }
        data.insert(
            "CreateFanAirItems".into(),
            Tag::LongArray(
                next_records
                    .into_iter()
                    .flat_map(|(uuid, kind, timer)| {
                        let (high, low) = split_uuid(uuid);
                        [high, low, i64::from(kind), i64::from(timer)]
                    })
                    .collect(),
            ),
        );
    } else {
        data.insert("CreateFanAirItems".into(), Tag::IntArray(Vec::new()));
    }

    // Process a Depot occupying the first unobstructed position in the lane.
    let mut active_process = None;
    for d in 1..=distance.ceil() as i32 {
        let at = offset(pos, direction, d);
        if block_id(host, level, at).as_deref() == Some(DEPOT) {
            if let Some(kind) = active_process {
                process_depot(host, level, at, kind);
            }
            break;
        }
        if let Some(kind) = process_at(host, level, at) {
            active_process = Some(kind);
        }
    }
}

fn process_code(process: Process) -> i32 {
    match process {
        Process::Splashing => 1,
        Process::Smoking => 2,
        Process::Haunting => 3,
        Process::Blasting => 4,
    }
}

fn process_from_code(code: i32) -> Option<Process> {
    Some(match code {
        1 => Process::Splashing,
        2 => Process::Smoking,
        3 => Process::Haunting,
        4 => Process::Blasting,
        _ => return None,
    })
}

fn saved_entities(data: &Compound, key: &str) -> Vec<u128> {
    match data.get(&key.into()) {
        Some(Tag::LongArray(ids)) => ids
            .chunks_exact(2)
            .map(|pair| join_uuid(pair[0], pair[1]))
            .collect(),
        _ => Vec::new(),
    }
}

fn set_saved_entities(data: &mut Compound, key: &str, values: Vec<u128>) {
    data.insert(
        key.into(),
        Tag::LongArray(
            values
                .into_iter()
                .flat_map(|uuid| {
                    let (high, low) = split_uuid(uuid);
                    [high, low]
                })
                .collect(),
        ),
    );
}

fn nozzle_visible(host: &dyn Host, level: LevelRef, center: [f64; 3], position: [f64; 3]) -> bool {
    let toward = std::array::from_fn::<_, 3, _>(|axis| center[axis] - position[axis]);
    let largest = toward.iter().map(|value| value.abs()).fold(0.0, f64::max);
    if largest <= 0.5 {
        return true;
    }
    let edge = std::array::from_fn(|axis| center[axis] - toward[axis] * (0.5 / largest));
    level.line_of_sight(host, position, edge).unwrap_or(false)
}

impl NozzlePart {
    fn support_matches(&self, host: &dyn LevelHost, pos: [i32; 3], direction: [i32; 3]) -> bool {
        let fan_pos = offset(pos, direction.map(|n| -n), 1);
        let Some(state) = host.block_state(fan_pos) else {
            return false;
        };
        host.state_block(state) == Some(FAN)
            && host.state_string(state).is_some_and(|value| {
                value.contains(&format!("facing={}", direction_name(direction)))
            })
    }
}

fn direction_name(direction: [i32; 3]) -> &'static str {
    match direction {
        [1, 0, 0] => "east",
        [-1, 0, 0] => "west",
        [0, 1, 0] => "up",
        [0, -1, 0] => "down",
        [0, 0, 1] => "south",
        _ => "north",
    }
}

#[mod_api::horizon_part]
impl BlockPart for NozzlePart {
    fn state_for_placement(
        &self,
        host: &dyn LevelHost,
        event: &mut mod_api::StateForPlacementEvent<'_>,
    ) -> Option<Option<BlockState>> {
        if host.state_block(event.state) != Some(NOZZLE) {
            return None;
        }
        let direction = match event.context.face {
            mod_api::Direction::East => "east",
            mod_api::Direction::West => "west",
            mod_api::Direction::Up => "up",
            mod_api::Direction::Down => "down",
            mod_api::Direction::South => "south",
            mod_api::Direction::North => "north",
        };
        Some(host.state_with_property(event.state, "facing", direction))
    }

    fn can_survive(
        &self,
        host: &dyn LevelHost,
        event: &mut mod_api::CanSurviveEvent,
    ) -> Option<bool> {
        if host.state_block(event.state) != Some(NOZZLE) {
            return None;
        }
        let state = host.state_string(event.state)?;
        let facing = state.split("facing=").nth(1)?.split([',', ']']).next()?;
        let direction = direction_from_name(facing)?;
        Some(self.support_matches(host, [event.pos.x, event.pos.y, event.pos.z], direction))
    }

    fn update_shape(
        &self,
        host: &mut dyn mod_api::LevelTicksHost,
        event: &mut mod_api::UpdateShapeEvent,
    ) -> Option<BlockState> {
        if host.state_block(event.state) != Some(NOZZLE) {
            return None;
        }
        let state = host.state_string(event.state)?;
        let facing = state.split("facing=").nth(1)?.split([',', ']']).next()?;
        let direction = direction_from_name(facing)?;
        let pos = [event.pos.x, event.pos.y, event.pos.z];
        let support_pos = offset(pos, direction.map(|n| -n), 1);
        if [
            event.neighbour_pos.x,
            event.neighbour_pos.y,
            event.neighbour_pos.z,
        ] == support_pos
            && !self.support_matches(host, pos, direction)
        {
            host.block_state_id("minecraft:air")
        } else {
            None
        }
    }
}

fn direction_from_name(name: &str) -> Option<[i32; 3]> {
    Some(match name {
        "east" => [1, 0, 0],
        "west" => [-1, 0, 0],
        "up" => [0, 1, 0],
        "down" => [0, -1, 0],
        "south" => [0, 0, 1],
        "north" => [0, 0, -1],
        _ => return None,
    })
}

#[mod_api::horizon_part]
impl BlockEntityPart for NozzlePart {
    fn block_entity_ticks(&self, _: &dyn Host, event: &mut BlockEntityTicksEvent<'_>) {
        event.ticks = true;
    }

    fn block_entity_tick(&self, host: &mut dyn ServerHost, event: &mut BlockEntityTickEvent<'_>) {
        if event.entity.id() != NOZZLE {
            return;
        }
        let Some(level) = host.levels().list_levels().into_iter().find(|level| {
            level
                .block(host, event.pos)
                .is_some_and(|block| block.id(host) == NOZZLE)
        }) else {
            return;
        };
        let Some(direction) = facing(host, level, event.pos) else {
            return;
        };
        let fan_pos = offset(event.pos, direction.map(|n| -n), 1);
        if block_id(host, level, fan_pos).as_deref() != Some(FAN) {
            return;
        }
        let speed = host
            .block_entity_identity(level, fan_pos)
            .and_then(|fan| fan.data(host))
            .and_then(|data| match data.get(&"Speed".into()) {
                Some(Tag::Float(value)) => Some(f32::from_bits(*value)),
                _ => None,
            })
            .unwrap_or(0.0);
        nozzle_tick(
            host,
            level,
            event.pos,
            &mut event.entity.nbt,
            direction,
            speed,
        );
    }
}

fn nozzle_tick(
    host: &mut dyn ServerHost,
    level: LevelRef,
    pos: [i32; 3],
    data: &mut Compound,
    direction: [i32; 3],
    speed: f32,
) {
    if speed == 0.0 {
        data.insert("CreateNozzleRange".into(), Tag::Float(0.0f32.to_bits()));
        set_saved_entities(data, "CreateNozzleItems", Vec::new());
        set_saved_entities(data, "CreateNozzleEntities", Vec::new());
        return;
    }
    let pushing = rules::pushing(speed, direction);
    let reach = f64::from(rules::reach(speed));
    let center = pos.map(|n| f64::from(n) + 0.5);
    let old_range = match data.get(&"CreateNozzleRange".into()) {
        Some(Tag::Float(value)) => f32::from_bits(*value).max(0.0),
        _ => 0.0,
    };
    data.insert(
        "CreateNozzleRange".into(),
        Tag::Float((reach as f32).to_bits()),
    );
    let scan = int(data, "CreateNozzleScan").unwrap_or(0) <= 0;
    data.insert(
        "CreateNozzleScan".into(),
        Tag::Int(if scan {
            5
        } else {
            int(data, "CreateNozzleScan").unwrap_or(0) - 1
        }),
    );
    let mut item_ids = saved_entities(data, "CreateNozzleItems");
    let mut entity_ids = saved_entities(data, "CreateNozzleEntities");
    let players = level.online_players(host).unwrap_or_default();
    if scan && old_range > 0.0 {
        let half = f64::from(old_range / 2.0);
        let entities = level
            .entities_in(host, center.map(|v| v - half), center.map(|v| v + half))
            .unwrap_or_default();
        for entity in entities {
            let Some(uuid) = entity.uuid(host) else {
                continue;
            };
            let Some(position) = entity.position(host) else {
                continue;
            };
            let distance = (0..3)
                .map(|axis| (position[axis] - center[axis]).powi(2))
                .sum::<f64>()
                .sqrt();
            if distance > reach || !nozzle_visible(host, level, center, position) {
                item_ids.retain(|id| *id != uuid);
                entity_ids.retain(|id| *id != uuid);
                continue;
            }
            if host.item_entity(entity).is_some() {
                if !item_ids.contains(&uuid) {
                    item_ids.push(uuid);
                }
            } else if host.living(entity).is_some() && !entity_ids.contains(&uuid) {
                entity_ids.push(uuid);
            }
        }
        // Online players are supplied by the server player list and are not
        // guaranteed to appear in the general entity AABB query.
        for player in &players {
            let entity = player.entity();
            let Some(uuid) = entity.uuid(host) else {
                continue;
            };
            let Some(position) = entity.position(host) else {
                continue;
            };
            let distance = (0..3)
                .map(|axis| (position[axis] - center[axis]).powi(2))
                .sum::<f64>()
                .sqrt();
            if distance <= reach
                && nozzle_visible(host, level, center, position)
                && !entity_ids.contains(&uuid)
            {
                entity_ids.push(uuid);
            }
        }
    }
    let mut candidates = level
        .entities_in(host, center.map(|v| v - reach), center.map(|v| v + reach))
        .unwrap_or_default();
    let ids = item_ids
        .iter()
        .chain(entity_ids.iter())
        .copied()
        .collect::<Vec<_>>();
    for player in &players {
        let entity = player.entity();
        if entity.uuid(host).is_some_and(|uuid| ids.contains(&uuid))
            && !candidates.contains(&entity)
        {
            candidates.push(entity);
        }
    }
    let mut active = Vec::new();
    for entity in candidates.iter().copied() {
        if entity.uuid(host).is_some_and(|uuid| ids.contains(&uuid)) {
            active.push(entity);
        }
    }
    for entity in active {
        let Some(position) = entity.position(host) else {
            continue;
        };
        if !nozzle_visible(host, level, center, position) {
            continue;
        }
        let distance = (0..3)
            .map(|axis| (position[axis] - center[axis]).powi(2))
            .sum::<f64>()
            .sqrt();
        let is_item = host.item_entity(entity).is_some();
        let crouching = !is_item && entity.is_crouching(host).unwrap_or(false);
        let Some(impulse) = rules::nozzle_impulse(
            center,
            position,
            reach,
            pushing,
            if is_item { 128.0 } else { 32.0 },
            crouching,
        ) else {
            continue;
        };
        let velocity = entity.velocity(host).unwrap_or([0.0; 3]);
        let next = std::array::from_fn(|axis| velocity[axis] + impulse[axis]);
        if let Some(player) = players
            .iter()
            .copied()
            .find(|player| player.entity() == entity)
        {
            let _ = player.set_velocity(host, next);
        } else {
            let _ = entity.set_velocity(host, next);
        }
        let _ = entity.reset_fall_distance(host);
        let _ = distance;
    }
    let mut live_ids = Vec::new();
    for entity in candidates.iter().copied() {
        if let Some(uuid) = entity.uuid(host) {
            live_ids.push(uuid);
        }
    }
    item_ids.retain(|id| live_ids.contains(id));
    entity_ids.retain(|id| live_ids.contains(id));
    set_saved_entities(data, "CreateNozzleItems", item_ids);
    set_saved_entities(data, "CreateNozzleEntities", entity_ids);
}

// Kept local until the typed package build validates the contract; the adapter
// intentionally makes no claims about exact Java packet timing.
#[allow(dead_code)]
fn _loaded_speed(data: &Compound) -> f32 {
    match data.get(&"Speed".into()) {
        Some(Tag::Float(value)) => f32::from_bits(*value),
        _ => 0.0,
    }
}
