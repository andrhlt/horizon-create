fn package_filter_character(game: &Game<'_>, c: char, canceled: &mut bool) {
    crate::game::create_package_filter_editor::character(game, c, canceled);
    crate::game::create_clipboard_editor::character(game, c, canceled);
    crate::game::create_requester_editor::character(game, c, canceled);
    crate::game::create_stock_keeper_screen::character(game, c, canceled);
}
