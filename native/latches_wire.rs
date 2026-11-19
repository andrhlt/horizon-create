fn latches_wire(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    direction: Option<horizon_core::geometry::Direction>,
    answer: &mut Option<bool>,
) {
    *answer = if level
        .native_state_block(state)
        .is_some_and(|name| crate::game::create_depot::nixie_palette(name).is_some())
    {
        Some(direction.is_some())
    } else {
        crate::game::create_latches::wire_connection(level, state, direction)
    };
}
