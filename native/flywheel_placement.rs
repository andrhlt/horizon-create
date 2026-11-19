fn flywheel_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    use crate::game::create_flywheel;

    if answer.is_none() && level.native_state_block(state) == Some(create_flywheel::FLYWHEEL) {
        *answer = Some(create_flywheel::placement(level, state, context));
    }
}
