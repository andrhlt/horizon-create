fn use_planks(
    game: &mut crate::game::Game<'_>,
    stack: &crate::items::ItemStack,
    pos: [i32; 3],
    claimed: &mut bool,
) {
    *claimed |= crate::game::create_wheel_material::use_planks(game, pos, stack);
}
