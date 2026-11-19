fn recipe_categories_hook(game: &mut Game<'_>, categories: &mut Vec<NativeRecipeCategory>) {
    crate::game::create_recipe_categories::categories(game, categories);
}
