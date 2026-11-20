use std::hash::{Hash, Hasher};

use horizon_core::geometry::{Direction, trig};
use horizon_core::random::RandomSource;
use horizon_world::nbt::{Compound, Tag};

use crate::containers::ModBlockEntity;
use crate::crafting::{Ingredient, Recipe as CraftingRecipe, Template};
use crate::items::ItemStack;

use super::Game;
use super::create_belt;
use super::create_depot::{DEPOT, compound, encode, receive_stack};
use super::create_fan::facing;
use super::create_fluids::{
    BASIN, BUCKET, Fluid, basin_destination, basin_tanks, liquid_from_stack, set_basin_fluid,
};
use super::create_item_filters::accepts;
use super::create_machines::{
    float, ingredient_matches, insert, int, mod_entity, offset, reading, set_float,
};
use super::create_visuals::{draw_rotating, wheel_angle};
use super::native_block_entity_draw::BlockEntityDraw;

pub(super) const MIXER: &str = "create:mechanical_mixer";
use super::create_burner::BURNER;
const SHAFTLESS_COG: &str = "create:block/cogwheel_shaftless";
const POLE: &str = "create:block/mechanical_mixer/pole";
const WHISK: &str = "create:block/mechanical_mixer/head";

fn rolled_output_counts<T>(
    outputs: Vec<(T, u32, Option<f32>)>,
    mut roll: impl FnMut() -> f32,
) -> Vec<(T, u32)> {
    outputs
        .into_iter()
        .map(|(item, count, chance)| {
            let count = chance.map_or(count, |chance| {
                (0..count).filter(|_| roll() <= chance).count() as u32
            });
            (item, count)
        })
        .filter(|(_, count)| *count > 0)
        .collect()
}

pub(super) fn models(models: &mut Vec<String>) {
    models.extend([SHAFTLESS_COG, POLE, WHISK].map(String::from));
}

pub(super) struct Recipe {
    pub(super) id: String,
    inputs: Vec<u32>,
    outputs: Vec<(ItemStack, Option<f32>)>,
    fluid_output: Option<Fluid>,
    brewed: Option<Brewed>,
    drained: [i32; 4],
    duration: u64,
}

struct Brewed {
    from_output: bool,
    slot: usize,
    input: Fluid,
    output: Fluid,
}

fn consume(
    slots: &[Option<ItemStack>],
    used: &mut [u32],
    mut count: u32,
    matches: impl Fn(&ItemStack) -> bool,
) -> Option<()> {
    for (slot, used) in slots.iter().zip(used.iter_mut()) {
        if let Some(stack) = slot.as_ref().filter(|stack| matches(stack)) {
            let taken = (stack.count - *used).min(count);
            count -= taken;
            *used += taken;
        }
        if count == 0 {
            return Some(());
        }
    }
    None
}

fn brew(game: &Game<'_>, basin: &ModBlockEntity, wanted: Option<&str>) -> Option<Recipe> {
    let in_tanks = basin_tanks(basin, false);
    let out_tanks = basin_tanks(basin, true);
    for (input_slot, item) in basin.items[..9].iter().enumerate() {
        let Some(reagent) = item.as_ref() else {
            continue;
        };
        for (from_output, tanks) in [(false, &in_tanks), (true, &out_tanks)] {
            for (slot, fluid) in tanks.iter().enumerate() {
                if !from_output
                    && wanted.is_none()
                    && matches!(basin.nbt.get(&format!("InputTank{slot}Refilled").as_str().into()),
                        Some(Tag::Long(refilled)) if *refilled == game.world.game_time)
                {
                    continue;
                }
                let Some(fluid) = fluid.as_ref().filter(|fluid| fluid.amount >= BUCKET) else {
                    continue;
                };
                let Some((_, bottle)) = super::create_spout::bottle(fluid) else {
                    continue;
                };
                let Some(recipe) = game.stations().brewing.find(&bottle, reagent) else {
                    continue;
                };
                if wanted.is_some_and(|id| id != recipe.id) {
                    continue;
                }
                let Some(output) = liquid_from_stack(&recipe.output, BUCKET) else {
                    continue;
                };
                let Some(out) = basin_destination(&out_tanks, &output) else {
                    continue;
                };
                if out_tanks[out]
                    .as_ref()
                    .is_some_and(|current| current.amount + output.amount > BUCKET)
                {
                    continue;
                }
                let mut inputs = vec![0; 9];
                inputs[input_slot] = 1;
                return Some(Recipe {
                    id: recipe.id.clone(),
                    inputs,
                    outputs: Vec::new(),
                    fluid_output: None,
                    brewed: Some(Brewed {
                        from_output,
                        slot,
                        input: fluid.clone(),
                        output,
                    }),
                    drained: [0; 4],
                    duration: 0,
                });
            }
        }
    }
    None
}

