fn package_filter_receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    crate::game::create_package_filter_editor::receive(game, channel, data);
    crate::game::create_list_filter_editor::receive(game, channel, data);
    crate::game::create_clipboard_editor::receive(game, channel, data);
    crate::game::create_requester_editor::receive(game, channel, data);
    crate::game::create_stock_keeper_screen::receive(game, channel, data);
}
