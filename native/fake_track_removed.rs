fn fake_track_removed(
    level: &mut crate::game::GameLevel<'_>,
    ticks: &mut horizon_world::level::Ticks,
    pos: horizon_core::position::BlockPos,
) {
    crate::game::create_track::remove_endpoint(level, ticks, pos);
}
