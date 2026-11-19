fn station_name_mouse(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    canceled: &mut bool,
) {
    crate::game::create_station_name::mouse(game, screen, button, canceled);
    crate::game::create_frogport_screen::mouse(game, screen, button, canceled);
}
