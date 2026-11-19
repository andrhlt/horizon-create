fn elevator_floors_client(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    crate::game::create_elevator_floors::receive_from_server(game, channel, data);
    crate::game::create_elevator_doors::receive_from_server(game, channel, data);
}
