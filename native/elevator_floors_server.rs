fn elevator_floors_server(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    crate::game::create_elevator_floors::receive_from_client(game, player, channel, data);
}
