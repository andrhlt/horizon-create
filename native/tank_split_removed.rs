fn tank_split_removed(level: &mut crate::game::GameLevel<'_>, pos: horizon_core::position::BlockPos, ticks: &mut horizon_world::level::Ticks) {
    crate::game::create_fluid_tank::split_pair(level, ticks, [pos.x, pos.y, pos.z]);
}
