fn peculiar_bell_shape(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    direction: horizon_core::geometry::Direction,
    neighbour: horizon_world::registry::BlockStateId,
    result: &mut Option<horizon_world::registry::BlockStateId>,
) {
    crate::game::create_peculiar_bell::update_shape(level, state, direction, neighbour, result);
}