fn recipe(game: &Game<'_>, pos: [i32; 3], wanted: Option<&str>) -> Option<Recipe> {
    let basin = mod_entity(game, pos).filter(|basin| basin.id == BASIN)?;
    if basin.items.len() < 18 {
        return None;
    }
    let burner = offset(pos, Direction::Down.normal());
    let heat = match game.native_block_property(burner, "blaze").as_deref() {
        Some("seething") => 2,
        Some("fading" | "kindled") => 1,
        _ => 0,
    };
    game.native_recipes_of_type("create:mixing")
        .iter()
        .filter(|recipe| wanted.is_none_or(|id| id == recipe.id))
        .filter_map(|recipe| {
            let json = &recipe.json;
            let needed = match json["heat_requirement"].as_str() {
                Some("superheated") => 2,
                Some("heated") => 1,
                _ => 0,
            };
            if heat < needed {
                return None;
            }
            let (inputs, drained) = processing_inputs(game, basin, &basin.items[..9], json)?;
            let mut outputs = Vec::new();
            let mut fluid_output = None;
            for result in json["results"].as_array()? {
                if let Some(amount) = result["amount"].as_i64() {
                    let amount = i32::try_from(amount).ok().filter(|amount| *amount > 0)?;
                    if fluid_output.is_some() {
                        return None;
                    }
                    fluid_output = Some(Fluid {
                        id: result["id"].as_str()?.to_owned(),
                        amount,
                        components: None,
                    });
                } else {
                    let output = game.native_recipe_result(result)?;
                    let chance = result["chance"].as_f64().unwrap_or(1.0) as f32;
                    outputs.push((output, (chance < 1.0).then_some(chance)));
                }
            }
            if !outputs
                .iter()
                .all(|(stack, _)| accepts(game.items(), &basin.nbt, stack))
            {
                return None;
            }
            let plan = Recipe {
                id: recipe.id.clone(),
                inputs,
                outputs,
                fluid_output,
                brewed: None,
                drained,
                duration: json["processing_time"].as_u64().unwrap_or(0),
            };
            if let Some(fluid) = &plan.fluid_output {
                if !accepts_fluid_output(game, basin, fluid) {
                    return None;
                }
                basin_fluid_output(basin, &plan, fluid)?;
            }
            Some(plan)
        })
        .max_by_key(|recipe| recipe.inputs.iter().sum::<u32>())
        .or_else(|| {
            if heat >= 1 {
                brew(game, basin, wanted)
            } else {
                None
            }
        })
}

#[cfg(test)]
mod recipe_output_tests {
    use super::rolled_output_counts;

    #[test]
    fn mixing_outputs_keep_recipe_order_and_roll_each_item() {
        let mut rolls = [0.1, 0.4, 0.9].into_iter();
        let actual = rolled_output_counts(
            vec![
                ("first", 1, None),
                ("chance", 3, Some(0.5)),
                ("last", 1, None),
            ],
            || rolls.next().unwrap(),
        );
        assert_eq!(actual, vec![("first", 1), ("chance", 2), ("last", 1)]);
    }
}

