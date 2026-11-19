fn depot_analog_output(
    level: &crate::game::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
    output: &mut i32,
) {
    if level.native_state_block(state) == Some(crate::game::create_lectern_controller::BLOCK) { *output = 15; }
    if level.native_state_block(state) == Some(crate::game::create_burner::LIT_BURNER) {
        *output = if level.registry.state(state).and_then(|s| s.properties.get("flame_type")).is_some_and(|flame| flame == "soul") { 2 } else { 1 };
    }
    crate::game::create_depot::output(level, pos, state, output);
    crate::game::create_redstone_requester::output(level, pos, state, output);
    crate::game::create_packager::output(level, pos, state, output);
    crate::game::create_postbox::output(level, pos, state, output);
    crate::game::create_toolbox::output(level, pos, state, output);
    crate::game::create_backtank::output(level, pos, state, output);
    crate::game::create_train_signal::output(level, pos, state, output);
    crate::game::create_sequencer::analog_output(level, state, output);
    crate::game::create_item_drain::output(level, pos, state, output);
    crate::game::create_vault::output(level, pos, state, output);
    crate::game::create_portable_interface::output(level, pos, state, output);
    crate::game::create_tank_lighting::output(level, pos, state, output);
}
