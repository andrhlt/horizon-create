fn sequencer_editor_tick(game: &mut crate::game::Game<'_>) {
    crate::game::create_sequencer_editor::tick(game);
    crate::game::create_threshold_switch_editor::tick(game);
}
