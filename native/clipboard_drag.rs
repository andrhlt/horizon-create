fn clipboard_drag(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    canceled: &mut bool,
) {
    crate::game::create_clipboard_editor::drag(game, screen, button, canceled);
}
