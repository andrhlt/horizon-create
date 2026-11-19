fn symmetry_wand_placed(
    game: &mut crate::game::Game<'_>,
    stack: &crate::items::ItemStack,
    pos: [i32; 3],
    state: horizon_world::registry::BlockStateId,
) {
    crate::game::create_symmetry_wand::placed(game, stack, pos, state);
}
