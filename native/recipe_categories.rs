// Recipe-viewer data for Create processing recipes.
use super::Game;
use horizon_client::mod_api::{
    NativeCategoryRecipe, NativeChanceOutput, NativeFluidStack, NativeRecipeCategory, NativeStack,
};
use serde_json::Value;

fn stack(item: impl Into<String>, count: u32) -> NativeStack {
    NativeStack {
        item: item.into(),
        count,
        components: String::new(),
    }
}

fn ingredient(value: &Value) -> Value {
    match value {
        Value::Array(values) => Value::Array(values.iter().map(ingredient).collect()),
        Value::Object(_) if value.get("item").is_some() => value["item"].clone(),
        Value::Object(_) if value["tag"].is_string() => {
            Value::String(format!("#{}", value["tag"].as_str().unwrap()))
        }
        _ => value.clone(),
    }
}

fn is_item_ingredient(value: &Value) -> bool {
    match value {
        Value::String(_) => true,
        Value::Array(values) => !values.is_empty() && values.iter().all(is_item_ingredient),
        Value::Object(_) => {
            value.get("type").is_none()
                && value.get("fluid").is_none()
                && (value["item"].is_string() || value["tag"].is_string())
        }
        _ => false,
    }
}

pub(super) fn categories(game: &mut Game<'_>, categories: &mut Vec<NativeRecipeCategory>) {
    for (id, kind, title, fallback, catalyst) in [
        (
            "create:pressing",
            "create:pressing",
            "create.recipe.pressing",
            "Pressing",
            "create:mechanical_press",
        ),
        (
            "create:milling",
            "create:milling",
            "create.recipe.milling",
            "Milling",
            "create:millstone",
        ),
        (
            "create:sawing",
            "create:cutting",
            "create.recipe.sawing",
            "Sawing",
            "create:mechanical_saw",
        ),
        (
            "create:mixing",
            "create:mixing",
            "create.recipe.mixing",
            "Mixing",
            "create:mechanical_mixer",
        ),
        (
            "create:filling",
            "create:filling",
            "create.recipe.filling",
            "Filling",
            "create:spout",
        ),
        (
            "create:fan_washing",
            "create:splashing",
            "create.recipe.fan_washing",
            "Bulk Washing",
            "create:encased_fan",
        ),
    ] {
        let mut entry = category(game, id, kind, title, fallback, catalyst);
        if id == "create:fan_washing" {
            let name = game.translate("create.recipe.fan_washing.fan", "Fan behind Flowing Water");
            let component = format!(
                "[minecraft:custom_name={{text:{},italic:false}}]",
                serde_json::to_string(&name).unwrap()
            );
            entry.icon.components = component.clone();
            entry.catalysts[0].components = component;
        }
        categories.push(entry);
    }
    // Create's JEI Crushing category includes Milling recipes unless the
    // first Milling ingredient matches an existing Crushing input.
    let excluded = game
        .native_recipes_of_type("create:crushing")
        .iter()
        .filter_map(|recipe| {
            let input = recipe.json["ingredients"].as_array()?.first()?;
            if !is_item_ingredient(input) {
                return None;
            }
            game.native_recipe_ingredient(&ingredient(input))
        })
        .collect::<Vec<_>>();
    let mut crushing = category(
        game,
        "create:crushing",
        "create:crushing",
        "create.recipe.crushing",
        "Crushing",
        "create:crushing_wheel",
    );
    if let Some(milling) = categories
        .iter()
        .find(|category| category.id == "create:milling")
    {
        crushing.recipes.extend(
            milling
                .recipes
                .iter()
                .filter(|recipe| {
                    recipe
                        .inputs
                        .first()
                        .and_then(|slot| slot.first())
                        .is_some_and(|sample| {
                            !excluded
                                .iter()
                                .any(|ingredient| ingredient.items.contains(&sample.item))
                        })
                })
                .cloned(),
        );
    }
    categories.push(crushing);
}

