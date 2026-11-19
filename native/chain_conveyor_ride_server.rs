fn chain_conveyor_ride_server(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    crate::game::create_chain_conveyor_ride_packets::receive(game, player, channel, data);
}
