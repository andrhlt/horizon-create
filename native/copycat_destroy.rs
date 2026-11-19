fn copycat_destroy(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    state: horizon_world::registry::BlockStateId,
    canceled: &bool,
) {
    if !*canceled {
        crate::game::create_copycat::before_destroy(game, pos, state);
    }
}
