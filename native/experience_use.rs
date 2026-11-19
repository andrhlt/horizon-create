fn experience_use(
    game: &mut crate::game::Game<'_>,
    stack: &crate::items::ItemStack,
    claimed: &mut bool,
) {
    crate::game::create_experience::release(game, stack, claimed);
}
