fn fluid_pipe_shape(
    level: &crate::game::GameLevel<'_>,
    ticks: &mut horizon_world::level::Ticks,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
    direction: horizon_core::geometry::Direction,
    neighbour: horizon_world::registry::BlockStateId,
    answer: &mut Option<horizon_world::registry::BlockStateId>,
) {
    use crate::game::create_fluids::{self, PIPE};
    let Some(block) = level.native_state_block(state) else {
        return;
    };
    if !create_fluids::transport_block(block) {
        return;
    }
    let at = [pos.x, pos.y, pos.z];
    let updated = if answer.is_none() && block == PIPE {
        let updated = create_fluids::pipe_connections(
            level, pos, state, direction, Some(direction.opposite()),
        );
        *answer = Some(updated);
        updated
    } else {
        state
    };
    if level.facts.get(updated).waterlogged {
        level.native_schedule_fluid_tick(ticks, at, "minecraft:water", 5);
    }
    if updated != state || level.native_state_block(neighbour).is_some_and(create_fluids::updates_connections) {
        level.native_schedule_block_tick(ticks, at, block, 1);
    }
}
