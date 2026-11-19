fn speed_controller_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    fluid: horizon_world::fluid::FluidState,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    if answer.is_none()
        && let Some(placed) = crate::game::create_cogwheel::place(level, state, context, fluid)
            .or_else(|| crate::game::create_speed_controller::place(level, state, context))
            .or_else(|| crate::game::create_shaft::place(level, state, context, fluid))
            .or_else(|| crate::game::create_threshold_switch::place(level, state, context))
            .or_else(|| crate::game::create_speed_controller::place_motor(level, state, context))
            .or_else(|| crate::game::create_bearing::windmill_place(level, state, context))
    {
        *answer = Some(placed);
    }
}
