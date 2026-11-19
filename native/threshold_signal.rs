fn threshold_signal(
    level: &crate::game::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
    face: horizon_core::geometry::Direction,
    direct: bool,
    signal: &mut i32,
) {
    crate::game::create_track_observer::signal(level, state, direct, signal);
    crate::game::create_placard::signal(level, state, face, direct, signal);
    crate::game::create_threshold_switch::signal(level, state, face, direct, signal);
    crate::game::create_elevator::signal(level, state, face, direct, signal);
    crate::game::create_contact::signal(level, state, face, direct, signal);
    crate::game::create_redstone_link::signal(level, pos, state, face, direct, signal);
    crate::game::create_analog_lever::signal(level, pos, state, face, direct, signal);
    crate::game::create_rose_lamp::signal(level, pos, state, face, direct, signal);
    crate::game::create_latches::signal(level, state, face, signal);
    crate::game::create_desk_bell::signal(level, state, face, direct, signal);
}
