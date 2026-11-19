fn package_filter_mouse(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    modifiers: u32,
    canceled: &mut bool,
) {
    crate::game::create_package_filter_editor::mouse(game, screen, button, modifiers, canceled);
    crate::game::create_list_filter_editor::mouse(game, screen, button, modifiers, canceled);
    crate::game::create_clipboard_editor::mouse(game, screen, button, modifiers, canceled);
    crate::game::create_requester_editor::mouse(game, screen, button, modifiers, canceled);
    crate::game::create_stock_keeper_screen::mouse(game, screen, button, modifiers, canceled);
}
