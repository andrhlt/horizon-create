fn elevator_floors_editor_mouse(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    canceled: &mut bool,
) {
    crate::game::create_elevator_floors::editor_mouse(game, screen, button, canceled);
}
