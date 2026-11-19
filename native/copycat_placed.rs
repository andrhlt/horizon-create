fn copycat_placed(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    state: horizon_world::registry::BlockStateId,
) {
    crate::game::create_copycat::placed(game, pos, state);
}
