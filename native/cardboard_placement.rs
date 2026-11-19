fn cardboard_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    if answer.is_some()
        || !matches!(
            level.native_state_block(state),
            Some("create:cardboard_block" | "create:bound_cardboard_block")
        )
    {
        return;
    }
    let quadrant = ((f64::from(context.yaw) / 90.0 + 0.5).floor() as i32).rem_euclid(4);
    let axis = if quadrant % 2 == 0 { "z" } else { "x" };
    *answer = Some(level.native_state_with_property(state, "axis", axis));
}
