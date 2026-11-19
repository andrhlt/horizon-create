fn threshold_source(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    source: &mut bool,
) {
    crate::game::create_threshold_switch::source(level, state, source);
    crate::game::create_elevator::source(level, state, source);
    crate::game::create_contact::source(level, state, source);
    crate::game::create_redstone_link::source(level, state, source);
    crate::game::create_analog_lever::source(level, state, source);
    *source |=
        level.native_state_block(state) == Some(crate::game::create_track_observer::OBSERVER);
    *source |= crate::game::create_rose_lamp::is_lamp(level, state);
    *source |= crate::game::create_latches::is_diode(level, state);
    *source |= crate::game::create_desk_bell::is_bell(level, state);
    *source |= level.native_state_block(state) == Some(crate::game::create_placard::ITEM);
}
