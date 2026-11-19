use horizon_world::level::flags;

use crate::items::ItemStack;

use super::Game;
use super::create_machines::ingredient_matches;

pub(super) fn apply(game: &mut Game<'_>, pos: [i32; 3], held: &ItemStack) -> bool {
    let input = game.native_block(pos);
    let Some(output) = game
        .native_recipes_of_type("create:item_application")
        .iter()
        .find_map(|recipe| {
            let ingredients = recipe.json["ingredients"].as_array()?;
            let [base, tool] = ingredients.as_slice() else {
                return None;
            };
            if !ingredient_matches(game, tool, &held.item)
                || !ingredient_matches(game, base, &input)
            {
                return None;
            }
            let result = game.native_recipe_result(recipe.json["results"].as_array()?.first()?)?;
            game.native_default_state(&result.item)
        })
    else {
        return false;
    };
    let original = game.world.block(pos[0], pos[1], pos[2]);
    let output = game.with_level(|_, level, _| {
        let Some(original) = level.registry.state(original) else {
            return output;
        };
        original
            .properties
            .iter()
            .fold(output, |state, (key, value)| {
                level
                    .native_state_with_property(state, key, value)
                    .unwrap_or(state)
            })
    });
    let changed = game.native_set_block(game.native_dimension(), pos, output, flags::UPDATE_ALL);
    if changed {
        game.with_level(|_, level, _| {
            level.native_play_sound(
                "minecraft:block.copper.break",
                pos.map(|coord| f64::from(coord) + 0.5),
                7,
                1.0,
                1.45,
            );
        });
    }
    changed
}
