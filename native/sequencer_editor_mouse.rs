fn sequencer_editor_mouse(
    game: &crate::game::Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    canceled: &mut bool,
) {
    crate::game::create_sequencer_editor::mouse(game, screen, button, canceled);
    crate::game::create_threshold_switch_editor::mouse(game, screen, button, canceled);
}
