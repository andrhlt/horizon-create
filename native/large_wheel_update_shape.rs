fn large_wheel_update_shape(
    level: &crate::game::GameLevel<'_>,
    ticks: &mut horizon_world::level::Ticks,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
) {
    crate::game::create_large_wheel::update_shape(level, ticks, [pos.x, pos.y, pos.z], state);
}
