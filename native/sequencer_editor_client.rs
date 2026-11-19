fn sequencer_editor_client(
    game: &mut crate::game::Game<'_>,
    player: u128,
    channel: &str,
    data: &[u8],
) {
    crate::game::create_sequencer_editor::receive_client(game, player, channel, data);
    crate::game::create_threshold_switch_editor::receive_client(game, player, channel, data);
}
