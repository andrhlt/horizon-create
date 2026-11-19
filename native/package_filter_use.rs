fn package_filter_use(game: &mut Game<'_>, stack: &crate::items::ItemStack, claimed: &mut bool) {
    if !*claimed && crate::game::create_shopping_list::discard(game, stack) {
        *claimed = true;
        return;
    }
    crate::game::create_package_filter_editor::open(game, stack, claimed);
    crate::game::create_list_filter_editor::open(game, stack, claimed);
    crate::game::create_package_open::open(game, stack, claimed);
    crate::game::create_clipboard_editor::open(game, stack, claimed);
}
