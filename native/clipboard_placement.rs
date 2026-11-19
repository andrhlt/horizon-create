fn clipboard_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    fluid: horizon_world::fluid::FluidState,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    if answer.is_none()
        && let Some(placed) = crate::game::create_factory_gauge::place(level, state, context, fluid)
    {
        *answer = Some(Some(placed));
    }
    if answer.is_none()
        && let Some(placed) = crate::game::create_stock_link::place(level, state, context, fluid)
    {
        *answer = Some(Some(placed));
    }
    if answer.is_none()
        && let Some(placed) = crate::game::create_redstone_requester::place(level, state, context)
    {
        *answer = Some(Some(placed));
    }
    if answer.is_none()
        && let Some(placed) = crate::game::create_stock_ticker::place(level, state, context)
    {
        *answer = Some(Some(placed));
    }
    if answer.is_none()
        && let Some(placed) = crate::game::create_postbox::place(level, state, context, fluid)
    {
        *answer = Some(Some(placed));
    }
    if answer.is_none()
        && let Some(placed) = crate::game::create_nozzle::place(level, state, context)
    {
        *answer = Some(Some(placed));
    }
    if answer.is_none()
        && let Some(placed) = crate::game::create_toolbox::place(level, state, context, fluid)
    {
        *answer = Some(Some(placed));
    }
    if answer.is_none()
        && let Some(placed) = crate::game::create_backtank::place(level, state, context, fluid)
    {
        *answer = Some(Some(placed));
    }
    if answer.is_none() {
        *answer = crate::game::create_placard::place(level, state, context, fluid);
    }
    if answer.is_none() {
        *answer = crate::game::create_item_hatch::place(level, state, context, fluid);
    }
    if answer.is_none() {
        *answer = crate::game::create_clipboard_block::place(level, state, context, fluid);
    }
}
