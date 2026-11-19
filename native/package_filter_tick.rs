fn package_filter_tick(game: &mut Game<'_>) {
    crate::game::create_package_filter_editor::tick(game);
    crate::game::create_list_filter_editor::tick(game);
    crate::game::create_clipboard_editor::tick(game);
    crate::game::create_requester_editor::tick(game);
    crate::game::create_stock_keeper_screen::tick(game);
}
