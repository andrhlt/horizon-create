fn controller_rail_placed(
    level: &crate::game::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    old: horizon_world::registry::BlockStateId,
    new: horizon_world::registry::BlockStateId,
) {
    crate::game::create_controller_rail::placed(level, pos, old, new);
    crate::game::create_machines::motor_block_changed(level, pos, old, new);
}
