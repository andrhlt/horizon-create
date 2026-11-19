fn fluid_valve_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    if answer.is_none()
        && let Some(placed) = crate::game::create_valve::place(level, state, context)
    {
        *answer = Some(Some(placed));
    }
}
