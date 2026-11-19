fn train_postbox_registry_removed(
    level: &mut crate::game::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    old: horizon_world::registry::BlockStateId,
) {
    crate::game::create_train_postbox_registry::removed(level, [pos.x, pos.y, pos.z], old);
}
