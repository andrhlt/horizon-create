fn girder_shape(
    level: &crate::game::GameLevel<'_>,
    ticks: &mut horizon_world::level::Ticks,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
    direction: horizon_core::geometry::Direction,
    neighbour: horizon_world::registry::BlockStateId,
    new: &mut Option<horizon_world::registry::BlockStateId>,
) {
    if new.is_none()
        && let Some(updated) =
            crate::game::create_shaft::update_girder_shape(level, pos, state, direction, neighbour)
    {
        if level.facts.get(updated).waterlogged {
            level.native_schedule_fluid_tick(ticks, [pos.x, pos.y, pos.z], "minecraft:water", 5);
        }
        *new = Some(updated);
    }
}
