fn sandpaper_tick(game: &crate::game::Game<'_>, stack: &crate::items::ItemStack, remaining: i32) {
    crate::game::create_sandpaper::tick(game, stack, remaining);
}
