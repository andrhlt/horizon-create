fn linear_chassis_shape(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    face: horizon_core::geometry::Direction,
    neighbour: horizon_world::registry::BlockStateId,
    new: &mut Option<horizon_world::registry::BlockStateId>,
) {
    if new.is_none() {
        *new = crate::game::create_linear_chassis::update_shape(level, state, face, neighbour);
    }
}
