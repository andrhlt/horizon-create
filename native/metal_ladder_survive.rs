fn metal_ladder_survive(
    level: &crate::game::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
    survives: &mut Option<bool>,
) {
    crate::game::create_metal_ladder::survive(level, pos, state, survives);
    crate::game::create_steam_whistle::survive(level, pos, state, survives);
}
