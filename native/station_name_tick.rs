fn station_name_tick(game: &mut Game<'_>) {
    crate::game::create_station_name::tick(game);
    crate::game::create_frogport_open::tick(game);
    crate::game::create_frogport_screen::tick(game);
}
