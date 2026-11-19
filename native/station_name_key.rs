fn station_name_key(game: &Game<'_>, key: &str, modifiers: u32, canceled: &mut bool) {
    crate::game::create_station_name::key(game, key, modifiers, canceled);
    crate::game::create_frogport_screen::key(game, key, modifiers, canceled);
}
