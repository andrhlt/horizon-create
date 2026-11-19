fn chain_conveyor_hanging_client(game: &Game<'_>, channel: &str, data: &[u8]) {
    crate::game::create_chain_conveyor_hanging::receive(game, channel, data);
}
