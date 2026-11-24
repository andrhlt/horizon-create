// A processing recipe lookup from the player's inventory.
use super::native_hooks::{NativeRecipeLayout, NativeRecipeView};
use super::{Game, Screen};
use horizon_client::mod_api::{NativePanelEvent, NativeStack};

pub(super) fn key(game: &mut Game<'_>, key: &str, pressed: bool) {
    if !pressed
        || !matches!(key, "key.keyboard.r" | "key.keyboard.u")
        || game.screen != Screen::Inventory
        || game.title.is_some()
        || game.container.is_some()
        || game.station.is_some()
        || game.craft_table.is_some()
        || game.dialog_open()
        || game
            .remote
            .as_ref()
            .is_some_and(|remote| remote.menu.is_some())
        || game.recipe_search_focused()
        || game.mod_browser_typing()
    {
        return;
    }
    let Some(pointed) = game.mod_browser_pointed() else {
        return;
    };
    show(game, pointed, key == "key.keyboard.u", 0);
}

fn show(game: &mut Game<'_>, mut pointed: NativeStack, uses: bool, selected: usize) {
    let mut matches = Vec::new();
    for category in game
        .native_collect_recipe_categories()
        .into_iter()
        .filter(|category| {
            matches!(
                category.id.as_str(),
                "create:pressing"
                    | "create:milling"
                    | "create:sawing"
                    | "create:mixing"
                    | "create:filling"
                    | "create:crushing"
                    | "create:fan_washing"
            )
        })
    {
        let views: Vec<_> = category
            .recipes
            .into_iter()
            .filter_map(|recipe| {
                if uses
                    && !recipe
                        .inputs
                        .iter()
                        .flatten()
                        .any(|input| input.item == pointed.item)
                {
                    return None;
                }
                if !uses
                    && !recipe
                        .outputs
                        .iter()
                        .any(|output| output.stack.item == pointed.item)
                {
                    return None;
                }
                let multiple = recipe.outputs.len() + recipe.fluid_outputs.len() > 1;
                // The current fluid view supports one fluid output without
                // simultaneous item or other fluid outputs.
                if !recipe.fluid_outputs.is_empty() && multiple {
                    return None;
                }
                // The multi-output layout currently has exactly one input.
                // Mixing with multiple outputs needs a layout for both.
                if recipe.inputs.len() > 1 && multiple {
                    return None;
                }
                if recipe.inputs.len() > 9 {
                    return None;
                }
                let mixing = category.id == "create:mixing";
                if recipe
                    .fluid_inputs
                    .iter()
                    .any(|(_, fluid)| !has_fluid_sprite(game, &fluid.fluid))
                    || recipe
                        .fluid_outputs
                        .iter()
                        .any(|fluid| !has_fluid_sprite(game, &fluid.fluid))
                {
                    return None;
                }
                let note = if mixing {
                    let heat = recipe.notes.join(", ");
                    if let Some(output) =
                        recipe.outputs.first().filter(|output| output.chance < 1.0)
                    {
                        format!("{heat}, {}%", output.chance * 100.0)
                    } else {
                        heat
                    }
                } else if multiple {
                    recipe
                        .outputs
                        .iter()
                        .map(|output| format!("{}%", output.chance * 100.0))
                        .collect::<Vec<_>>()
                        .join("|")
                } else if recipe.outputs[0].chance < 1.0 {
                    format!("{}%", recipe.outputs[0].chance * 100.0)
                } else {
                    String::new()
                };
                let input_count = recipe.inputs.len();
                let grid = matches!(category.id.as_str(), "create:mixing" | "create:filling");
                let mut slots = recipe.inputs;
                let mut outputs = recipe
                    .outputs
                    .into_iter()
                    .map(|output| output.stack)
                    .collect::<Vec<_>>();
                let last = outputs.pop();
                slots.extend(outputs.into_iter().map(|stack| vec![stack]));
                let fluid_outputs = recipe
                    .fluid_outputs
                    .into_iter()
                    .map(|fluid| (input_count, fluid))
                    .collect();
                Some(NativeRecipeView {
                    layout: if multiple {
                        NativeRecipeLayout::Processing
                    } else if grid {
                        NativeRecipeLayout::Grid
                    } else {
                        NativeRecipeLayout::Single
                    },
                    width: if grid { input_count.min(3) as u32 } else { 1 },
                    height: if grid {
                        input_count.div_ceil(3) as u32
                    } else {
                        1
                    },
                    slots,
                    fluid_inputs: recipe.fluid_inputs,
                    results: last.into_iter().collect(),
                    fluid_outputs,
                    note,
                    action: None,
                })
            })
            .collect();
        if !views.is_empty() {
            matches.push((
                category.id,
                category.title,
                category.icon,
                category.catalysts,
                views,
            ));
        }
    }
    if matches.is_empty() || selected >= matches.len() {
        return;
    }
    // With more than one category, tabs select categories. With one category,
    // retain the existing machine catalyst tabs.
    let tabs = if matches.len() > 1 {
        matches
            .iter()
            .map(|(_, _, icon, _, _)| icon.clone())
            .collect()
    } else {
        matches[0].3.clone()
    };
    let multi_category = matches.len() > 1;
    let (id, title, _, _, mut views) = matches.swap_remove(selected);
    if multi_category && id == "create:mixing" {
        let basin = game.translate("block.create.basin", "Basin");
        for view in &mut views {
            view.note = format!("{} · {basin}", view.note);
        }
    }
    // The item list is hidden by the recipe page; retain the lookup and mode
    // there so a tab click can rebuild it from the current synced categories.
    pointed.count = if uses { 2 } else { 1 };
    game.native_panel_items("create", vec![pointed]);
    game.native_panel_recipes("create", &title, tabs, selected as u32, views);
}

fn has_fluid_sprite(game: &Game<'_>, fluid: &str) -> bool {
    let sprite = match fluid {
        "minecraft:water" => "block/water_still".to_owned(),
        "minecraft:lava" => "block/lava_still".to_owned(),
        id if id.starts_with("create:") => format!("create:fluid/{}_still", &id[7..]),
        _ => return false,
    };
    game.gui.atlas.sprites.contains_key(&sprite)
}

pub(super) fn panel(game: &mut Game<'_>, id: &str, event: &NativePanelEvent) {
    if id != "create" {
        return;
    }
    match event {
        NativePanelEvent::Back => {
            game.native_panel_recipes("create", "", Vec::new(), 0, Vec::new());
            game.native_panel_items("create", Vec::new());
        }
        NativePanelEvent::Tab(index) => {
            let query = game
                .panel
                .shown(|owner| owner == "create")
                .and_then(|shown| shown.items.first())
                .cloned();
            if let Some(query) = query {
                let uses = query.count == 2;
                show(game, query, uses, *index as usize);
            }
        }
        _ => {}
    }
}
