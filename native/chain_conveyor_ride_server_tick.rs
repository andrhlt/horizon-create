fn chain_conveyor_ride_server_tick(game: &mut Game<'_>) {
    crate::game::create_chain_conveyor_ride_packets::tick(game);
}
