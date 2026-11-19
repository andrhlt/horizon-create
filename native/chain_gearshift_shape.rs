fn chain_gearshift_shape(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    direction: horizon_core::geometry::Direction,
    neighbour: horizon_world::registry::BlockStateId,
    new: &mut Option<horizon_world::registry::BlockStateId>,
) {
    if new.is_none() {
        *new =
            crate::game::create_chain_gearshift::update_shape(level, state, direction, neighbour);
    }
}
