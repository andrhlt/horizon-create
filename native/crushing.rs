use horizon_core::geometry::Direction;
use horizon_world::level::flags;
use horizon_world::nbt::Tag;

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_belt;
use super::create_depot::{DEPOT, receive_stack};
use super::create_fan::facing;
use super::create_machines::{
    DIRECTIONS, axis_index, float, ingredient_matches, int, mod_entity, offset, rpm_at, set_float,
};

pub(super) const WHEEL: &str = "create:crushing_wheel";
pub(super) const CONTROLLER: &str = "create:crushing_wheel_controller";
pub(super) const CASED_SHAFT: &str = "create:andesite_encased_shaft";
pub(super) const MODEL: &str = "create:block/crushing_wheel/block";
pub(super) const SLOTS: usize = 16;

pub(super) fn placement(
    level: &super::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    if answer.is_some() || level.native_state_block(state) != Some(WHEEL) {
        return;
    }
    let preferred = super::create_hand_crank::preferred_direction(level, context.pos);
    let axis = if context.sneaking {
        preferred.map_or_else(
            || context.nearest_looking_direction().normal(),
            |_| context.face.normal(),
        )
    } else {
        preferred.map_or_else(
            || context.nearest_looking_direction().normal(),
            |face| face.normal(),
        )
    };
    let axis_index = axis
        .iter()
        .position(|component| *component != 0)
        .unwrap_or(1);
    let axis_name = ["x", "y", "z"][axis_index];
    let Some(placed) = level.native_state_with_property(state, "axis", axis_name) else {
        *answer = Some(None);
        return;
    };

    for direction in Direction::ALL {
        let step = direction.normal();
        let pos = offset([context.pos.x, context.pos.y, context.pos.z], step);
        let neighbor = level.world.block(pos[0], pos[1], pos[2]);
        let Some(block) = level.native_state_block(neighbor) else {
            continue;
        };
        if block == WHEEL {
            let neighbor_axis = level
                .registry
                .state(neighbor)
                .and_then(|state| state.properties.get("axis"))
                .map(String::as_str);
            if step[axis_index] == 0 || neighbor_axis != Some(axis_name) {
                *answer = Some(None);
                return;
            }
        } else if block == CONTROLLER && step[axis_index] == 0 {
            *answer = Some(None);
            return;
        }
    }
    *answer = Some(Some(placed));
}

fn axis(game: &Game<'_>, pos: [i32; 3]) -> Option<usize> {
    if game.native_block(pos) != WHEEL {
        return None;
    }
    axis_index(&game.native_block_property(pos, "axis")?)
}

pub(super) fn maintain_pair(game: &mut Game<'_>, pos: [i32; 3]) {
    let Some(axis) = axis(game, pos) else { return };
    for step in DIRECTIONS.into_iter().filter(|step| step[axis] == 0) {
        let middle = offset(pos, step);
        let other = offset(middle, step);
        if self::axis(game, other) == Some(axis) {
            let state = game.world.block(middle[0], middle[1], middle[2]);
            if game.res.behaviours().is_replaceable(state)
                && let Some(controller) = game.native_default_state(CONTROLLER)
            {
                game.native_set_block(
                    game.native_dimension(),
                    middle,
                    controller,
                    flags::UPDATE_ALL,
                );
            }
        }
    }
}

fn cross(a: usize, b: usize) -> [i32; 3] {
    let mut product = [0; 3];
    product[3 - a - b] = if (a + 1) % 3 == b { 1 } else { -1 };
    product
}

fn pair(game: &Game<'_>, pos: [i32; 3]) -> Option<(Direction, f32)> {
    let mut stopped = false;
    for (span, step) in [[1, 0, 0], [0, 1, 0], [0, 0, 1]].into_iter().enumerate() {
        let negative = offset(pos, step.map(|n| -n));
        let positive = offset(pos, step);
        let Some(axle) = axis(game, negative) else {
            continue;
        };
        if axle == span || axis(game, positive) != Some(axle) {
            continue;
        }
        let first = rpm_at(game, negative);
        let second = rpm_at(game, positive);
        if first == 0.0 || second == 0.0 || first.signum() == second.signum() {
            stopped = true;
            continue;
        }
        let normal = cross(axle, span).map(|n| n * first.signum() as i32);
        let face = Direction::ALL
            .into_iter()
            .find(|face| face.normal() == normal)?;
        return Some((face, first.abs() / 50.0));
    }
    stopped.then_some((Direction::Down, 0.0))
}

