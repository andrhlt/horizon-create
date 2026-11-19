fn station_name_extra(game: &mut Game<'_>, block: &str, pos: [i32; 3], data: &mut Option<Vec<u8>>) {
    crate::game::create_station_name::extra(game, block, pos, data);
    crate::game::create_frogport_screen::extra(game, block, pos, data);
}
