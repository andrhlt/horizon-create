fn package_throw_tick(
    game: &crate::game::Game<'_>,
    stack: &crate::items::ItemStack,
    remaining: i32,
) {
    crate::game::create_package_throw::tick(game, stack, remaining);
}
