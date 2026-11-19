// Fixture-only consumer: the command exists only when explicitly enabled.
fn recipe_categories_control(
    game: &mut crate::game::Game<'_>,
    line: &str,
) -> std::ops::ControlFlow<Result<Option<Value>>> {
    if std::env::var_os("CREATE_TEST_RECIPE_CATEGORIES").is_none() {
        return std::ops::ControlFlow::Continue(());
    }
    if line == "create-test-recipe-panel" {
        let page = game
            .panel
            .shown(|_| true)
            .and_then(|shown| shown.recipes.as_ref());
        let page = page.map(|page| serde_json::json!({
            "title": page.title,
            "tabs": page.tabs.iter().map(|s| &s.item).collect::<Vec<_>>(),
            "recipes": page.recipes.iter().map(|r| {
                let multi = r.layout == crate::game::native_hooks::NativeRecipeLayout::Processing;
                let inputs = if multi { &r.slots[..1] } else { &r.slots[..] };
                let outputs: Vec<_> = if multi {
                    r.slots.iter().skip(1).flatten().chain(r.results.iter()).collect()
                } else { r.results.iter().collect() };
                serde_json::json!({
                    "inputs": inputs.iter().map(|slot| slot.iter().map(|s| &s.item).collect::<Vec<_>>()).collect::<Vec<_>>(),
                    "outputs": outputs.iter().map(|s| &s.item).collect::<Vec<_>>(),
                    "output_counts": outputs.iter().map(|s| s.count).collect::<Vec<_>>(),
                    "chance_labels": if multi { r.note.split('|').collect::<Vec<_>>() } else { Vec::new() },
                    "note": r.note,
                    "fluids": r.fluid_inputs.iter().map(|(slot, fluid)| serde_json::json!({"slot": slot, "fluid": fluid.fluid, "amount": fluid.amount})).collect::<Vec<_>>(),
                    "fluid_outputs": r.fluid_outputs.iter().map(|(slot, fluid)| serde_json::json!({"slot": slot, "fluid": fluid.fluid, "amount": fluid.amount})).collect::<Vec<_>>(),
                })
            }).collect::<Vec<_>>(),
        }));
        return std::ops::ControlFlow::Break(Ok(Some(
            serde_json::json!({"ok": true, "panel": page}),
        )));
    }
    if line != "create-test-recipe-categories" {
        return std::ops::ControlFlow::Continue(());
    }
    let categories = game.native_collect_recipe_categories();
    let categories: Vec<_> = categories.into_iter().map(|category| {
        let stack = |s: horizon_client::mod_api::NativeStack| {
            serde_json::json!({"item": s.item, "count": s.count, "components": s.components})
        };
        serde_json::json!({
            "id": category.id,
            "title": category.title,
            "icon": stack(category.icon),
            "catalysts": category.catalysts.into_iter().map(stack).collect::<Vec<_>>(),
            "recipes": category.recipes.into_iter().map(|recipe| serde_json::json!({
                "inputs": recipe.inputs.into_iter().map(|slot| slot.into_iter().map(stack).collect::<Vec<_>>()).collect::<Vec<_>>(),
                "fluids": recipe.fluid_inputs.into_iter().map(|(slot, fluid)| serde_json::json!({"slot": slot, "fluid": fluid.fluid, "amount": fluid.amount})).collect::<Vec<_>>(),
                "fluid_outputs": recipe.fluid_outputs.into_iter().map(|fluid| serde_json::json!({"fluid": fluid.fluid, "amount": fluid.amount})).collect::<Vec<_>>(),
                "outputs": recipe.outputs.into_iter().map(|output| serde_json::json!({
                    "stack": stack(output.stack), "chance": output.chance,
                    "min": output.min, "max": output.max,
                })).collect::<Vec<_>>(),
            })).collect::<Vec<_>>(),
        })
    }).collect();
    std::ops::ControlFlow::Break(Ok(Some(
        serde_json::json!({"ok": true, "categories": categories}),
    )))
}
