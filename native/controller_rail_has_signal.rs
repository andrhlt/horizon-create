fn controller_rail_has_signal(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    output: &mut bool,
) {
    if level.native_state_block(state) == Some(crate::game::create_controller_rail::RAIL) {
        *output = true;
    }
}
