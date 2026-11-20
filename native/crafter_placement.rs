fn crafter_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    use crate::game::{create_crafter::CRAFTER, create_fluids::name};
    use horizon_core::geometry::Direction;

    if answer.is_some() || level.native_state_block(state) != Some(CRAFTER) {
        return;
    }

    let [dx, dy, dz] = context.face.opposite().normal();
    let support = context.pos.offset(dx, dy, dz);
    let support_state = level.world.block(support.x, support.y, support.z);
    let attached = !context.sneaking && level.native_state_block(support_state) == Some(CRAFTER);
    let rotation = ((f64::from(context.yaw) / 90.0 + 0.5).floor() as i32).rem_euclid(4);
    let mut front = [
        Direction::North,
        Direction::East,
        Direction::South,
        Direction::West,
    ][rotation as usize];
    if attached
        && let Some(facing) = level
            .registry
            .state(support_state)
            .and_then(|state| state.properties.get("facing"))
        && let Some(direction) = Direction::ALL
            .into_iter()
            .find(|&face| name(face) == facing)
    {
        front = direction;
    }
    let positive = matches!(front, Direction::East | Direction::South);
    let pointing = if !attached && front == context.face {
        "up"
    } else {
        match context.face {
            Direction::Down => "up",
            Direction::Up => "down",
            Direction::East | Direction::North if positive => "left",
            Direction::East | Direction::North => "right",
            Direction::West | Direction::South if positive => "right",
            Direction::West | Direction::South => "left",
        }
    };
    *answer = Some(
        level
            .native_state_with_property(state, "facing", name(front))
            .and_then(|state| level.native_state_with_property(state, "pointing", pointing)),
    );
}
