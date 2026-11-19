fn sequencer_editor_draw(
    game: &crate::game::Game<'_>,
    screen: &NativeScreenView<'_>,
    batch: &mut HudBatch,
) {
    crate::game::create_sequencer_editor::draw(game, screen, batch);
    crate::game::create_threshold_switch_editor::draw(game, screen, batch);
}
