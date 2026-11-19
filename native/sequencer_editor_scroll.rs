fn sequencer_editor_scroll(
    game: &crate::game::Game<'_>,
    mouse: [f32; 2],
    scroll: [f64; 2],
    modifiers: u32,
    canceled: &mut bool,
) {
    crate::game::create_sequencer_editor::scroll(game, mouse, scroll[1], modifiers, canceled);
    crate::game::create_threshold_switch_editor::scroll(game, mouse, scroll[1], modifiers, canceled);
}
