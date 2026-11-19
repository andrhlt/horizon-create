fn factory_gauge_destroy(game: &mut crate::game::Game<'_>, pos: [i32; 3], canceled: &mut bool) {
    crate::game::create_factory_gauge::break_panel(game, pos, canceled);
}
