fn attribute_filter_scroll(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    scroll: [f64; 2],
    canceled: &mut bool,
) {
    crate::game::create_list_filter_editor::scroll(game, screen, scroll, canceled);
    crate::game::create_clipboard_editor::scroll(game, scroll[1], canceled);
    crate::game::create_requester_editor::scroll(game, screen, scroll, canceled);
    crate::game::create_stock_keeper_screen::scroll(game, screen, scroll[1], canceled);
}
