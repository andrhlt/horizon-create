fn ejector_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    fluid: horizon_world::fluid::FluidState,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    use horizon_world::fluid::FluidKind;

    if answer.is_some()
        || level.native_state_block(state) != Some(crate::game::create_ejector::EJECTOR)
    {
        return;
    }
    let horizontal = ((f64::from(context.yaw) / 90.0 + 0.5).floor() as i32).rem_euclid(4);
    let facing = ["north", "east", "south", "west"][horizontal as usize];
    let waterlogged = fluid.kind() == FluidKind::Water && fluid.is_source();
    *answer = Some(
        level
            .native_state_with_property(state, "facing", facing)
            .and_then(|state| {
                level.native_state_with_property(
                    state,
                    "waterlogged",
                    if waterlogged { "true" } else { "false" },
                )
            }),
    );
}
