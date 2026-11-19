fn clockwork_remove(
    level: &crate::game::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    old: horizon_world::registry::BlockStateId,
    side_effects: bool,
) {
    crate::game::create_clockwork::queue_removal(level, pos, old, side_effects);
}
