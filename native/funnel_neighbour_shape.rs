fn funnel_neighbour_shape(
    level: &crate::game::GameLevel<'_>,
    ticks: &mut horizon_world::level::Ticks,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
    direction: horizon_core::geometry::Direction,
    answer: &mut Option<horizon_world::registry::BlockStateId>,
) {
    if answer.is_none()
        && let Some(updated) =
            crate::game::create_funnel::shape_after_neighbour(level, pos, state, direction)
    {
        if level.facts.get(updated).waterlogged {
            level.native_schedule_fluid_tick(ticks, [pos.x, pos.y, pos.z], "minecraft:water", 5);
        }
        *answer = Some(updated);
    }
}
