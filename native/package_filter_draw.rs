fn package_filter_draw(game: &Game<'_>, screen: &NativeScreenView<'_>, batch: &mut HudBatch) {
    crate::game::create_package_filter_editor::draw(game, screen, batch);
    crate::game::create_list_filter_editor::draw(game, screen, batch);
    crate::game::create_clipboard_editor::draw(game, screen, batch);
    crate::game::create_requester_editor::draw(game, screen, batch);
    crate::game::create_stock_keeper_screen::draw(game, screen, batch);
}
