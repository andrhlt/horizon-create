fn train_schedule_use(game: &mut Game<'_>, stack: &crate::items::ItemStack, claimed: &mut bool) {
    crate::game::create_train_schedule::use_schedule(game, stack, claimed);
}
