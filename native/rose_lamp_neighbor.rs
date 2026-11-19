fn rose_lamp_neighbor(
    level: &mut crate::game::GameLevel<'_>,
    ticks: &mut horizon_world::level::Ticks,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
    handled: &mut bool,
) {
    if level.native_state_block(state) == Some(crate::game::create_sequencer::SEQUENCER) {
        crate::game::create_sequencer::neighbor(level, ticks, pos);
        *handled = true;
    } else if level.native_state_block(state) == Some(crate::game::create_sticker::STICKER) {
        crate::game::create_sticker::neighbor(level, ticks, pos, state);
        *handled = true;
    } else if level.native_state_block(state) == Some(crate::game::create_steam_whistle::WHISTLE) {
        crate::game::create_steam_whistle::neighbor(level, ticks, pos, state);
        *handled = true;
    } else if level.native_state_block(state).is_some_and(crate::game::create_packager::is_packager) {
        crate::game::create_packager::neighbor(level, ticks, pos, state);
        *handled = true;
    } else if level.native_state_block(state) == Some(crate::game::create_stock_link::LINK) {
        crate::game::create_stock_link::update_power(level, ticks, pos, state);
        *handled = true;
    } else if level.native_state_block(state)
        == Some(crate::game::create_redstone_requester::REQUESTER)
    {
        crate::game::create_redstone_requester::neighbor(level, ticks, pos, state);
        *handled = true;
    } else if crate::game::create_rose_lamp::is_lamp(level, state) {
        crate::game::create_rose_lamp::neighbor(level, ticks, pos, state);
        *handled = true;
    } else if crate::game::create_latches::is_diode(level, state) {
        crate::game::create_latches::neighbor(level, ticks, pos, state);
        *handled = true;
    }
}
