fn potato_cannon_on(game: &mut crate::game::Game<'_>, stack: &crate::items::ItemStack, claimed: &mut bool) {
    crate::game::create_potato_cannon::fire(game, stack, claimed);
}
