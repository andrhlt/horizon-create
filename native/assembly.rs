use horizon_core::random::{LegacyRandom, RandomSource};
use horizon_world::nbt::{Compound, Tag};
use serde_json::Value;
use std::cell::RefCell;

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_machines::{ingredient_matches, int, reading, set_float};

const COMPONENT: &str = "create:sequenced_assembly";

pub(super) enum Action {
    Pass,
    Hold,
    Output { stack: ItemStack, locked: bool },
}

pub(super) enum ResultStack {
    Item(ItemStack),
    Weighted(Vec<(ItemStack, f32)>),
}

thread_local! {
    // Isolated fixture runners seed only this recipe roll.
    static FIXTURE_RANDOM: RefCell<Option<LegacyRandom>> = RefCell::new(
        std::env::var("CREATE_ASSEMBLY_TRACE_SEED").ok()
            .and_then(|seed| seed.parse().ok())
            .map(LegacyRandom::new),
    );
}

impl ResultStack {
    pub(super) fn stack(self, game: &mut Game<'_>) -> ItemStack {
        match self {
            Self::Item(stack) => stack,
            Self::Weighted(options) => {
                let random = FIXTURE_RANDOM
                    .with_borrow_mut(|seed| seed.as_mut().map(RandomSource::next_float))
                    .unwrap_or_else(|| game.world.random.next_float());
                let mut roll = random * options.iter().map(|(_, weight)| weight).sum::<f32>();
                let last = options.len() - 1;
                for (index, (stack, weight)) in options.into_iter().enumerate() {
                    roll -= weight;
                    if roll < 0.0 || index == last {
                        return stack;
                    }
                }
                unreachable!("a weighted assembly must have at least two outcomes");
            }
        }
    }
}

fn matches(game: &Game<'_>, value: &Value, item: &str) -> bool {
    value.as_array().map_or_else(
        || ingredient_matches(game, value, item),
        |choices| {
            choices
                .iter()
                .any(|value| ingredient_matches(game, value, item))
        },
    )
}

pub(super) fn result(
    game: &Game<'_>,
    stack: &ItemStack,
    kind: &str,
    tool: Option<&ItemStack>,
) -> Option<ResultStack> {
    result_matching(game, stack, kind, tool, |_| true)
}

fn result_matching(
    game: &Game<'_>,
    stack: &ItemStack,
    kind: &str,
    tool: Option<&ItemStack>,
    mut accepts: impl FnMut(&Value) -> bool,
) -> Option<ResultStack> {
    let progress = stack.data().and_then(|data| data.other(COMPONENT));
    game.native_recipes_of_type(COMPONENT).iter().find_map(|recipe| {
        let json = &recipe.json;
        let next_item = &json["transitional_item"];
        let step = match progress {
            None if matches(game, &json["ingredient"], &stack.item) => 0,
            Some(Tag::Compound(progress))
                if matches!(progress.get(&"id".into()), Some(Tag::String(id)) if id.to_string_lossy() == recipe.id)
                    && next_item["id"].as_str() == Some(stack.item.as_ref()) =>
            {
                usize::try_from(int(progress, "step")?).ok()?
            }
            _ => return None,
        };
        let sequence = json["sequence"].as_array()?;
        let operation = &sequence[step.checked_rem(sequence.len())?];
        if operation["type"].as_str() != Some(kind)
            || tool.is_some_and(|tool| !matches(game, &operation["ingredients"][1], &tool.item))
            || !accepts(operation)
        {
            return None;
        }
        let loops = usize::try_from(json["loops"].as_u64().unwrap_or(1)).ok()?;
        let count = sequence.len().checked_mul(loops)?;
        let next = step.checked_add(1)?;
        if next >= count {
            let results = json["results"].as_array()?;
            let mut choices = results.iter().filter_map(|result| {
                let chance = result["chance"].as_f64().unwrap_or(1.0) as f32;
                if chance <= 0.0 {
                    return None;
                }
                Some((game.native_recipe_result(result)?, chance))
            }).collect::<Vec<_>>();
            return match choices.len() {
                0 => None,
                1 => choices.pop().map(|(stack, _)| ResultStack::Item(stack)),
                _ => Some(ResultStack::Weighted(choices)),
            };
        }
        let mut output = game.native_recipe_result(next_item)?;
        let mut data = Compound::new();
        data.insert("id".into(), Tag::String(recipe.id.as_str().into()));
        data.insert("step".into(), Tag::Int(i32::try_from(next).ok()?));
        set_float(&mut data, "progress", next as f32 / count as f32);
        output.data_mut().set_other(COMPONENT, Some(Tag::Compound(data)));
        Some(ResultStack::Item(output))
    })
}