fn name(face: Direction) -> &'static str {
    match face {
        Direction::Up => "up",
        Direction::Down => "down",
        Direction::North => "north",
        Direction::South => "south",
        Direction::East => "east",
        Direction::West => "west",
    }
}

fn recipe(game: &Game<'_>, input: &ItemStack) -> Option<(f32, Vec<(ItemStack, f32)>)> {
    for kind in ["create:crushing", "create:milling"] {
        for recipe in game.native_recipes_of_type(kind) {
            let Some(ingredients) = recipe.json["ingredients"].as_array() else {
                continue;
            };
            if ingredients.len() != 1 || !ingredient_matches(game, &ingredients[0], &input.item) {
                continue;
            }
            let results = recipe.json["results"]
                .as_array()?
                .iter()
                .filter_map(|result| {
                    Some((
                        game.native_recipe_result(result)?,
                        result["chance"].as_f64().unwrap_or(1.0) as f32,
                    ))
                })
                .collect();
            let duration = recipe.json["processing_time"].as_u64().unwrap_or(100) as f32;
            return Some((duration, results));
        }
    }
    None
}

fn insert_item(entity: &mut ModBlockEntity, stack: ItemStack, duration: f32) {
    entity.items.resize(SLOTS, None);
    entity.items[0] = Some(stack);
    set_float(&mut entity.nbt, "ProcessingTime", duration);
    entity.nbt.insert("AppliedRecipe".into(), Tag::Byte(0));
}

pub(super) fn offer(game: &mut Game<'_>, pos: [i32; 3], stack: &mut ItemStack) {
    if !mod_entity(game, pos)
        .is_some_and(|entity| entity.id == CONTROLLER && entity.items.iter().all(Option::is_none))
    {
        return;
    }
    let duration = recipe(game, stack).map_or(100.0, |recipe| recipe.0);
    if game
        .native_with_mod_block_entity(pos, |entity| insert_item(entity, stack.clone(), duration))
        .is_some()
    {
        stack.count = 0;
    }
}

pub(super) fn blocking_belt_position(
    game: &mut Game<'_>,
    chain: &[[i32; 3]],
    direction: Direction,
    movement: Direction,
    old: f32,
    next: f32,
    stack: &mut ItemStack,
) -> Option<f32> {
    let length = chain.len() as i32;
    let positive = direction == movement;
    let step = if positive { 1 } else { -1 };
    let mut index = (old.floor() as i32).clamp(0, length - 1);
    let along = direction.normal();
    while (0..length).contains(&index)
        && if positive {
            index as f32 <= next
        } else {
            (index + 1) as f32 >= next
        }
    {
        let pos = offset(chain[index as usize], [0, 1, 0]);
        let entry = index as f32 + 0.5 - 0.399 * step as f32;
        index += step;
        if game.native_block(pos) != CONTROLLER
            || game.native_block_property(pos, "facing").as_deref() != Some(name(movement))
        {
            continue;
        }
        let past = (next - entry) * step as f32;
        if past <= 0.0 || past >= 0.799 {
            return None;
        }
        offer(game, pos, stack);
        return Some(entry);
    }
    None
}

fn emit(game: &mut Game<'_>, pos: [i32; 3], face: Direction, inputs: &mut [Option<ItemStack>]) {
    let front = face.normal();
    let destination = offset(pos, [front[0], -1, front[2]]);
    if face != Direction::Up
        && let Some((start, index, movement, speed)) = create_belt::feed_point(game, destination)
    {
        for input in inputs.iter_mut() {
            if input.is_some() && create_belt::can_feed(game, start, index, movement, face, speed) {
                create_belt::feed(
                    game,
                    start,
                    index,
                    movement,
                    face,
                    speed,
                    input.take().unwrap(),
                );
            }
        }
    } else if face != Direction::Up && game.native_block(destination) == DEPOT {
        for input in inputs.iter_mut() {
            if let Some(stack) = input.take() {
                *input = receive_stack(game, destination, stack);
            }
        }
    } else {
        let at = std::array::from_fn(|i| f64::from(pos[i]) + 0.5 + f64::from(front[i]) * 0.55);
        let velocity = [
            f64::from(front[0]) * 0.25,
            if face == Direction::Up { 0.5 } else { 0.0 },
            f64::from(front[2]) * 0.25,
        ];
        for stack in inputs.iter_mut().filter_map(Option::take) {
            game.add_item_entity(stack, at, Some(velocity), 10);
        }
    }
}