fn processing_inputs(
    game: &Game<'_>,
    basin: &ModBlockEntity,
    items: &[Option<ItemStack>],
    json: &serde_json::Value,
) -> Option<(Vec<u32>, [i32; 4])> {
    let mut used = vec![0; items.len()];
    let mut drained = [0; 4];
    // Java combines the basin's output tanks before its input tanks.
    let tanks = [basin_tanks(basin, true), basin_tanks(basin, false)].concat();
    for ingredient in json["ingredients"].as_array()? {
        match ingredient["type"].as_str() {
            Some(kind @ ("neoforge:single" | "neoforge:tag")) => {
                let mut amount = i32::try_from(ingredient["amount"].as_i64()?).ok()?;
                if amount <= 0 {
                    return None;
                }
                for (tank, reserved) in tanks.iter().zip(&mut drained) {
                    let Some(fluid) = tank else { continue };
                    let matched = match kind {
                        "neoforge:single" => super::create_spout::matches_fluid(fluid, ingredient),
                        _ => matches!(
                            (ingredient["tag"].as_str(), fluid.id.as_str()),
                            (Some("c:honey"), "create:honey") | (Some("c:milk"), "minecraft:milk"),
                        ),
                    };
                    if matched {
                        let taken = (fluid.amount - *reserved).min(amount);
                        *reserved += taken;
                        amount -= taken;
                    }
                }
                if amount > 0 {
                    return None;
                }
            }
            _ => consume(
                items,
                &mut used,
                ingredient["count"].as_u64().unwrap_or(1) as u32,
                |stack| ingredient_matches(game, ingredient, &stack.item),
            )?,
        }
    }
    Some((used, drained))
}

fn uniform_crafting(recipe: &CraftingRecipe) -> Option<(&Ingredient, u32, &Template)> {
    let (ingredients, missing, result): (Vec<_>, _, _) = match recipe {
        CraftingRecipe::Shaped { cells, result, .. } => {
            let ingredients: Vec<_> = cells.iter().flatten().collect();
            let missing = ingredients.len() != cells.len();
            (ingredients, missing, result)
        }
        CraftingRecipe::Shapeless {
            ingredients,
            result,
        } => (ingredients.iter().collect(), false, result),
        CraftingRecipe::Special(_) => return None,
    };
    if !matches!(ingredients.len(), 4 | 9) || missing {
        return None;
    }
    let first = ingredients[0];
    ingredients
        .iter()
        .all(|ingredient| ingredient.order == first.order)
        .then_some((first, ingredients.len() as u32, result))
}

pub(super) fn compacting_recipe(
    game: &Game<'_>,
    pos: [i32; 3],
    wanted: Option<&str>,
) -> Option<Recipe> {
    let basin = mod_entity(game, pos).filter(|basin| basin.id == BASIN)?;
    if basin.items.len() < 18 || !processed(&basin.nbt).is_empty() {
        return None;
    }
    let spout = basin_has_spout(game, pos);
    let can_make = |recipe: &Recipe| {
        recipe
            .outputs
            .iter()
            .all(|(stack, _)| accepts(game.items(), &basin.nbt, stack))
            && (spout || basin_output(game, basin, recipe).is_some())
    };
    let explicit = game
        .native_recipes_of_type("create:compacting")
        .iter()
        .filter(|recipe| wanted.is_none_or(|id| id == recipe.id))
        .filter_map(|recipe| {
            let (inputs, drained) = processing_inputs(game, basin, &basin.items, &recipe.json)?;
            let outputs = recipe.json["results"]
                .as_array()?
                .iter()
                .map(|result| game.native_recipe_result(result))
                .collect::<Option<Vec<_>>>()?;
            Some(Recipe {
                id: recipe.id.clone(),
                inputs,
                outputs: outputs.into_iter().map(|stack| (stack, None)).collect(),
                fluid_output: None,
                brewed: None,
                drained,
                duration: 0,
            })
        });
    let available: u32 = basin.items.iter().flatten().map(|item| item.count).sum();
    let crafting = game
        .recipes()
        .crafting
        .iter()
        .filter(|(id, _)| {
            available >= 4
                && !id.ends_with("_manual_only")
                && wanted.is_none_or(|wanted| wanted == id)
        })
        .filter_map(|(id, recipe)| {
            let (ingredient, count, result) = uniform_crafting(recipe)?;
            let mut inputs = vec![0; basin.items.len()];
            consume(&basin.items, &mut inputs, count, |stack| {
                ingredient.test(stack)
            })?;
            Some(Recipe {
                id: id.clone(),
                inputs,
                outputs: vec![(result.create(), None)],
                fluid_output: None,
                brewed: None,
                drained: [0; 4],
                duration: 0,
            })
        });
    explicit
        .chain(crafting)
        .filter(can_make)
        .max_by_key(|recipe| recipe.inputs.iter().sum::<u32>())
}

