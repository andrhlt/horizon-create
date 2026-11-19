fn recipe_lookup_key(game: &mut crate::game::Game<'_>, key: &str, pressed: bool) {
    crate::game::create_recipe_lookup::key(game, key, pressed);
}
