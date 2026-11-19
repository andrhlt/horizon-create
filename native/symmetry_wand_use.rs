fn symmetry_wand_use(game: &mut Game<'_>, stack: &crate::items::ItemStack, claimed: &mut bool) {
    if !*claimed && crate::game::create_symmetry_wand::deactivate(game, stack) {
        *claimed = true;
    }
}
