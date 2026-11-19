fn press_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    use crate::game::{create_fluids, create_hand_crank, create_press};
    use horizon_core::geometry::Direction;

    let Some(block) = level.native_state_block(state) else {
        return;
    };
    if answer.is_some() || !create_press::assembly_operator(block) {
        return;
    }
    let pos = context.pos;
    let below = horizon_core::position::BlockPos::new(pos.x, pos.y - 1, pos.z);
    let below_state = level.world.block(below.x, below.y, below.z);
    if level.native_state_block(below_state) == Some(create_fluids::BASIN)
        || (context.face == Direction::Up
            && context.hit_pos == below
            && create_press::operator_support(level, below))
    {
        *answer = Some(None);
        return;
    }

    if block != create_press::PRESS {
        return;
    }

    let selected = create_hand_crank::preferred_in_directions(
        level,
        pos,
        [
            Direction::South,
            Direction::West,
            Direction::North,
            Direction::East,
        ],
    )
    .map(Direction::opposite);
    let facing = selected.map_or_else(
        || {
            let rotation = ((f64::from(context.yaw) / 90.0 + 0.5).floor() as i32).rem_euclid(4);
            ["north", "east", "south", "west"][rotation as usize]
        },
        create_fluids::name,
    );
    *answer = Some(level.native_state_with_property(state, "facing", facing));
}
