fn speed_controller_input_server(
    game: &mut crate::game::Game<'_>,
    player: u128,
    channel: &str,
    data: &[u8],
) {
    crate::game::create_speed_controller_controls::receive(game, player, channel, data);
}
