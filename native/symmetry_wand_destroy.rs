fn symmetry_wand_destroy(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    state: horizon_world::registry::BlockStateId,
    canceled: &bool,
) {
    if !*canceled {
        crate::game::create_symmetry_wand::broken(game, pos, state);
    }
}
