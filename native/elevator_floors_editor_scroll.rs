fn elevator_floors_editor_scroll(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    scroll: [f64; 2],
    canceled: &mut bool,
) {
    crate::game::create_station_name::scroll(game, screen, scroll[1], canceled);
    crate::game::create_elevator_floors::editor_scroll(game, screen, scroll[1], canceled);
}
