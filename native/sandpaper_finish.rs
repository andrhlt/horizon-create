fn sandpaper_finish(
    game: &mut crate::game::Game<'_>,
    stack: &crate::items::ItemStack,
    hand: crate::game::Hand,
    result: &mut Option<crate::items::ItemStack>,
) {
    crate::game::create_sandpaper::finish(game, stack, hand, result);
}
