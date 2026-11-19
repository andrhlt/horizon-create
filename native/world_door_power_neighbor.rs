fn world_door_power_neighbor(
    level: &mut crate::game::GameLevel<'_>,
    ticks: &mut horizon_world::level::Ticks,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
    handled: &mut bool,
) {
    if !*handled {
        *handled =
            crate::game::create_elevator_doors::world_door_neighbor(level, ticks, pos, state);
    }
}
