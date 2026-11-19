fn depot_has_analog_output(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    output: &mut bool,
) {
    *output |= level.native_state_block(state) == Some(crate::game::create_lectern_controller::BLOCK);
    *output |=
        level.native_state_block(state) == Some(crate::game::create_redstone_requester::REQUESTER);
    *output |= level.native_state_block(state) == Some(crate::game::create_burner::LIT_BURNER);
    crate::game::create_depot::has_output(level, state, output);
    *output |= level.native_state_block(state).is_some_and(crate::game::create_packager::is_packager);
    *output |= level
        .native_state_block(state)
        .is_some_and(|name| {
            crate::game::create_postbox::block(name) || crate::game::create_toolbox::block(name)
        });
    *output |= level.native_state_block(state).is_some_and(crate::game::create_backtank::block);
    crate::game::create_train_signal::has_output(level, state, output);
    crate::game::create_sequencer::has_analog_output(level, state, output);
    crate::game::create_item_drain::has_output(level, state, output);
    crate::game::create_vault::has_output(level, state, output);
    crate::game::create_portable_interface::has_output(level, state, output);
    crate::game::create_tank_lighting::has_output(level, state, output);
}
