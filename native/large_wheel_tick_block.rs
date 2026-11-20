fn large_wheel_tick_block(
    level: &mut crate::game::GameLevel<'_>,
    ticks: &mut horizon_world::level::Ticks,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
) {
    crate::game::create_fluids::tick_changed_pipe(level, pos, state);
    crate::game::create_large_wheel::tick_block(level, ticks, pos, state);
    crate::game::create_sequencer::tick_block(level, ticks, pos, state);
    crate::game::create_contact::tick(level, ticks, pos, state);
    crate::game::create_rose_lamp::tick(level, ticks, pos, state);
    crate::game::create_latches::tick(level, ticks, pos, state);
    crate::game::create_item_hatch::tick(level, ticks, pos, state);
}
