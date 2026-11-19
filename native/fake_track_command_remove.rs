fn fake_track_command_remove(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    state: horizon_world::registry::BlockStateId,
) {
    if game.native_block(pos) != crate::game::create_track::TRACK
        || game
            .pack
            .assets
            .registry
            .state(state)
            .is_some_and(|block| block.name == crate::game::create_track::TRACK)
    {
        return;
    }
    game.with_level(|_, level, ticks| {
        crate::game::create_fake_track::remove_owner(
            level,
            ticks,
            horizon_core::position::BlockPos::new(pos[0], pos[1], pos[2]),
        );
    });
}