fn category(
    game: &mut Game<'_>,
    id: &str,
    kind: &str,
    title: &str,
    fallback: &str,
    catalyst: &str,
) -> NativeRecipeCategory {
    let recipes = game
        .native_recipes_of_type(kind)
        .iter()
        .filter_map(|recipe| {
            let ingredients = recipe.json["ingredients"].as_array()?;
            let multi_input = matches!(kind, "create:mixing" | "create:filling");
            if ingredients.is_empty() || (!multi_input && ingredients.len() != 1) {
                return None;
            }
            let mut inputs = Vec::new();
            let mut fluid_inputs = Vec::new();
            for input in ingredients {
                if multi_input
                    && input["type"].as_str() == Some("neoforge:single")
                    && input.get("components").is_none()
                {
                    let fluid = input["fluid"].as_str()?.to_owned();
                    let amount = i32::try_from(input["amount"].as_i64()?)
                        .ok()
                        .filter(|n| *n > 0)?;
                    fluid_inputs.push((
                        inputs.len(),
                        NativeFluidStack {
                            fluid,
                            amount,
                            components: Default::default(),
                        },
                    ));
                    inputs.push(Vec::new());
                } else {
                    // Unknown fluids and custom ingredient forms need their own display.
                    if !is_item_ingredient(input) {
                        return None;
                    }
                    inputs.push(
                        game.native_recipe_ingredient(&ingredient(input))?
                            .order
                            .into_iter()
                            .map(|item| stack(item, 1))
                            .collect(),
                    );
                }
            }
            let notes = if kind == "create:mixing" {
                let (key, fallback) = match recipe.json["heat_requirement"]
                    .as_str()
                    .unwrap_or("none")
                {
                    "none" => ("create.recipe.heat_requirement.none", "No Heating Required"),
                    "heated" => ("create.recipe.heat_requirement.heated", "Heated"),
                    "superheated" => ("create.recipe.heat_requirement.superheated", "Super-Heated"),
                    _ => return None,
                };
                vec![game.translate(key, fallback)]
            } else {
                Vec::new()
            };
            let mut outputs = Vec::new();
            let mut fluid_outputs = Vec::new();
            for result in recipe.json["results"].as_array()? {
                if kind == "create:mixing"
                    && matches!(
                        result["id"].as_str(),
                        Some("create:honey" | "create:chocolate" | "minecraft:lava")
                    )
                    && result.get("components").is_none()
                    && result.get("chance").is_none()
                {
                    let amount = i32::try_from(result["amount"].as_i64()?)
                        .ok()
                        .filter(|n| *n > 0)?;
                    fluid_outputs.push(NativeFluidStack {
                        fluid: result["id"].as_str()?.into(),
                        amount,
                        components: Default::default(),
                    });
                } else {
                    let item = game.native_recipe_result(result)?;
                    outputs.push(NativeChanceOutput {
                        stack: NativeStack {
                            item: item.item.to_string(),
                            count: item.count,
                            components: super::native_recipes::components(&item),
                        },
                        chance: result["chance"].as_f64().unwrap_or(1.0) as f32,
                        min: item.count,
                        max: item.count,
                        notes: Vec::new(),
                    });
                }
            }
            if outputs.is_empty() && fluid_outputs.is_empty() {
                return None;
            }
            Some(NativeCategoryRecipe {
                inputs,
                fluid_inputs,
                outputs,
                fluid_outputs,
                notes,
            })
        })
        .collect();
    NativeRecipeCategory {
        id: id.into(),
        title: game.translate(title, fallback),
        subtitle: String::new(),
        icon: stack(catalyst, 1),
        catalysts: if kind == "create:mixing" {
            vec![stack(catalyst, 1), stack("create:basin", 1)]
        } else {
            vec![stack(catalyst, 1)]
        },
        recipes,
    }
}
