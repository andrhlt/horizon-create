fn schematic_table_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    if answer.is_some() || level.native_state_block(state) != Some("create:schematic_table") {
        return;
    }
    let horizontal = ((f64::from(context.yaw) / 90.0 + 0.5).floor() as i32).rem_euclid(4);
    let facing = ["north", "east", "south", "west"][horizontal as usize];
    *answer = Some(level.native_state_with_property(state, "facing", facing));
}