fn processed(nbt: &Compound) -> Vec<ItemStack> {
    let Some(Tag::List(stacks)) = nbt.get(&"Overflow".into()) else {
        return Vec::new();
    };
    stacks
        .iter()
        .filter_map(|stack| {
            if let Tag::Compound(stack) = stack {
                ItemStack::from_nbt(stack)
            } else {
                None
            }
        })
        .collect()
}

fn write_overflow(basin: &mut ModBlockEntity, stacks: &[ItemStack]) {
    basin.nbt.insert(
        "Overflow".into(),
        Tag::List(stacks.iter().map(encode).collect()),
    );
}

pub(super) fn use_item(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> bool {
    if stack.item.as_ref() != "minecraft:milk_bucket" || game.native_block(pos) != BASIN {
        return false;
    }
    let milk = Fluid {
        id: "minecraft:milk".into(),
        amount: BUCKET,
        components: None,
    };
    let filled = game.native_with_mod_block_entity(pos, |basin| {
        let tanks = basin_tanks(basin, false);
        let Some(index) = basin_destination(&tanks, &milk) else {
            return false;
        };
        if tanks[index].is_some() {
            return false;
        }
        set_basin_fluid(basin, false, index, Some(milk));
        true
    });
    if filled != Some(true) {
        // The Basin handles the bucket click even if its milk tank is full.
        return filled.is_some();
    }

    if !game.creative {
        game.consume_held();
        let bucket = ItemStack::new("minecraft:bucket", 1);
        if game.held().is_none() {
            *game.held_mut() = Some(bucket);
        } else if let Some(left) = game.give(bucket) {
            let center = pos.map(|value| f64::from(value) + 0.5);
            game.add_item_entity(left, center, None, 10);
        }
    }
    game.native_block_entity_sync(pos);
    true
}

const BASIN_FLUID_VISUAL: &str = "BasinFluidVisual";

fn basin_display_tick(game: &mut Game<'_>, pos: [i32; 3], basin: &mut ModBlockEntity) {
    let tanks = basin_tanks(basin, false)
        .into_iter()
        .chain(basin_tanks(basin, true));
    let previous = match basin.nbt.get(&BASIN_FLUID_VISUAL.into()) {
        Some(Tag::List(tanks)) => tanks.as_slice(),
        _ => &[],
    };
    let visual: Vec<_> = tanks
        .enumerate()
        .map(|(index, tank)| {
            let before = match previous.get(index) {
                Some(Tag::Compound(tank)) => Some(tank),
                _ => None,
            };
            let old_level = before.and_then(|tank| float(tank, "Level")).unwrap_or(0.0);
            let target = tank
                .as_ref()
                .map_or(0.0, |tank| tank.amount as f32 / BUCKET as f32);
            let difference = target - old_level;
            let next = if difference.abs() < 1.0e-5 {
                target
            } else {
                old_level + difference * 0.25
            };
            let mut tag = Compound::new();
            if target > 0.0 || old_level.max(next) * BUCKET as f32 >= 1.0 {
                if let Some(fluid) = tank
                    .map(|tank| tank.nbt())
                    .or_else(|| before.and_then(|tank| tank.get(&"Fluid".into())).cloned())
                {
                    tag.insert("Fluid".into(), fluid);
                    set_float(&mut tag, "PreviousLevel", old_level);
                    set_float(&mut tag, "Level", next);
                }
            }
            Tag::Compound(tag)
        })
        .collect();
    if visual
        .iter()
        .all(|tank| matches!(tank, Tag::Compound(tank) if tank.is_empty()))
    {
        if basin.nbt.remove(&BASIN_FLUID_VISUAL.into()).is_some() {
            game.native_block_entity_sync(pos);
        }
    } else if visual != previous {
        basin
            .nbt
            .insert(BASIN_FLUID_VISUAL.into(), Tag::List(visual));
        game.native_block_entity_sync(pos);
    }
}

pub(super) fn basin_display_update_tag(basin: &ModBlockEntity) -> Compound {
    let visual = basin
        .nbt
        .get(&BASIN_FLUID_VISUAL.into())
        .cloned()
        .unwrap_or_else(|| Tag::List(Vec::new()));
    Compound::from([(BASIN_FLUID_VISUAL.into(), visual)])
}

pub(super) fn draw_basin(game: &Game<'_>, basin: &ModBlockEntity, draw: &mut BlockEntityDraw) {
    let Some(Tag::List(tanks)) = basin.nbt.get(&BASIN_FLUID_VISUAL.into()) else {
        return;
    };
    let visible: Vec<_> = tanks
        .iter()
        .filter_map(|tank| {
            let Tag::Compound(tank) = tank else {
                return None;
            };
            let fluid = super::create_fluids::read_fluid(compound(tank, "Fluid")?)?;
            let previous = float(tank, "PreviousLevel")?;
            let current = float(tank, "Level")?;
            let units = (previous + (current - previous) * draw.partial) * BUCKET as f32;
            (units >= 1.0).then_some((fluid, units))
        })
        .collect();
    let total: f32 = visible.iter().map(|(_, units)| units).sum();
    if total < 1.0 {
        return;
    }
    let fill = (total / (2.0 * BUCKET as f32)).clamp(0.0, 1.0);
    let height = 12.0 * (1.0 - (1.0 - fill) * (1.0 - fill));
    let mut x = 2.0;
    for (fluid, units) in visible {
        let width = (units / total).clamp(0.0, 1.0) * 12.0;
        super::create_spout::draw_still_fluid(
            game,
            draw,
            &fluid,
            [x, 2.0, 2.0],
            [width, height, 12.0],
        );
        x += width;
    }
}

fn basin_inputs(basin: &ModBlockEntity) -> Tag {
    let mut hash = std::collections::hash_map::DefaultHasher::new();
    horizon_client::save::encode_items(&basin.items[..9]).hash(&mut hash);
    Tag::Long(hash.finish() as i64)
}

pub(super) fn basin_tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    // Java schedules the operator check when the Basin ticks after an input change.
    let inputs = basin_inputs(entity);
    entity.nbt.insert("CheckedInputs".into(), inputs);
    basin_display_tick(game, pos, entity);
    let mut outputs = processed(&entity.nbt);
    if outputs.is_empty() {
        return;
    }
    let state = game.world.block(pos[0], pos[1], pos[2]);
    let Some(face) = facing(game, state).filter(|face| face.normal()[1] == 0) else {
        return;
    };
    let target = offset(offset(pos, Direction::Down.normal()), face.normal());
    if let Some((start, index, movement, speed)) = create_belt::feed_point(game, target) {
        outputs.retain(|item| {
            if create_belt::can_feed(game, start, index, movement, Direction::Up, speed) {
                // The basin uses the segment's inventory, which inserts
                // near its center rather than through its leading edge.
                create_belt::feed(
                    game,
                    start,
                    index,
                    movement,
                    Direction::Up,
                    speed,
                    item.clone(),
                );
                false
            } else {
                true
            }
        });
    } else {
        outputs = outputs
            .into_iter()
            .filter_map(|item| {
                if game.native_block(target) == DEPOT {
                    receive_stack(game, target, item)
                } else {
                    game.native_insert_item(target, face.opposite(), item)
                }
            })
            .collect();
    }
    write_overflow(entity, &outputs);
}

