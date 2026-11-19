fn chain_gearshift_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    if answer.is_none()
        && let Some(placed) = crate::game::create_chain_gearshift::place(level, state, context)
    {
        *answer = Some(Some(placed));
    }
}