pub(super) fn fill(
    game: &Game<'_>,
    stack: &ItemStack,
    fluid: Option<&super::create_fluids::Fluid>,
) -> (bool, Option<(i32, ResultStack)>) {
    let mut fillable = false;
    let mut amount = 0;
    let output = result_matching(game, stack, "create:filling", None, |operation| {
        let required = &operation["ingredients"][1];
        let Some(required_amount) = required["amount"]
            .as_i64()
            .and_then(|n| i32::try_from(n).ok())
            .filter(|amount| *amount > 0)
        else {
            return false;
        };
        fillable = true;
        amount = required_amount;
        fluid.is_some_and(|fluid| super::create_spout::matches_fluid(fluid, required))
    });
    (fillable, output.map(|stack| (amount, stack)))
}

pub(super) fn deployer_state(entity: &ModBlockEntity) -> &str {
    match entity.nbt.get(&"State".into()) {
        Some(Tag::String(value)) if value.to_string_lossy() == "EXPANDING" => "EXPANDING",
        Some(Tag::String(value)) if value.to_string_lossy() == "RETRACTING" => "RETRACTING",
        _ => "WAITING",
    }
}

fn standalone_application(
    game: &Game<'_>,
    input: &ItemStack,
    held: &ItemStack,
) -> Option<(ResultStack, bool)> {
    ["create:deploying", "create:item_application"]
        .into_iter()
        .find_map(|kind| {
            game.native_recipes_of_type(kind).iter().find_map(|recipe| {
                if recipe.id.ends_with("_manual_only") {
                    return None;
                }
                let [target, tool] = recipe.json["ingredients"].as_array()?.as_slice() else {
                    return None;
                };
                if !matches(game, target, &input.item) || !matches(game, tool, &held.item) {
                    return None;
                }
                let [output] = recipe.json["results"].as_array()?.as_slice() else {
                    return None;
                };
                Some((
                    ResultStack::Item(game.native_recipe_result(output)?),
                    recipe.json["keep_held_item"].as_bool().unwrap_or(false),
                ))
            })
        })
}

pub(super) fn deploy(
    game: &mut Game<'_>,
    pos: [i32; 3],
    stack: &mut ItemStack,
    locked: bool,
) -> Action {
    if game.native_block_property(pos, "facing").as_deref() != Some("down") {
        return Action::Pass;
    }
    let powered = game.native_neighbor_signal(game.native_dimension(), pos) > 0;
    let Some(entity) = super::create_machines::mod_entity(game, pos) else {
        return Action::Pass;
    };
    if reading(entity, 0) == 0.0
        || matches!(entity.nbt.get(&"Mode".into()), Some(Tag::String(mode)) if mode.to_string_lossy() == "PUNCH")
    {
        return Action::Pass;
    }
    let state = deployer_state(entity);
    if !locked && state != "WAITING" {
        return Action::Hold;
    }
    if state == "WAITING" && powered {
        return Action::Pass;
    }
    let Some(tool) = entity.items.first().and_then(Option::as_ref) else {
        return Action::Hold;
    };
    let Some((output, keep_held)) = result(game, stack, "create:deploying", Some(tool))
        .map(|output| (output, false))
        .or_else(|| standalone_application(game, stack, tool))
    else {
        return Action::Pass;
    };
    if locked && state == "RETRACTING" && int(&entity.nbt, "Timer") == Some(1000) {
        if !keep_held {
            game.native_with_mod_block_entity(pos, |entity| {
                if let Some(tool) = &mut entity.items[0] {
                    tool.count -= 1;
                    if tool.count == 0 {
                        entity.items[0] = None;
                    }
                }
            });
        }
        game.native_block_entity_sync(pos);
        stack.count -= 1;
        return Action::Output {
            stack: output.stack(game),
            locked: false,
        };
    }
    if state == "WAITING" {
        game.native_with_mod_block_entity(pos, |entity| {
            entity
                .nbt
                .insert("State".into(), Tag::String("EXPANDING".into()));
            entity.nbt.insert("Timer".into(), Tag::Int(1000));
        });
        game.native_block_entity_sync(pos);
    }
    Action::Hold
}
