fn recipe_lookup_panel(game: &mut crate::game::Game<'_>, mod_id: &str, event: &NativePanelEvent) {
    crate::game::create_recipe_lookup::panel(game, mod_id, event);
}
