fn clipboard_survive(
    level: &crate::game::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
    survives: &mut Option<bool>,
) {
    if survives.is_none() {
        *survives = crate::game::create_factory_gauge::survive(level, pos, state);
    }
    if survives.is_none() {
        *survives = crate::game::create_nozzle::survive(level, pos, state);
    }
    if survives.is_none() {
        *survives = crate::game::create_placard::survive(level, pos, state);
    }
    if survives.is_none() {
        *survives = crate::game::create_clipboard_block::survive(level, pos, state);
    }
}
