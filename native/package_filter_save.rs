fn package_filter_save(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    crate::game::create_package_filter_editor::save(game, player, channel, data);
    crate::game::create_list_filter_editor::edit(game, player, channel, data);
    crate::game::create_clipboard_editor::save(game, player, channel, data);
    crate::game::create_requester_editor::edit(game, player, channel, data);
    crate::game::create_stock_keeper_screen::handle(game, player, channel, data);
}