pub(super) fn load_structure(nbt: &mut horizon_world::nbt::Compound) {
    if !matches!(nbt.get(&"id".into()), Some(Tag::String(id)) if id.to_string_lossy() == CONTROLLER)
    {
        return;
    }
    set_float(nbt, "Speed", 0.0);
    if let Some(Tag::Compound(inventory)) = nbt.get_mut(&"Inventory".into())
        && matches!(inventory.get(&"Items".into()), Some(Tag::List(items)) if items.is_empty())
    {
        inventory.insert("AppliedRecipe".into(), Tag::Byte(0));
    }
}

fn migrate(entity: &mut ModBlockEntity) {
    entity.items.resize(SLOTS, None);
    if let Some(Tag::Compound(inventory)) = entity.nbt.remove(&"Inventory".into()) {
        if let Some(Tag::List(items)) = inventory.get(&"Items".into()) {
            for entry in items {
                let Tag::Compound(stack) = entry else {
                    continue;
                };
                let slot = int(stack, "Slot").unwrap_or(-1) as usize;
                if let Some(target) = entity.items.get_mut(slot)
                    && target.is_none()
                {
                    *target = ItemStack::from_nbt(stack);
                }
            }
        }
        set_float(
            &mut entity.nbt,
            "ProcessingTime",
            float(&inventory, "ProcessingTime").unwrap_or(0.0),
        );
        let applied =
            entity.items.iter().any(Option::is_some) && int(&inventory, "AppliedRecipe") == Some(1);
        entity
            .nbt
            .insert("AppliedRecipe".into(), Tag::Byte(i8::from(applied)));
    }
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    migrate(entity);
    let Some((face, speed)) = pair(game, pos) else {
        if let Some(air) = game.native_default_state("minecraft:air") {
            // Its block entity is currently lent to this tick, so hand back
            // any contents explicitly before removing the block.
            for stack in entity.items.iter_mut().filter_map(Option::take) {
                game.add_item_entity(
                    stack,
                    pos.map(|coordinate| f64::from(coordinate) + 0.5),
                    None,
                    10,
                );
            }
            game.native_set_block(game.native_dimension(), pos, air, flags::UPDATE_ALL);
        }
        return;
    };
    let valid = speed > 0.0;
    game.native_set_block_property_with(pos, "valid", if valid { "true" } else { "false" }, 2);
    game.native_set_block_property_with(pos, "facing", name(face), 2);
    set_float(&mut entity.nbt, "Speed", speed);
    if !valid || entity.items.iter().all(Option::is_none) {
        return;
    }

    let applied = int(&entity.nbt, "AppliedRecipe").unwrap_or(1) != 0;
    if !applied {
        let Some(input) = entity.items[0].as_ref() else {
            return;
        };
        let loss = (speed * 4.0 / (input.count as f32).log2()).clamp(0.25, 20.0);
        let remaining = float(&entity.nbt, "ProcessingTime").unwrap_or(0.0) - loss;
        if remaining >= 20.0 {
            set_float(&mut entity.nbt, "ProcessingTime", remaining);
            return;
        }
        let count = input.count;
        let results = recipe(game, input).map(|recipe| recipe.1);
        entity.items.fill(None);
        if let Some(results) = results {
            for (slot, stack) in entity
                .items
                .iter_mut()
                .skip(1)
                .zip(super::create_fan_items::roll(game, count, &results))
            {
                *slot = Some(stack);
            }
        }
        set_float(&mut entity.nbt, "ProcessingTime", 0.0);
        entity.nbt.insert("AppliedRecipe".into(), Tag::Byte(1));
        return;
    }
    emit(game, pos, face, &mut entity.items);
}

pub(super) fn landing(
    game: &mut Game<'_>,
    state: horizon_world::registry::BlockStateId,
    pos: [i32; 3],
    stack: &mut ItemStack,
) {
    if game.native_state_block(state) == Some(CONTROLLER)
        && matches!(facing(game, state), Some(Direction::Down))
        && game.native_block_state_property(state, "valid") == Some("true")
    {
        offer(game, pos, stack);
    }
}
