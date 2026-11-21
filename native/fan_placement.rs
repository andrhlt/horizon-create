fn fan_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    use crate::game::{create_fan::FAN, create_fluids, create_hand_crank, create_machines};
    use horizon_core::geometry::Direction;

    if answer.is_some() || level.native_state_block(state) != Some(FAN) {
        return;
    }
    let is_chute = |direction: Direction| {
        let [dx, dy, dz] = direction.normal();
        let pos = context.pos.offset(dx, dy, dz);
        matches!(
            level.native_state_block(level.world.block(pos.x, pos.y, pos.z)),
            Some(create_machines::CHUTE | create_machines::PLAIN_CHUTE)
        )
    };
    let facing = if is_chute(context.face.opposite()) {
        context.face.opposite()
    } else if is_chute(context.face) {
        context.face
    } else {
        // The shared helper returns the direction away from the shaft.
        let preferred = create_hand_crank::preferred_direction(level, context.pos)
            .map(Direction::opposite)
            .unwrap_or_else(|| context.nearest_looking_direction());
        if context.sneaking {
            preferred
        } else {
            preferred.opposite()
        }
    };
    *answer = Some(level.native_state_with_property(state, "facing", create_fluids::name(facing)));
}
