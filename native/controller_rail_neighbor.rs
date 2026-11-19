fn controller_rail_neighbor(
    level: &crate::game::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
) {
    crate::game::create_controller_rail::observe(level, pos, state);
}