fn basin_has_spout(game: &Game<'_>, pos: [i32; 3]) -> bool {
    let state = game.world.block(pos[0], pos[1], pos[2]);
    facing(game, state).is_some_and(|face| face.normal()[1] == 0)
}

fn subtract(slot: &mut Option<ItemStack>, count: u32) {
    if let Some(stack) = slot.as_mut() {
        stack.count -= count;
        if stack.count == 0 {
            *slot = None;
        }
    }
}

fn basin_output(
    game: &Game<'_>,
    basin: &ModBlockEntity,
    plan: &Recipe,
) -> Option<Vec<Option<ItemStack>>> {
    let mut output = basin.items[9..].to_vec();
    for (slot, count) in output.iter_mut().zip(plan.inputs.iter().skip(9)) {
        subtract(slot, *count);
    }
    for (stack, _) in &plan.outputs {
        let limit = game.native_max_stack_size(&stack.item).unwrap_or(64);
        if insert(&mut output, stack, limit) > 0 {
            return None;
        }
    }
    Some(output)
}

fn accepts_fluid_output(game: &Game<'_>, basin: &ModBlockEntity, fluid: &Fluid) -> bool {
    if !basin.nbt.contains_key(&"Filter".into()) {
        return true;
    }
    let container = match fluid.id.as_str() {
        "create:honey" => "minecraft:honey_bottle",
        "create:chocolate" => "create:chocolate_bucket",
        _ => return false,
    };
    accepts(game.items(), &basin.nbt, &ItemStack::new(container, 1))
}

