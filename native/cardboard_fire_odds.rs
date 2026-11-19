fn cardboard_fire_odds(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    odds: &mut Option<(i32, i32)>,
) {
    if matches!(
        level.native_state_block(state),
        Some("create:cardboard_block" | "create:bound_cardboard_block")
    ) {
        *odds = Some((100, 20));
    }
}
