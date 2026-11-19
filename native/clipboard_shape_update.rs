fn clipboard_shape_update(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    direction: horizon_core::geometry::Direction,
    neighbour: horizon_world::registry::BlockStateId,
    new: &mut Option<horizon_world::registry::BlockStateId>,
) {
    if new.is_none() {
        *new = crate::game::create_nozzle::update_shape(level, state, direction, neighbour);
    }
    if new.is_none() {
        *new = crate::game::create_placard::update_shape(level, state, direction, neighbour);
    }
    if new.is_none() {
        *new =
            crate::game::create_clipboard_block::update_shape(level, state, direction, neighbour);
    }
}
