fn sandpaper_start(
    game: &mut crate::game::Game<'_>,
    stack: &crate::items::ItemStack,
    hand: crate::game::Hand,
    canceled: &mut bool,
) {
    crate::game::create_sandpaper::start(game, stack, hand, canceled);
}
