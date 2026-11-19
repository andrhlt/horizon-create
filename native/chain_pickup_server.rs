fn chain_pickup_server(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    crate::game::create_chain_conveyor_packages::receive_air_pickup(game, player, channel, data);
}
