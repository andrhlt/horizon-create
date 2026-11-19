fn station_name_receive(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    crate::game::create_station_name::receive(game, player, channel, data);
    crate::game::create_frogport_screen::receive(game, player, channel, data);
}
