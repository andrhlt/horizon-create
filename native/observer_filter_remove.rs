fn observer_filter_remove(
    level: &mut crate::game::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    side_effects: bool,
) {
    crate::game::create_threshold_switch::release_observer_filter(level, pos, side_effects);
}
