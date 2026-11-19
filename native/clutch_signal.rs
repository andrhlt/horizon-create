fn clutch_signal(
    level: &crate::game::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
) {
    crate::game::create_machines::observe_clutch_signal(level, [pos.x, pos.y, pos.z], state);
}
