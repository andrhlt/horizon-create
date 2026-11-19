fn contact_shape(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    direction: horizon_core::geometry::Direction,
    neighbor: horizon_world::registry::BlockStateId,
    result: &mut Option<horizon_world::registry::BlockStateId>,
) {
    crate::game::create_contact::shape(level, state, direction, neighbor, result);
    crate::game::create_latches::support_change(level, state, direction, neighbor, result);
}
