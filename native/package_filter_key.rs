fn package_filter_key(game: &Game<'_>, key: &str, modifiers: u32, canceled: &mut bool) {
    crate::game::create_package_filter_editor::key(game, key, modifiers, canceled);
    crate::game::create_clipboard_editor::key(game, key, modifiers, canceled);
    crate::game::create_requester_editor::key(game, key, modifiers, canceled);
    crate::game::create_stock_keeper_screen::key(game, key, modifiers, canceled);
}
