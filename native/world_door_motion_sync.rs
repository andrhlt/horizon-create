fn world_door_motion_sync(
    game: &mut crate::game::Game<'_>,
    pos: (i32, i32, i32),
    previous: Option<horizon_world::registry::BlockStateId>,
    state: horizon_world::registry::BlockStateId,
) {
    crate::game::create_elevator_doors::sync_world_door_motion(game, pos, previous, state);
}
