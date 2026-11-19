fn ejector_player_launch(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    crate::game::create_ejector::receive_player_launch(game, player, channel, data);
}