fn basin_fluid_output(
    basin: &ModBlockEntity,
    plan: &Recipe,
    fluid: &Fluid,
) -> Option<(usize, Fluid)> {
    let mut tanks = basin_tanks(basin, true);
    for (tank, reserved) in tanks.iter_mut().zip(plan.drained) {
        if let Some(current) = tank {
            current.amount -= reserved;
            if current.amount <= 0 {
                *tank = None;
            }
        }
    }
    let index = basin_destination(&tanks, fluid)?;
    let mut filled = fluid.clone();
    filled.amount += tanks[index].as_ref().map_or(0, |existing| existing.amount);
    (filled.amount <= BUCKET).then_some((index, filled))
}

pub(super) fn apply(game: &mut Game<'_>, pos: [i32; 3], planned: Recipe) -> bool {
    if !mod_entity(game, pos).is_some_and(|basin| basin.id == BASIN && basin.items.len() >= 18) {
        return false;
    }
    let spout = basin_has_spout(game, pos);
    if spout && mod_entity(game, pos).is_some_and(|basin| !processed(&basin.nbt).is_empty()) {
        return false;
    }
    let mut planned = planned;
    planned.outputs = rolled_output_counts(
        planned
            .outputs
            .drain(..)
            .map(|(stack, chance)| {
                let count = stack.count;
                (stack, count, chance)
            })
            .collect(),
        || game.world.random.next_float(),
    )
    .into_iter()
    .map(|(mut stack, count)| {
        stack.count = count;
        (stack, None)
    })
    .collect();
    let Some(basin) =
        mod_entity(game, pos).filter(|basin| basin.id == BASIN && basin.items.len() >= 18)
    else {
        return false;
    };
    let output = if spout {
        None
    } else {
        let Some(output) = basin_output(game, basin, &planned) else {
            return false;
        };
        Some(output)
    };
    let fluid_output = match &planned.fluid_output {
        Some(fluid) => {
            let Some(output) = basin_fluid_output(basin, &planned, fluid) else {
                return false;
            };
            Some(output)
        }
        None => None,
    };
    game.native_with_mod_block_entity(pos, |basin| {
        if let Some(mut brewed) = planned.brewed {
            let mut output_tanks = basin_tanks(basin, true);
            brewed.input.amount -= BUCKET;
            let rest = (brewed.input.amount > 0).then_some(brewed.input);
            if brewed.from_output {
                output_tanks[brewed.slot] = rest.clone();
            }
            let Some(index) = basin_destination(&output_tanks, &brewed.output) else {
                return false;
            };
            brewed.output.amount += output_tanks[index].as_ref().map_or(0, |fluid| fluid.amount);
            if brewed.output.amount > BUCKET {
                return false;
            }
            set_basin_fluid(basin, brewed.from_output, brewed.slot, rest);
            set_basin_fluid(basin, true, index, Some(brewed.output));
        }
        for (index, amount) in planned.drained.into_iter().enumerate() {
            if amount > 0 {
                let from_output = index < 2;
                let slot = index % 2;
                let mut rest = basin_tanks(basin, from_output)[slot].clone();
                if let Some(fluid) = &mut rest {
                    fluid.amount -= amount;
                }
                set_basin_fluid(basin, from_output, slot, rest);
            }
        }
        if let Some((index, fluid)) = fluid_output {
            set_basin_fluid(basin, true, index, Some(fluid));
        }
        if let Some(output) = output {
            basin.items[9..].clone_from_slice(&output);
            for (slot, count) in basin.items[..9].iter_mut().zip(planned.inputs) {
                subtract(slot, count);
            }
        } else {
            for (slot, count) in basin.items.iter_mut().zip(planned.inputs) {
                subtract(slot, count);
            }
            let outputs = planned
                .outputs
                .iter()
                .map(|(stack, _)| stack.clone())
                .collect::<Vec<_>>();
            write_overflow(basin, &outputs);
        }
        true
    })
    .unwrap_or(false)
}

