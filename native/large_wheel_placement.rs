fn large_wheel_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    if answer.is_none()
        && let Some(placement) = crate::game::create_track::place(level, state, context)
    {
        *answer = Some(placement);
        return;
    }
    if answer.is_none()
        && let Some(placement) = crate::game::create_latches::placement(level, state, context)
    {
        *answer = Some(placement);
        return;
    }
    crate::game::create_large_wheel::placement(level, state, context, answer);
    if answer.is_none()
        && let Some(placement) = crate::game::create_funnel::place(level, state, context)
            .or_else(|| crate::game::create_arm::place(level, state, context))
            .or_else(|| crate::game::create_contact::place(level, state, context))
            .or_else(|| crate::game::create_redstone_link::place(level, state, context))
            .or_else(|| crate::game::create_hose::place(level, state, context))
            .or_else(|| crate::game::create_portable_interface::place(level, state, context))
            .or_else(|| crate::game::create_mechanical_piston::place(level, state, context))
            .or_else(|| crate::game::create_saw::place(level, state, context))
            .or_else(|| crate::game::create_drill::placement(level, state, context))
    {
        *answer = Some(Some(placement));
    }
}
