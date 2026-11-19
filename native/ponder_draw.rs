fn ponder_draw(game: &Game<'_>, batch: &mut HudBatch, screen: &NativeScreenView<'_>) {
    crate::game::create_ponder::draw(game, batch, screen);
}
