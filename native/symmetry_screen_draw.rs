fn symmetry_screen_draw(game: &Game<'_>, screen: &NativeScreenView<'_>, batch: &mut HudBatch) {
    crate::game::create_symmetry_screen::draw(game, screen, batch);
}
