fn package_throw_release(
    game: &mut crate::game::Game<'_>,
    stack: &crate::items::ItemStack,
    remaining: i32,
    used: &mut bool,
) {
    crate::game::create_package_throw::release(game, stack, remaining, used);
}
