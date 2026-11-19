fn metal_ladder_shape(
    level: &crate::game::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
    result: &mut Option<horizon_world::registry::BlockStateId>,
) {
    crate::game::create_metal_ladder::shape(level, pos, state, result);
    crate::game::create_steam_whistle::shape(level, pos, state, result);
}
