fn block_spread(
    level: &crate::game::GameLevel<'_>,
    kind: &str,
    from: horizon_core::position::BlockPos,
    to: horizon_core::position::BlockPos,
    canceled: &mut bool,
) {
    crate::game::create_machines::block_spread(level, kind, from, to, canceled);
}