pub(super) fn tick(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    rpm: f32,
    changed: bool,
) {
    let basin = offset(pos, [0, -2, 0]);
    let fluid_check = entity.nbt.remove(&"CheckFluidRecipe".into()).is_some();
    let mut running = int(&entity.nbt, "Running") == Some(1);
    let mut ticks = int(&entity.nbt, "Ticks").unwrap_or(0);
    let mut time = int(&entity.nbt, "ProcessingTicks").unwrap_or(0);
    let mut active_recipe = match entity.nbt.get(&"Recipe".into()) {
        Some(Tag::String(id)) => Some(id.to_string_lossy()),
        _ => None,
    };
    if ticks >= 40 || (running && game.native_block(basin) != BASIN) {
        running = false;
        ticks = 0;
        active_recipe = None;
    } else {
        if !running
            && rpm.abs() >= 32.0
            && mod_entity(game, basin).is_some_and(|basin| processed(&basin.nbt).is_empty())
            && let Some(plan) = recipe(game, basin, None)
        {
            let uses_fluid =
                plan.fluid_output.is_some() || plan.drained.iter().any(|&amount| amount > 0);
            let inputs_checked = mod_entity(game, basin).is_some_and(|basin| {
                basin.nbt.get(&"CheckedInputs".into()) == Some(&basin_inputs(basin))
            });
            if !uses_fluid && !inputs_checked {
                // Wait for the Basin tick to schedule its operator check.
            } else if uses_fluid && !fluid_check && !changed {
                // The Basin defers processing until the next operator tick.
                entity.nbt.insert("CheckFluidRecipe".into(), Tag::Byte(1));
            } else {
                running = true;
                ticks = 0;
                active_recipe = Some(plan.id);
            }
        }
        if running {
            if rpm.abs() < 32.0 {
                if ticks < 20 {
                    ticks = 40 - ticks;
                } else if ticks == 20 {
                    ticks += 1;
                }
            }
            if ticks == 20 {
                if time < 0 {
                    let duration = recipe(game, basin, active_recipe.as_deref())
                        .map_or(0, |plan| plan.duration);
                    let multiplier = if duration == 0 {
                        1.0
                    } else {
                        duration as f32 / 100.0
                    };
                    let speed_steps = ((512.0 / rpm.abs()) as u32).max(1).ilog2() as i32;
                    time = (speed_steps * (15.0 * multiplier).ceil() as i32 + 1).max(1);
                } else {
                    time -= 1;
                    if time == 0 {
                        ticks += 1;
                        time = -1;
                        if let Some(plan) = recipe(game, basin, active_recipe.as_deref()) {
                            let id = plan.id.clone();
                            if apply(game, basin, plan) && recipe(game, basin, Some(&id)).is_some()
                            {
                                ticks = 20;
                                active_recipe = Some(id);
                            }
                        }
                    }
                }
            }
            if ticks != 20 {
                ticks += 1;
            }
        }
    }
    entity
        .nbt
        .insert("Running".into(), Tag::Byte(i8::from(running)));
    entity.nbt.insert("Ticks".into(), Tag::Int(ticks));
    entity.nbt.insert("ProcessingTicks".into(), Tag::Int(time));
    if let Some(id) = active_recipe {
        entity
            .nbt
            .insert("Recipe".into(), Tag::String(id.as_str().into()));
    } else {
        entity.nbt.remove(&"Recipe".into());
    }
    set_float(
        &mut entity.nbt,
        "HeadOffset",
        head_offset(running, ticks, 0.0),
    );
    set_float(&mut entity.nbt, "HeadRPM", head_speed(running, ticks, rpm));
    if running || changed {
        game.native_block_entity_sync(pos);
    }
}

