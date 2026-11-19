fn station_name_character(game: &Game<'_>, c: char, canceled: &mut bool) {
    crate::game::create_station_name::character(game, c, canceled);
    crate::game::create_frogport_screen::character(game, c, canceled);
}
