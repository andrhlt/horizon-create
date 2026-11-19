fn sequencer_editor_server(game: &mut crate::game::Game<'_>, channel: &str, data: &[u8]) {
    crate::game::create_sequencer_editor::receive_server(game, channel, data);
    crate::game::create_threshold_switch_editor::receive_server(game, channel, data);
}