fn head_offset(running: bool, ticks: i32, partial: f32) -> f32 {
    let motion = if !running {
        0.0
    } else if ticks == 20 {
        1.0
    } else {
        let time = if ticks < 20 {
            ticks as f32 + partial
        } else {
            (40 - ticks) as f32 - partial
        };
        (1.0 - trig::cos(f64::from(
            (f64::from(time / 20.0) * std::f64::consts::PI) as f32,
        ))) / 2.0
    };
    motion + 7.0 / 16.0
}

fn head_speed(running: bool, tick: i32, rpm: f32) -> f32 {
    if !running {
        rpm / 2.0
    } else if (15..=20).contains(&tick) {
        rpm * 2.0
    } else {
        rpm
    }
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    let mut tag = Compound::new();
    set_float(&mut tag, "VisualSpeed", reading(entity, 0));
    for name in ["Running", "Ticks"] {
        tag.insert(name.into(), Tag::Int(int(&entity.nbt, name).unwrap_or(0)));
    }
    tag
}

pub(super) fn draw(game: &Game<'_>, entity: &ModBlockEntity, draw: &mut BlockEntityDraw) {
    let rpm = float(&entity.nbt, "VisualSpeed").unwrap_or(0.0);
    let running = int(&entity.nbt, "Running") == Some(1);
    let ticks = int(&entity.nbt, "Ticks").unwrap_or(0);
    let angle = wheel_angle(draw.game_time, draw.partial, rpm, 0.0);
    draw_rotating(game, draw, 1, angle, SHAFTLESS_COG);
    let reach = head_offset(running, ticks, draw.partial);
    draw.push();
    draw.translate([0.0, -reach, 0.0]);
    game.native_draw_model(draw, POLE, 0xffffff);
    let whisk_angle = wheel_angle(
        draw.game_time,
        draw.partial,
        head_speed(running, ticks, rpm),
        0.0,
    );
    draw_rotating(game, draw, 1, whisk_angle, WHISK);
    draw.pop();
}
